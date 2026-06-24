import json
import jwt
import os
import asyncio
# from mcp.server import Server
# import mcp.types as types
from mcp.server.fastmcp import FastMCP
from app.database import AsyncSessionLocal
from app.models import User
from app.config import settings
from tavily import AsyncTavilyClient
from sqlalchemy.future import select

from app.services import student_service, general_service

# mcp = Server("hsu_chatbot_mcp")
mcp = FastMCP("hsu_chatbot_mcp")

os.environ["TAVILY_API_KEY"] = "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"
tavily_client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])

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

# @mcp.list_tools()
# async def handle_list_tools() -> list[types.Tool]:
#     return [
#         types.Tool(
#             name="get_my_grades",
#             description="Get the grades of the currently authenticated student.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "token": {"type": "string", "description": "JWT access token of the user"}
#                 },
#                 "required": ["token"]
#             }
#         ),
#         types.Tool(
#             name="get_my_current_classes",
#             description="Get the current classes of the authenticated student.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "token": {"type": "string", "description": "JWT access token of the user"}
#                 },
#                 "required": ["token"]
#             }
#         ),
#         types.Tool(
#             name="admin_query",
#             description="Admin only tool to query database schemas or other user information.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "token": {"type": "string", "description": "JWT access token of the admin"},
#                     "query_type": {"type": "string", "description": "Type of query: 'schema' or 'all_students'"}
#                 },
#                 "required": ["token", "query_type"]
#             }
#         ),
#         types.Tool(
#             name="get_professor_info",
#             description="Get information about a professor (like email, department) or find out which professor teaches a specific subject.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "token": {"type": "string", "description": "JWT access token of the user"},
#                     "professor_name": {"type": "string", "description": "Name of the professor to search for (optional)"},
#                     "subject_name": {"type": "string", "description": "Name of the subject to find the professor for (optional)"}
#                 },
#                 "required": ["token"]
#             }
#         ),
#         types.Tool(
#             name="get_my_gpa",
#             description="Get the cumulative GPA and total earned credits of the authenticated student.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "token": {"type": "string", "description": "JWT access token of the user"}
#                 },
#                 "required": ["token"]
#             }
#         ),
#         types.Tool(
#             name="search_classes_by_subject",
#             description="Search for available classes by subject name.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "token": {"type": "string", "description": "JWT access token of the user"},
#                     "subject_name": {"type": "string", "description": "Name of the subject to search classes for"}
#                 },
#                 "required": ["token", "subject_name"]
#             }
#         ),
#         types.Tool(
#             name="web_search",
#             description="Retrieves AI-optimized search snippets from Tavily for a list of queries.",
#             inputSchema={
#                 "type": "object",
#                 "properties": {
#                     "queries": {
#                         "type": "array",
#                         "items": {"type": "string"},
#                         "description": "A list of search queries"
#                     },
#                     "k_per_query": {
#                         "type": "integer",
#                         "description": "Number of results to retrieve per query",
#                         "default": 5
#                     }
#                 },
#                 "required": ["queries"]
#             }
#         )
#     ]

