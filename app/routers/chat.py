import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.database import get_db
from app.models import ChatSession, ChatMessage, User
from app.schemas import MessageCreate, MessageResponse, ChatSessionResponse, ChatSessionUpdate
from app.auth import get_current_user, oauth2_scheme
from app.chatbot import generate_chatbot_response

router = APIRouter(prefix="/api/chat", tags=["Chat"])

@router.post("/message", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    message_in: MessageCreate,
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):

    session_id = message_in.session_id
    
    if session_id:
        stmt = select(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        result = await db.execute(stmt)
        session = result.scalars().first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found or access denied"
            )
    else:
        session_id = uuid.uuid4().hex
        
        title = message_in.content[:40] + ("..." if len(message_in.content) > 40 else "")
        if not title:
            title = "New Chat"
            
        session = ChatSession(
            id=session_id,
            user_id=current_user.id,
            title=title
        )
        db.add(session)
        
    # Lấy lịch sử trò chuyện (tối đa 6 tin nhắn gần nhất)
    stmt_history = select(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.id.desc()).limit(6)
    result_history = await db.execute(stmt_history)
    history_records = result_history.scalars().all()
    history_records.reverse()  # Sắp xếp theo thứ tự thời gian cũ -> mới
    
    chat_history = [{"role": m.role, "content": m.content} for m in history_records]

    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=message_in.content
    )
    db.add(user_msg)
    
    bot_response_text = await generate_chatbot_response(message_in.content, chat_history, token)
    
    bot_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=bot_response_text
    )
    db.add(bot_msg)
    
    session.updated_at = func.now()
    
    await db.commit()
    await db.refresh(bot_msg)
    
    return bot_msg


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns a list of all chat sessions for the authenticated user,
    sorted by last activity (updated_at) descending.
    """
    stmt = select(ChatSession).filter(ChatSession.user_id == current_user.id).order_by(ChatSession.updated_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/history", response_model=List[MessageResponse])
async def get_chat_history(
    session_id: str = Query(..., description="The session ID to retrieve history for"),
    limit: int = Query(50, ge=1, le=100, description="Max messages to retrieve"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves chat history for a specific session.
    Verifies that the session belongs to the authenticated user.
    """
    # Verify ownership
    stmt_session = select(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    result_session = await db.execute(stmt_session)
    session = result_session.scalars().first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or access denied"
        )
        
    stmt_msg = select(ChatMessage).filter(ChatMessage.session_id == session_id)
    stmt_msg = stmt_msg.order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit)
    
    result_msg = await db.execute(stmt_msg)
    return result_msg.scalars().all()


@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
async def rename_chat_session(
    session_id: str,
    session_update: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Renames the title of an active chat session.
    """
    stmt = select(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    result = await db.execute(stmt)
    session = result.scalars().first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or access denied"
        )
        
    session.title = session_update.title
    session.updated_at = func.now()
    
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Deletes a chat session and cascade-deletes all its messages.
    """
    stmt = select(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    result = await db.execute(stmt)
    session = result.scalars().first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or access denied"
        )
        
    await db.delete(session)
    await db.commit()
    return {"message": "Chat session and message history deleted successfully"}
