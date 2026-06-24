import asyncio
import os
import pickle
from contextlib import AsyncExitStack
from pathlib import Path

import chromadb
import pandas as pd
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_mcp.toolkit import MCPToolkit
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from underthesea import word_tokenize

BASE_DIR = Path(__file__).resolve().parent.parent

APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"

CHROMA_DB_PATH = BASE_DIR / "chroma_db"
BM25_PATH = DATA_DIR / "bm25_index.pkl"
CSV_PATH = DATA_DIR / "all_chunks.csv"

# Global RAG resources
chroma_client = None
collection = None
embed_model = None
bm25 = None
all_docs = []

# Global MCP Client resources
mcp_tools = []
mcp_client = None
compiled_agent = None
exit_stack = AsyncExitStack()


def init_rag_resources():
    global chroma_client, collection, embed_model, bm25, all_docs
    if not (BM25_PATH.exists() and CSV_PATH.exists() and CHROMA_DB_PATH.exists()):
        print("[DEBUG] RAG files missing, skipping RAG init.")
        return

    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    collection = chroma_client.get_collection("hsu_rules")
    embed_model = SentenceTransformer("BAAI/bge-m3", trust_remote_code=True)

    with open(BM25_PATH, "rb") as f:
        bm25 = pickle.load(f)

    df = pd.read_csv(CSV_PATH)
    for i, row in df.iterrows():
        title = str(row.get("title", "")).strip()
        content = str(row.get("content", "")).strip()
        source = str(row.get("source", "")).strip()
        if not content or content == "nan":
            continue
        all_docs.append({"title": title, "content": content, "source": source})


# RAG Search Implementation
def embed_query(query: str):
    if not embed_model:
        return []
    embedding = embed_model.encode(query, normalize_embeddings=True)
    return embedding.tolist()


def hybrid_search(query: str, top_k: int = 5):
    if not collection or not bm25:
        return []

    q_emb = embed_query(query)
    results = collection.query(query_embeddings=[q_emb], n_results=top_k)
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    vector_results = []
    for d, m, dist in zip(docs, metas, distances):
        vector_results.append(
            {
                "score": round(1 - dist, 4),
                "content": d,
                "title": m.get("parent_title"),
                "source": m.get("source"),
            }
        )

    query_tokens = word_tokenize(query.lower())
    scores = bm25.get_scores(query_tokens)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    bm25_results = []
    for idx, score in ranked[:top_k]:
        if score <= 0:
            continue
        chunk = all_docs[idx]
        full_text = f"Title: {chunk['title']}\n\nContent:\n{chunk['content']}".strip()
        bm25_results.append(
            {
                "score": round(score, 4),
                "content": full_text,
                "title": chunk["title"],
                "source": chunk["source"],
            }
        )

    merged = {}
    for r in vector_results + bm25_results:
        merged[r["content"]] = r
    final_results = list(merged.values())
    return final_results[:top_k]


# Langchain Tool for RAG
@tool
def search_university_handbook(query: str) -> str:
    """
    Search the university handbook for general rules, regulations, departments, and general info.
    Use this to answer student questions about how the university works, policies, etc.
    """
    results = hybrid_search(query, top_k=5)
    if not results:
        return "Không tìm thấy thông tin nào trong sổ tay trường học."
    context_parts = []
    for i, doc in enumerate(results):
        title = doc.get("title", "Không rõ tiêu đề")
        content = doc.get("content", "")
        context_parts.append(f"Tài liệu {i + 1} - {title}:\n{content}")
    return "\n\n".join(context_parts)


