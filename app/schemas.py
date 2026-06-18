from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field

# User Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: str = Field(..., max_length=100, description="User email address")
    role: str = Field("student", description="User role: student or admin")

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


# University Schemas
class DepartmentResponse(BaseModel):
    id: int
    department_name: str

    class Config:
        from_attributes = True

class StudentResponse(BaseModel):
    id: int
    user_id: int
    student_code: str
    full_name: str
    major: Optional[str] = None

    class Config:
        from_attributes = True

class ProfessorResponse(BaseModel):
    id: int
    user_id: int
    department_id: Optional[int] = None
    professor_code: str
    full_name: str

    class Config:
        from_attributes = True

class SemesterResponse(BaseModel):
    id: int
    semester_name: str
    start_date: date
    end_date: date

    class Config:
        from_attributes = True

class SubjectResponse(BaseModel):
    id: int
    subject_code: str
    subject_name: str
    credits: int
    department_id: Optional[int] = None

    class Config:
        from_attributes = True

class ClassResponse(BaseModel):
    id: int
    code: str
    subject_id: int
    professor_id: Optional[int] = None
    semester_id: int
    room: Optional[str] = None
    schedule: Optional[str] = None

    class Config:
        from_attributes = True

class EnrollmentResponse(BaseModel):
    id: int
    student_id: int
    class_id: int

    class Config:
        from_attributes = True

class GradeDetailResponse(BaseModel):
    grade_detail_id: int
    grade_id: int
    component_name: str
    score: float
    weight: float

    class Config:
        from_attributes = True

class GradeResponse(BaseModel):
    id: int
    enrollment_id: int
    final_score: Optional[float] = None
    letter_grade: Optional[str] = None
    details: List[GradeDetailResponse] = []

    class Config:
        from_attributes = True

# Composite Responses for MCP
class StudentClassInfo(BaseModel):
    class_info: ClassResponse
    subject: SubjectResponse
    professor: Optional[ProfessorResponse] = None

class StudentGradeInfo(BaseModel):
    class_info: ClassResponse
    subject: SubjectResponse
    grade: GradeResponse
