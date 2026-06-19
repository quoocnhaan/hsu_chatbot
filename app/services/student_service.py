from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models import Student, Enrollment, Class, Grade, GradeDetail, Subject

async def get_student_grades(user_id: int, db) -> list[dict]:
    result = await db.execute(select(Student).where(Student.user_id == user_id))
    student = result.scalars().first()
    if not student:
        raise ValueError("Student profile not found for this user. Please contact admin.")

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
    
    return grades_info

async def get_student_classes(user_id: int, db) -> list[dict]:
    result = await db.execute(select(Student).where(Student.user_id == user_id))
    student = result.scalars().first()
    if not student:
        raise ValueError("Student profile not found for this user.")

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
    
    return classes_info

async def get_student_gpa(user_id: int, db) -> dict:
    result = await db.execute(select(Student).where(Student.user_id == user_id))
    student = result.scalars().first()
    if not student:
        raise ValueError("Student profile not found for this user.")

    stmt = (
        select(Enrollment)
        .where(Enrollment.student_id == student.id)
        .options(
            selectinload(Enrollment.class_).selectinload(Class.subject),
            selectinload(Enrollment.grades)
        )
    )
    enrollments = (await db.execute(stmt)).scalars().all()
    
    total_credits = 0
    total_points = 0.0
    
    for enr in enrollments:
        if not enr.grades:
            continue
            
        grade_record = next((g for g in enr.grades if g.final_score is not None), None)
        if grade_record:
            credits = enr.class_.subject.credits
            score = grade_record.final_score
            total_credits += credits
            total_points += score * credits
            
    if total_credits == 0:
        return {"gpa": 0.0, "total_credits": 0, "message": "No graded classes found."}
        
    gpa = round(total_points / total_credits, 2)
    return {"gpa": gpa, "total_credits": total_credits, "scale": "10.0"}

async def search_classes_by_subject(subject_name: str, db) -> list[dict]:
    stmt = (
        select(Class)
        .join(Subject)
        .where(Subject.subject_name.ilike(f"%{subject_name}%"))
        .options(
            selectinload(Class.subject),
            selectinload(Class.professor),
            selectinload(Class.semester)
        )
    )
    classes = (await db.execute(stmt)).scalars().all()
    
    result = []
    for c in classes:
        prof_name = c.professor.full_name if c.professor else "N/A"
        semester_name = c.semester.semester_name if c.semester else "N/A"
        result.append({
            "subject_code": c.subject.subject_code,
            "subject_name": c.subject.subject_name,
            "class_code": c.code,
            "room": c.room,
            "schedule": c.schedule,
            "professor": prof_name,
            "semester": semester_name
        })
    return result
