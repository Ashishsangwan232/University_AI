from sqlalchemy.orm import Session

from app.tools.campus import get_announcements_tool, get_services_tool, get_timetable_tool


def timetable_summary(student_id: str, db: Session, day: str | None = None) -> dict:
    return get_timetable_tool(student_id, db, day)


def announcements_summary(db: Session, limit: int = 10) -> dict:
    return get_announcements_tool(db, limit)


def services_summary(db: Session, query: str | None = None) -> dict:
    return get_services_tool(db, query)
