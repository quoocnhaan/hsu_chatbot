from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from app.database import engine, Base
from app.routers import auth, chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Automatically create tables in MySQL (if they don't exist yet) asynchronously
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up and close connection pools on application shutdown
    await engine.dispose()

app = FastAPI(
    title="FastAPI MySQL Chatbot Backend (Async)",
    description="An asynchronous FastAPI chatbot service integrating MySQL database persistence, JWT authentication, and modular chatbot responses.",
    version="1.0.0",
    lifespan=lifespan
)

# Whitelist specific origins for decoupled frontend setups (e.g., VS Code Live Server on port 5500)
# Note: Wildcard "*" cannot be used when allow_credentials=True.
origins = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include sub-routers
app.include_router(auth.router)
app.include_router(chat.router)

# Mount the static files directory (supports combined server hosting)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    """
    Serves the static index.html file for the frontend UI.
    """
    return FileResponse("static/index.html")