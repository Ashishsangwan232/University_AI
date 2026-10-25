from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceSubject


def get_subjects(db: Session, student_id: str) -> list[AttendanceSubject]:
    return list(db.scalars(select(AttendanceSubject).where(AttendanceSubject.student_id == student_id)))
