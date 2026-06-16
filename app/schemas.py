from datetime import datetime
from pydantic import BaseModel, Field

# User Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: str = Field(..., max_length=100, description="User email address")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Authentication/Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None


# Chat Session Schemas
class ChatSessionResponse(BaseModel):
    id: str
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChatSessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="New title for the chat session")


# Chat Message Schemas
class MessageCreate(BaseModel):
    content: str = Field(..., description="The content of the message to send")
    session_id: str | None = Field(None, description="Optional session ID to continue an existing chat session. If omitted, a new session is created.")

class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
