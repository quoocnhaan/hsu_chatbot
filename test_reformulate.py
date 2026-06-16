import asyncio
import ollama

async def main():
    chat_history = [
        {'role': 'user', 'content': 'trưởng khoa ngành công nghệ thông tin'},
        {'role': 'assistant', 'content': 'TS. Lê Đình Phong là Trưởng khoa Công nghệ, chuyên ngành Robotics và Giao tiếp Người – Máy. Nếu bạn cần thông tin về Giám đốc chương trình Công nghệ thông tin, đó là TS. Trang Hồng Sơn.'}
    ]
    user_message = 'thầy sinh năm bao nhiêu vậy? cho tôi email của thầy'
    
    history_text = '\n'.join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
    prompt = f"""Dựa vào lịch sử trò chuyện dưới đây, hãy viết lại câu hỏi cuối cùng của người dùng thành một câu hỏi độc lập, đầy đủ ngữ cảnh để có thể dùng tìm kiếm thông tin độc lập. Chỉ trả về câu hỏi đã được viết lại, tuyệt đối không giải thích hay thêm bất kỳ từ nào khác.
    
Lịch sử:
{history_text}

Câu hỏi hiện tại: {user_message}
Câu hỏi độc lập:"""

    ollama_client = ollama.AsyncClient()
    response = await ollama_client.chat(
        model='qwen3:8b',
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.1, 'num_predict': 100}
    )
    print('REFORMULATED:', response['message']['content'].strip())

asyncio.run(main())