# @mcp.call_tool()
# async def handle_call_tool(
#     name: str, arguments: dict | None
# ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
#     if not arguments:
#         arguments = {}
# 
#     if name == "web_search":
#         queries = arguments.get("queries", [])
#         k_per_query = arguments.get("k_per_query", 5)
#         
#         all_docs = []
#         seen_content = set()
# 
#         async def fetch_tavily(q):
#             try:
#                 response = await tavily_client.search(
#                     query=q, 
#                     max_results=k_per_query, 
#                     search_depth="basic" 
#                 )
#                 return response
#             except Exception as e:
#                 print(f"⚠️ Tavily failed for query '{q}': {e}")
#                 return None
# 
#         tasks = [fetch_tavily(q) for q in queries]
#         results = await asyncio.gather(*tasks)
#         
#         for res in results:
#             if not res or "results" not in res:
#                 continue
#                 
#             for item in res["results"]:
#                 title = item.get("title", "")
#                 content = item.get("content", "")
#                 url = item.get("url", "")
#                 
#                 formatted_content = f"Tiêu đề: {title}\nNội dung: {content}"
#                 
#                 if formatted_content not in seen_content:
#                     seen_content.add(formatted_content)
#                     all_docs.append({
#                         "content": formatted_content,
#                         "url": url
#                     })
#         return [types.TextContent(type="text", text=json.dumps(all_docs, indent=2, ensure_ascii=False))]
# 
#     requires_token = name in [
#         "get_my_grades", 
#         "get_my_current_classes", 
#         "get_my_gpa",
#         "search_classes_by_subject",
#         "admin_query", 
#         "get_professor_info"
#     ]
# 
#     if requires_token:
#         if "token" not in arguments:
#             return [types.TextContent(type="text", text="Error: Missing JWT token")]
# 
#         token = arguments["token"]
#         
#         async with AsyncSessionLocal() as db:
#             try:
#                 user = await get_current_user_from_token(token, db)
#             except Exception as e:
#                 return [types.TextContent(type="text", text=f"Authentication Error: {str(e)}")]
# 
#             try:
#                 if name == "get_my_grades":
#                     if user.role != "student":
#                         return [types.TextContent(type="text", text="Error: This tool is only for students.")]
#                     grades_info = await student_service.get_student_grades(user.id, db)
#                     return [types.TextContent(type="text", text=json.dumps(grades_info, indent=2, ensure_ascii=False))]
# 
#                 elif name == "get_my_current_classes":
#                     if user.role != "student":
#                         return [types.TextContent(type="text", text="Error: This tool is only for students.")]
#                     classes_info = await student_service.get_student_classes(user.id, db)
#                     return [types.TextContent(type="text", text=json.dumps(classes_info, indent=2, ensure_ascii=False))]
#                     
#                 elif name == "get_my_gpa":
#                     if user.role != "student":
#                         return [types.TextContent(type="text", text="Error: This tool is only for students.")]
#                     gpa_info = await student_service.get_student_gpa(user.id, db)
#                     return [types.TextContent(type="text", text=json.dumps(gpa_info, indent=2, ensure_ascii=False))]
#                     
#                 elif name == "search_classes_by_subject":
#                     subject_name = arguments.get("subject_name", "")
#                     classes_info = await student_service.search_classes_by_subject(subject_name, db)
#                     if not classes_info:
#                         return [types.TextContent(type="text", text=f"No classes found for subject matching '{subject_name}'")]
#                     return [types.TextContent(type="text", text=json.dumps(classes_info, indent=2, ensure_ascii=False))]
# 
#                 elif name == "get_professor_info":
#                     prof_name = arguments.get("professor_name")
#                     subj_name = arguments.get("subject_name")
#                     prof_info = await general_service.search_professor(prof_name, subj_name, db)
#                     if not prof_info:
#                         return [types.TextContent(type="text", text="No professor found matching the criteria.")]
#                     return [types.TextContent(type="text", text=json.dumps(prof_info, indent=2, ensure_ascii=False))]
# 
#                 elif name == "admin_query":
#                     if user.role != "admin":
#                         return [types.TextContent(type="text", text="Error: Unauthorized. Admin access required.")]
#                     
#                     query_type = arguments.get("query_type")
#                     if query_type == "schema":
#                         schema_dict = await general_service.get_database_schema(db)
#                         return [types.TextContent(type="text", text=json.dumps(schema_dict, indent=2))]
#                     elif query_type == "all_students":
#                         student_list = await general_service.get_all_students(db)
#                         return [types.TextContent(type="text", text=json.dumps(student_list, indent=2, ensure_ascii=False))]
#                     else:
#                         return [types.TextContent(type="text", text="Error: Unknown query_type")]
#                         
#             except ValueError as ve:
#                 return [types.TextContent(type="text", text=f"Error: {str(ve)}")]
# 
#     raise ValueError(f"Unknown tool: {name}")

# =====================================================================
# FASTMCP IMPLEMENTATION
# =====================================================================

@mcp.tool()
async def get_my_grades(token: str) -> str:
    """Get the grades of the currently authenticated student.

    Args:
        token: JWT access token of the user
    """
    async with AsyncSessionLocal() as db:
        try:
            user = await get_current_user_from_token(token, db)
        except Exception as e:
            return f"Authentication Error: {str(e)}"

        if user.role != "student":
            return "Error: This tool is only for students."
        
        try:
            grades_info = await student_service.get_student_grades(user.id, db)
            return json.dumps(grades_info, indent=2, ensure_ascii=False)
        except ValueError as ve:
            return f"Error: {str(ve)}"


@mcp.tool()
async def get_my_current_classes(token: str) -> str:
    """Get the current classes of the authenticated student.

    Args:
        token: JWT access token of the user
    """
    async with AsyncSessionLocal() as db:
        try:
            user = await get_current_user_from_token(token, db)
        except Exception as e:
            return f"Authentication Error: {str(e)}"

        if user.role != "student":
            return "Error: This tool is only for students."

        try:
            classes_info = await student_service.get_student_classes(user.id, db)
            return json.dumps(classes_info, indent=2, ensure_ascii=False)
        except ValueError as ve:
            return f"Error: {str(ve)}"


