from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.student import Student


def get_student(db: Session, student_id: str) -> Student | None:
    return db.scalar(select(Student).where(Student.id == student_id))
