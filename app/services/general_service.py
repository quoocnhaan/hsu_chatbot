from sqlalchemy import inspect
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models import Student, Professor, Class, Subject

async def get_database_schema(db) -> dict:
    def get_schema(session):
        inspector = inspect(session.bind)
        schema = {}
        for table_name in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            schema[table_name] = columns
        return schema
    
    return await db.run_sync(get_schema)

async def get_all_students(db) -> list[dict]:
    result = await db.execute(select(Student))
    students = result.scalars().all()
    return [{"student_code": s.student_code, "full_name": s.full_name} for s in students]

async def search_professor(prof_name: str | None, subj_name: str | None, db) -> list[dict]:
    professors = []
    if prof_name:
        stmt = (
            select(Professor)
            .where(Professor.full_name.ilike(f"%{prof_name}%"))
            .options(selectinload(Professor.user), selectinload(Professor.department))
        )
        professors = (await db.execute(stmt)).scalars().all()
    elif subj_name:
        stmt = (
            select(Class)
            .join(Subject)
            .where(Subject.subject_name.ilike(f"%{subj_name}%"))
            .options(
                selectinload(Class.professor).selectinload(Professor.user),
                selectinload(Class.professor).selectinload(Professor.department),
                selectinload(Class.subject)
            )
        )
        classes = (await db.execute(stmt)).scalars().all()
        for c in classes:
            if c.professor and c.professor not in professors:
                c.professor._teaches_subject = c.subject.subject_name
                professors.append(c.professor)
    
    prof_info = []
    for p in professors:
        info = {
            "full_name": p.full_name,
            "title": p.title if p.title else "N/A",
            "position": p.position if p.position else "N/A",
            "expertise": p.expertise if p.expertise else "N/A",
            "email": p.user.email if p.user else "N/A",
            "department": p.department.department_name if p.department else "N/A",
        }
        if hasattr(p, '_teaches_subject'):
            info["teaches_subject"] = p._teaches_subject
        prof_info.append(info)
        
    return prof_info
