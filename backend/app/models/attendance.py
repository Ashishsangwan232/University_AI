from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AttendanceSubject(Base):
    __tablename__ = "attendance_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    short: Mapped[str] = mapped_column(String(20))
    attended: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    teacher: Mapped[str] = mapped_column(String(120))