async def init_mcp_client():
    global mcp_tools, mcp_client
    if mcp_tools:
        return

    import sys
    mcp_script = str(BASE_DIR / "mcp_stdio.py")
    server_params = StdioServerParameters(command=sys.executable, args=[mcp_script], env=None)

    read_stream, write_stream = await exit_stack.enter_async_context(
        stdio_client(server_params)
    )
    mcp_client = await exit_stack.enter_async_context(
        ClientSession(read_stream, write_stream)
    )
    await mcp_client.initialize()

    toolkit = MCPToolkit(session=mcp_client)
    await toolkit.initialize()
    mcp_tools = toolkit.get_tools()

    # ---------------------------------------------------------
    # COMPILE THE GRAPH GLOBALLY ONCE
    # ---------------------------------------------------------
    global compiled_agent

    llm = ChatOllama(model="qwen3:8b", temperature=0.2)
    all_tools = [search_university_handbook] + mcp_tools

    workflow = StateGraph(MessagesState)
    llm_with_tools = llm.bind_tools(all_tools)

    async def call_model(state: MessagesState):
        response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    async def extra_custom_node(state: MessagesState):
        # Placeholder for future custom logic (translation, logging, guardrails, etc)
        print("[DEBUG] Running extra custom node...")
        return {"messages": []}

    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools=all_tools))
    workflow.add_node("extra_custom_node", extra_custom_node)

    # Add edges
    workflow.add_edge(START, "agent")

    def should_continue(state: MessagesState):
        last_message = state["messages"][-1]

        # If Ollama decided to use a tool, 'tool_calls' will be a list of the requested tools
        if last_message.tool_calls:
            print(f"\n[ROUTER] 🛠️ Ollama requested a tool: {last_message.tool_calls}")
            print("[ROUTER] 🔀 Routing to -> 'tools' node\n")
            return "tools"

        print("\n[ROUTER] 🗣️ Ollama is giving a final answer.")
        print("[ROUTER] 🔀 Routing to -> 'extra_custom_node'\n")
        return "extra_custom_node"

    workflow.add_conditional_edges(
        "agent", should_continue, ["tools", "extra_custom_node"]
    )
    workflow.add_edge("tools", "agent")
    workflow.add_edge("extra_custom_node", END)

    compiled_agent = workflow.compile()
    print(f"[DEBUG] Loaded {len(mcp_tools)} MCP tools & Compiled Agent Globally!")


async def close_mcp_client():
    await exit_stack.aclose()


# Initialize RAG on import
init_rag_resources()


async def generate_chatbot_response(
    user_message: str, chat_history: list = None, token: str = None
) -> str:
    """
    Generates a response asynchronously using LangGraph ReAct agent.
    """
    if chat_history is None:
        chat_history = []

    # Ensure the global agent is initialized
    if not compiled_agent:
        await init_mcp_client()

    # Convert dictionary history to Langchain message objects
    messages = []

    # Inject System Prompt with instructions and Token
    system_prompt = (
        "Bạn là trợ lý ảo chuyên nghiệp và lịch sự của trường đại học. "
        "Bạn có công cụ 'search_university_handbook' để tra cứu thông tin chung sổ tay sinh viên. "
        "Bạn có các công cụ 'get_my_grades', 'get_my_current_classes', 'get_my_gpa' để xem điểm, lịch học và GPA của sinh viên. "
        "Bạn có công cụ 'get_professor_info' để tra cứu thông tin giảng viên và 'search_classes_by_subject' để tìm lớp học. "
        "Bạn cũng có thể dùng 'web_search' để tìm kiếm thông tin trên internet. "
        "TUYỆT ĐỐI không bịa đặt thông tin. Nếu không tìm thấy, hãy nói 'Tôi không tìm thấy thông tin này.' "
        "TRẢ LỜI NGẮN GỌN VÀ MẠCH LẠC BẰNG TIẾNG VIỆT.\n\n"
        f"IMPORTANT: The current user's JWT token is: '{token}'. "
        "When you call any MCP tools like 'get_my_grades', 'get_my_current_classes', 'get_my_gpa', "
        "'get_professor_info', 'search_classes_by_subject', or 'web_search', you MUST pass this token exactly as provided in the 'token' argument."
    )
    messages.append(SystemMessage(content=system_prompt))

    for msg in chat_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=user_message))

    # Invoke the pre-compiled global agent graph
    try:
        response_state = await compiled_agent.ainvoke({"messages": messages})
        final_message = response_state["messages"][-1]
        return final_message.content
    except Exception as e:
        print(f"[DEBUG] Error running LangGraph: {e}")
        return f"Xin lỗi, hệ thống đang gặp sự cố: {e}"
