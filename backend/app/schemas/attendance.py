from typing import Any

from pydantic import BaseModel, Field


class AttendanceSubject(BaseModel):
    name: str
    short: str
    attended: int = Field(ge=0)
    total: int = Field(ge=0)
    teacher: str = ""

    @property
    def percentage(self) -> float:
        return round(self.attended / self.total * 100, 1) if self.total else 0.0


class AttendanceResponse(BaseModel):
    overall_percentage: float
    subjects: list[AttendanceSubject]
    source: str = "PostgreSQL demo data (UMS not connected)"
    #: True only when the numbers came from the authenticated UMS browser.
    live: bool = False
    #: UMS state machine value at the time the data was produced.
    state: str | None = None
    source_url: str | None = None
    updated_at: float | None = None


class AttendanceCalculateRequest(BaseModel):
    attended: int = Field(ge=0)
    total: int = Field(ge=0)
    target_percentage: float = Field(gt=0, le=100)


class AttendanceCalculateResponse(BaseModel):
    current_percentage: float
    target_percentage: float
    can_miss: int
    must_attend: int


class UMSUnavailableDetail(BaseModel):
    message: str
    state: str | None = None
    diagnostics: dict[str, Any] = {}
