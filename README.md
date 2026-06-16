# 🎓 AI RAG Chatbot System for University Counseling

A comprehensive, full-stack AI Chatbot system built with **FastAPI**, **MySQL**, and **Vanilla JS**. This project leverages **Retrieval-Augmented Generation (RAG)** utilizing both Dense Vector Search and Sparse Lexical Search to provide highly accurate, hallucination-free counseling answers based on university data.

![Chatbot Demo](https://via.placeholder.com/800x450.png?text=UI+Screenshot+Goes+Here)

## 🚀 Key Features

* **Hybrid RAG Pipeline:** Combines **ChromaDB** (Dense Vector Retrieval using `BAAI/bge-m3` embeddings) and **BM25** (Sparse Lexical Search using `underthesea` for Vietnamese tokenization) to achieve high-precision document retrieval.
* **Conversational Memory:** Maintains multi-turn contextual awareness by employing an LLM-based query reformulation step. It dynamically resolves coreferences (e.g., pronouns like "thầy", "môn đó") from the chat history before searching the database.
* **Zero Hallucination:** Integrates local LLMs via **Ollama (Qwen)** with strict prompt constraints, restricting the model to answer *strictly* based on retrieved context or conversation history.
* **Secure Double-Token Authentication:** Implements a highly secure JWT authentication system utilizing short-lived Access Tokens (in RAM) and long-lived Refresh Tokens (in HttpOnly cookies) to completely mitigate XSS vulnerabilities while providing a seamless silent-login UX.
* **Persistent Chat History:** Asynchronous MySQL database (via SQLAlchemy Async) to manage users, sessions, and chat messages.

## 🛠️ Technology Stack

**Backend:**
* [FastAPI](https://fastapi.tiangolo.com/) - High performance web framework
* [SQLAlchemy (Async)](https://www.sqlalchemy.org/) - ORM for MySQL
* [JWT (JSON Web Tokens)](https://jwt.io/) - Secure Authentication

**AI & NLP (Retrieval-Augmented Generation):**
* [Ollama](https://ollama.com/) - Local LLM Engine (Running `qwen3:8b` or `qwen2.5`)
* [ChromaDB](https://www.trychroma.com/) - Vector Database
* [SentenceTransformers](https://sbert.net/) - Embedding Model (`BAAI/bge-m3`)
* [rank_bm25](https://pypi.org/project/rank-bm25/) - Lexical Search
* [underthesea](https://github.com/undertheseanlp/underthesea) - Vietnamese NLP Toolkit

**Frontend:**
* Vanilla JavaScript (SPA), HTML5, CSS3

## 📂 Project Structure

```text
├── app/
│   ├── routers/          # API Route handlers (auth, chat)
│   ├── auth.py           # JWT Authentication & Password hashing
│   ├── chatbot.py        # RAG Pipeline, Query Reformulation & Ollama integration
│   ├── config.py         # Environment variables
│   ├── database.py       # Async SQLAlchemy configuration
│   ├── models.py         # MySQL Database Schema
│   └── schemas.py        # Pydantic models for validation
├── chroma_db/            # ChromaDB Vector Store Persistence
├── data/                 # Raw datasets and BM25 index
│   ├── all_chunks.csv
│   └── bm25_index.pkl
├── static/               # Frontend Assets (HTML, CSS, JS)
├── main.py               # FastAPI application entry point
├── requirements.txt      # Python dependencies
└── README.md
```

## ⚙️ Installation & Setup

### 1. Prerequisites
* Python 3.10+
* MySQL Server
* [Ollama](https://ollama.com/) installed and running locally.

### 2. Install Dependencies
Clone the repository and install the required Python packages:

```bash
git clone https://github.com/yourusername/hsu-rag-chatbot.git
cd hsu-rag-chatbot
pip install -r requirements.txt
```

### 3. Database Setup
Create a MySQL database and configure your `.env` file in the root directory:

```env
DATABASE_URL=mysql+aiomysql://username:password@localhost:3306/your_database_name
SECRET_KEY=your_super_secret_jwt_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
```

### 4. Download Local LLM (Ollama)
Ensure Ollama is running, then pull the required model (e.g., Qwen):
```bash
ollama run qwen3:8b
```

### 5. Run the Application
Start the FastAPI server (it will automatically create the database tables on the first run):
```bash
uvicorn main:app --reload
```

The application will be available at:
* Frontend: `http://localhost:8000/`
* API Docs (Swagger): `http://localhost:8000/docs`

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check [issues page](https://github.com/yourusername/hsu-rag-chatbot/issues).

## 📝 License
This project is [MIT](https://choosealicense.com/licenses/mit/) licensed.
