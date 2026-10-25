from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TimetableClass(Base):
    __tablename__ = "timetable_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    day: Mapped[str] = mapped_column(String(12), nullable=False)
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    end: Mapped[str] = mapped_column(String(5), nullable=False)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    room: Mapped[str] = mapped_column(String(80), nullable=False)
    teacher: Mapped[str] = mapped_column(String(120), nullable=False)


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[str] = mapped_column(String(40), nullable=False)
    tag: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    important: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CollegeService(Base):
    __tablename__ = "college_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="Available", nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
