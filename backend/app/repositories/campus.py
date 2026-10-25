from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.campus import Announcement, CollegeService, TimetableClass


def get_timetable(db: Session, student_id: str, day: str | None = None) -> list[TimetableClass]:
    query = select(TimetableClass).where(TimetableClass.student_id == student_id)
    if day:
        query = query.where(TimetableClass.day.ilike(day))
    query = query.order_by(TimetableClass.day, TimetableClass.time)
    return list(db.scalars(query).all())


def get_announcements(db: Session, limit: int | None = None) -> list[Announcement]:
    query = select(Announcement).order_by(Announcement.id.desc())
    if limit:
        query = query.limit(limit)
    return list(db.scalars(query).all())


def search_services(db: Session, query_text: str | None = None) -> list[CollegeService]:
    query = select(CollegeService).order_by(CollegeService.id)
    services = list(db.scalars(query).all())
    if not query_text:
        return services
    needle = query_text.lower()
    return [
        item for item in services
        if needle in item.name.lower()
        or needle in item.category.lower()
        or needle in item.description.lower()
    ]
