from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    program: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(80))
    year: Mapped[int] = mapped_column(Integer)
    semester: Mapped[int] = mapped_column(Integer)
    portal_connected: Mapped[bool] = mapped_column(Boolean, default=False)