@mcp.tool()
async def get_my_gpa(token: str) -> str:
    """Get the cumulative GPA and total earned credits of the authenticated student.

    Args:
        token: JWT access token of the user
    """
    async with AsyncSessionLocal() as db:
        try:
            user = await get_current_user_from_token(token, db)
        except Exception as e:
            return f"Authentication Error: {str(e)}"

        if user.role != "student":
            return "Error: This tool is only for students."

        try:
            gpa_info = await student_service.get_student_gpa(user.id, db)
            return json.dumps(gpa_info, indent=2, ensure_ascii=False)
        except ValueError as ve:
            return f"Error: {str(ve)}"


@mcp.tool()
async def search_classes_by_subject(token: str, subject_name: str) -> str:
    """Search for available classes by subject name.

    Args:
        token: JWT access token of the user
        subject_name: Name of the subject to search classes for
    """
    async with AsyncSessionLocal() as db:
        try:
            user = await get_current_user_from_token(token, db)
        except Exception as e:
            return f"Authentication Error: {str(e)}"

        try:
            classes_info = await student_service.search_classes_by_subject(subject_name, db)
            if not classes_info:
                return f"No classes found for subject matching '{subject_name}'"
            return json.dumps(classes_info, indent=2, ensure_ascii=False)
        except ValueError as ve:
            return f"Error: {str(ve)}"


@mcp.tool()
async def get_professor_info(token: str, professor_name: str = None, subject_name: str = None) -> str:
    """Get information about a professor (like email, department) or find out which professor teaches a specific subject.

    Args:
        token: JWT access token of the user
        professor_name: Name of the professor to search for (optional)
        subject_name: Name of the subject to find the professor for (optional)
    """
    async with AsyncSessionLocal() as db:
        try:
            user = await get_current_user_from_token(token, db)
        except Exception as e:
            return f"Authentication Error: {str(e)}"

        try:
            prof_info = await general_service.search_professor(professor_name, subject_name, db)
            if not prof_info:
                return "No professor found matching the criteria."
            return json.dumps(prof_info, indent=2, ensure_ascii=False)
        except ValueError as ve:
            return f"Error: {str(ve)}"


@mcp.tool()
async def admin_query(token: str, query_type: str) -> str:
    """Admin only tool to query database schemas or other user information.

    Args:
        token: JWT access token of the admin
        query_type: Type of query: 'schema' or 'all_students'
    """
    async with AsyncSessionLocal() as db:
        try:
            user = await get_current_user_from_token(token, db)
        except Exception as e:
            return f"Authentication Error: {str(e)}"

        if user.role != "admin":
            return "Error: Unauthorized. Admin access required."

        try:
            if query_type == "schema":
                schema_dict = await general_service.get_database_schema(db)
                return json.dumps(schema_dict, indent=2)
            elif query_type == "all_students":
                student_list = await general_service.get_all_students(db)
                return json.dumps(student_list, indent=2, ensure_ascii=False)
            else:
                return "Error: Unknown query_type"
        except ValueError as ve:
            return f"Error: {str(ve)}"


@mcp.tool()
async def web_search(queries: list[str], k_per_query: int = 5) -> str:
    """Retrieves AI-optimized search snippets from Tavily for a list of queries.

    Args:
        queries: A list of search queries
        k_per_query: Number of results to retrieve per query
    """
    all_docs = []
    seen_content = set()

    async def fetch_tavily(q):
        try:
            response = await tavily_client.search(
                query=q, 
                max_results=k_per_query, 
                search_depth="basic" 
            )
            return response
        except Exception as e:
            print(f"⚠️ Tavily failed for query '{q}': {e}")
            return None

    tasks = [fetch_tavily(q) for q in queries]
    results = await asyncio.gather(*tasks)
    
    for res in results:
        if not res or "results" not in res:
            continue
            
        for item in res["results"]:
            title = item.get("title", "")
            content = item.get("content", "")
            url = item.get("url", "")
            
            formatted_content = f"Tiêu đề: {title}\nNội dung: {content}"
            
            if formatted_content not in seen_content:
                seen_content.add(formatted_content)
                all_docs.append({
                    "content": formatted_content,
                    "url": url
                })
    return json.dumps(all_docs, indent=2, ensure_ascii=False)

