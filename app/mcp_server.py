import json
import jwt
from mcp.server import Server
import mcp.types as types
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionLocal
from app.models import User, Student, Enrollment, Class, Grade, GradeDetail, Subject, Professor
from app.config import settings

mcp = Server("hsu_chatbot_mcp")

async def get_current_user_from_token(token: str, db):
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "access":
            raise Exception("Invalid token type")
        username = payload.get("sub")
        if not username:
            raise Exception("Invalid token payload")
    except Exception as e:
        raise Exception(f"Token decode error: {e}")
    
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if not user:
        raise Exception("User not found")
    return user

@mcp.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_my_grades",
            description="Get the grades of the currently authenticated student.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {"type": "string", "description": "JWT access token of the user"}
                },
                "required": ["token"]
            }
        ),
        types.Tool(
            name="get_my_current_classes",
            description="Get the current classes of the authenticated student.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {"type": "string", "description": "JWT access token of the user"}
                },
                "required": ["token"]
            }
        ),
        types.Tool(
            name="admin_query",
            description="Admin only tool to query database schemas or other user information.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token": {"type": "string", "description": "JWT access token of the admin"},
                    "query_type": {"type": "string", "description": "Type of query: 'schema' or 'all_students'"}
                },
                "required": ["token", "query_type"]
            }
        )
    ]

@mcp.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if not arguments or "token" not in arguments:
        return [types.TextContent(type="text", text="Error: Missing JWT token")]

    token = arguments["token"]
    
    async with AsyncSessionLocal() as db:
        try:
            user = await get_current_user_from_token(token, db)
        except Exception as e:
            return [types.TextContent(type="text", text=f"Authentication Error: {str(e)}")]

        if name == "get_my_grades":
            if user.role != "student":
                return [types.TextContent(type="text", text="Error: This tool is only for students.")]
            
            # Find student profile
            result = await db.execute(select(Student).where(Student.user_id == user.id))
            student = result.scalars().first()
            if not student:
                return [types.TextContent(type="text", text="Error: Student profile not found for this user. Please contact admin.")]

            # Find enrollments and grades
            stmt = (
                select(Enrollment)
                .where(Enrollment.student_id == student.id)
                .options(
                    selectinload(Enrollment.class_).selectinload(Class.subject),
                    selectinload(Enrollment.grades).selectinload(Grade.details)
                )
            )
            enrollments = (await db.execute(stmt)).scalars().all()
            
            grades_info = []
            for enr in enrollments:
                subject_name = enr.class_.subject.subject_name
                grade_records = enr.grades
                for g in grade_records:
                    details = [{"component": d.component_name, "score": d.score, "weight": d.weight} for d in g.details]
                    grades_info.append({
                        "subject": subject_name,
                        "final_score": g.final_score,
                        "letter_grade": g.letter_grade,
                        "details": details
                    })
            
            return [types.TextContent(type="text", text=json.dumps(grades_info, indent=2, ensure_ascii=False))]

        elif name == "get_my_current_classes":
            if user.role != "student":
                return [types.TextContent(type="text", text="Error: This tool is only for students.")]
            
            # Find student profile
            result = await db.execute(select(Student).where(Student.user_id == user.id))
            student = result.scalars().first()
            if not student:
                return [types.TextContent(type="text", text="Error: Student profile not found for this user.")]

            # Find enrollments
            stmt = (
                select(Enrollment)
                .where(Enrollment.student_id == student.id)
                .options(
                    selectinload(Enrollment.class_).selectinload(Class.subject),
                    selectinload(Enrollment.class_).selectinload(Class.professor)
                )
            )
            enrollments = (await db.execute(stmt)).scalars().all()
            
            classes_info = []
            for enr in enrollments:
                prof_name = enr.class_.professor.full_name if enr.class_.professor else "N/A"
                classes_info.append({
                    "subject_code": enr.class_.subject.subject_code,
                    "subject_name": enr.class_.subject.subject_name,
                    "class_code": enr.class_.code,
                    "room": enr.class_.room,
                    "schedule": enr.class_.schedule,
                    "professor": prof_name
                })
            
            return [types.TextContent(type="text", text=json.dumps(classes_info, indent=2, ensure_ascii=False))]

        elif name == "admin_query":
            if user.role != "admin":
                return [types.TextContent(type="text", text="Error: Unauthorized. Admin access required.")]
            
            query_type = arguments.get("query_type")
            if query_type == "schema":
                return [types.TextContent(type="text", text="Database schema: Tables include users, students, professors, departments, subjects, classes, enrollments, grades, grade_details.")]
            elif query_type == "all_students":
                result = await db.execute(select(Student))
                students = result.scalars().all()
                student_list = [{"student_code": s.student_code, "full_name": s.full_name} for s in students]
                return [types.TextContent(type="text", text=json.dumps(student_list, indent=2, ensure_ascii=False))]
            else:
                return [types.TextContent(type="text", text="Error: Unknown query_type")]
            
        else:
            raise ValueError(f"Unknown tool: {name}")

