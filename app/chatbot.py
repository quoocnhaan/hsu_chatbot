import asyncio
import os
import pickle
from pathlib import Path

import chromadb
import ollama
import pandas as pd
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from underthesea import word_tokenize

BASE_DIR = Path(__file__).resolve().parent.parent

APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"

CHROMA_DB_PATH = BASE_DIR / "chroma_db"
BM25_PATH = DATA_DIR / "bm25_index.pkl"
CSV_PATH = DATA_DIR / "all_chunks.csv"

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = chroma_client.get_collection("hsu_rules")

embed_model = SentenceTransformer("BAAI/bge-m3", trust_remote_code=True)

with open(BM25_PATH, "rb") as f:
    bm25 = pickle.load(f)

df = pd.read_csv(CSV_PATH)
all_docs = []
for i, row in df.iterrows():
    title = str(row.get("title", "")).strip()
    content = str(row.get("content", "")).strip()
    source = str(row.get("source", "")).strip()
    if not content or content == "nan":
        continue
    all_docs.append({"title": title, "content": content, "source": source})

ollama_client = ollama.AsyncClient()


def embed_query(query: str):
    embedding = embed_model.encode(query, normalize_embeddings=True)
    return embedding.tolist()


def retrieve(query: str, k: int = 5):
    q_emb = embed_query(query)
    results = collection.query(query_embeddings=[q_emb], n_results=k)
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    retrieved = []
    for d, m, dist in zip(docs, metas, distances):
        retrieved.append(
            {
                "score": round(1 - dist, 4),
                "content": d,
                "title": m.get("parent_title"),
                "source": m.get("source"),
            }
        )
    return retrieved


def bm25_retrieve(query: str, k: int = 10):
    query_tokens = word_tokenize(query.lower())
    scores = bm25.get_scores(query_tokens)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    results = []
    for idx, score in ranked[:k]:
        if score <= 0:
            continue
        chunk = all_docs[idx]
        full_text = f"Title: {chunk['title']}\n\nContent:\n{chunk['content']}".strip()
        results.append(
            {
                "score": round(score, 4),
                "content": full_text,
                "title": chunk["title"],
                "source": chunk["source"],
            }
        )
    return results


def hybrid_search(query: str, top_k: int = 5):
    vector_results = retrieve(query, k=top_k)
    bm25_results = bm25_retrieve(query, k=top_k)

    merged = {}
    for r in vector_results:
        merged[r["content"]] = r
    for r in bm25_results:
        if r["content"] not in merged:
            merged[r["content"]] = r

    final_results = list(merged.values())
    return final_results[:top_k]


def build_prompt(context_docs, question: str):
    context_parts = []
    for i, doc in enumerate(context_docs):
        title = doc.get("title", "Không rõ tiêu đề")
        content = doc.get("content", "")
        context_parts.append(f"Tài liệu {i + 1} - {title}:\n{content}")

    context_text = "\n\n".join(context_parts)

    system_msg = "Bạn là trợ lý ảo chuyên nghiệp và lịch sự của trường đại học."

    format_constraint = f"""
QUY TẮC:
1. CHỈ sử dụng thông tin được cung cấp trong phần <NGỮ_CẢNH> bên dưới hoặc từ lịch sử trò chuyện để trả lời.
2. Tuyệt đối không suy đoán, bịa đặt, hoặc sử dụng kiến thức bên ngoài.
3. Nếu <NGỮ_CẢNH> và lịch sử trò chuyện không chứa thông tin để trả lời, hãy trả lời chính xác câu này: "Tôi không tìm thấy thông tin này."
4. Trả lời bằng tiếng Việt một cách rõ ràng, ngắn gọn và mạch lạc.

<NGỮ_CẢNH>
{context_text}
</NGỮ_CẢNH>
"""
    return system_msg, format_constraint


async def reformulate_query(user_message: str, chat_history: list) -> str:
    if not chat_history:
        return user_message
    
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
    prompt = f"""Dưới đây là lịch sử trò chuyện:
{history_text}

Dựa vào lịch sử trên, hãy viết lại câu hỏi sau đây của người dùng thành một câu hỏi độc lập và rõ nghĩa nhất (thay thế đại từ 'thầy', 'cô', 'anh ấy', 'môn đó'... bằng tên riêng cụ thể). 
Câu hỏi của người dùng: "{user_message}"

Yêu cầu bắt buộc: CHỈ trả về đúng 1 câu hỏi đã viết lại, KHÔNG giải thích, KHÔNG thêm ngoặc kép, KHÔNG thêm bất kỳ từ nào khác."""

    try:
        response = await ollama_client.chat(
            model="qwen3:8b",
            messages=[
                {"role": "system", "content": "Bạn là trợ lý chuyên phân tích ngữ cảnh. Hãy làm chính xác theo yêu cầu."},
                {"role": "user", "content": prompt}
            ],
            options={"temperature": 0.1}
        )
        raw_output = response["message"]["content"]
        print(f"[DEBUG] Raw Ollama Reformulate Output: {raw_output}")
        
        reformulated = raw_output.strip()
        # Fallback if the model is too talkative or fails
        if len(reformulated) > 300 or len(reformulated) < 2:
            return user_message
        return reformulated
    except Exception as e:
        print(f"[DEBUG] Lỗi khi viết lại câu hỏi: {e}")
        return user_message


async def generate_chatbot_response(user_message: str, chat_history: list = None) -> str:
    """
    Generates a response asynchronously using Ollama and Hybrid Search RAG.
    """
    if chat_history is None:
        chat_history = []
        
    try:
        print(f"\n[DEBUG] Lịch sử trò chuyện nhận được: {len(chat_history)} tin nhắn")
        for i, m in enumerate(chat_history):
            print(f"  {i}: {m['role']} - {m['content']}")
            
        # 1. Viết lại câu hỏi để tìm kiếm tốt hơn (tránh mất context)
        search_query = await reformulate_query(user_message, chat_history)
        print(f"\n[DEBUG] Câu hỏi gốc: {user_message}")
        print(f"[DEBUG] Câu hỏi viết lại để tìm kiếm: {search_query}\n")
        
        # 2. Tìm kiếm với câu hỏi đã viết lại
        best_chunks = hybrid_search(search_query, top_k=5)
        print(f"[DEBUG] Kết quả: {best_chunks}\n")


        system_msg, format_constraint = build_prompt(best_chunks, search_query)

        # 3. Đưa lịch sử trò chuyện vào ngữ cảnh của Ollama
        messages = [{"role": "system", "content": f"{system_msg}\n{format_constraint}"}]
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        current_temp = 0.2

        response = await ollama_client.chat(
            model="qwen3:8b",
            messages=messages,
            options={
                "temperature": current_temp,
                "top_p": 0.9,
                "num_predict": 2048,
                "repeat_penalty": 1.05,
            },
        )

        return response["message"]["content"]
    except Exception as e:
        return f"Xin lỗi, hệ thống đang gặp sự cố: {e}"
