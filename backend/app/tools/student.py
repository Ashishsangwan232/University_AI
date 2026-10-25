"""Who the student is, for the REST API and the Gemini agent.

Same rule as attendance, implemented once here:

    if an authenticated UMS session exists:
        return the real identity read from UMS, or raise an explicit
        unavailable error - never the demo student
    else:
        return the PostgreSQL demo student only when UMS_DEMO_MODE is on,
        clearly labelled as demo

A wrong name is as misleading as a wrong attendance percentage, so this never
quietly substitutes one for the other.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.student import get_student
from app.ums.profile import initials, term_number
from app.ums.service import (
    UMSLiveAttendanceUnavailable,
    ums_is_live,
    ums_status,
    ums_student_profile,
)


def live_student_payload() -> dict[str, Any]:
    """The real student from UMS, or :class:`UMSLiveAttendanceUnavailable`."""
    record = ums_student_profile()
    profile = record.get("profile") or {}

    semester = term_number(profile.get("term"))
    # Backend arithmetic, not a language model's guess: two terms make a year.
    year = ((semester + 1) // 2) if semester else None

    return {
        "id": profile.get("student_id") or "ums-student",
        "name": profile.get("name") or "",
        "program": profile.get("program") or None,
        "department": profile.get("department") or None,
        "year": year,
        "semester": semester,
        "student_id": profile.get("student_id") or None,
        "section": profile.get("section") or None,
        "term": profile.get("term") or None,
        "hostel": profile.get("hostel") or None,
        "room": profile.get("room") or None,
        "portal_connected": True,
        "live": True,
        "source": record.get("source") or "UMS Playwright session",
        "name_source": profile.get("name_source") or None,
    }


def demo_student_payload(student_id: str, db: Session) -> dict[str, Any] | None:
    student = get_student(db, student_id)
    if student is None:
        return None
    return {
        "id": student.id,
        "name": student.name,
        "program": student.program,
        "department": student.department,
        "year": student.year,
        "semester": student.semester,
        "portal_connected": False,
        "live": False,
        "source": "Demo student profile (UMS not connected)",
    }


def get_student_profile(student_id: str, db: Session) -> dict[str, Any]:
    """The single live-vs-demo decision for the student's identity."""
    status = ums_status()
    if ums_is_live(status):
        return live_student_payload()

    if not settings.ums_demo_mode:
        raise UMSLiveAttendanceUnavailable(
            "UMS is not connected and demo mode is disabled, so CampusAI does not know "
            "who you are yet. Click Connect UMS and sign in.",
            status.get("diagnostics", {}),
        )
    demo = demo_student_payload(student_id, db)
    if demo is None:
        raise UMSLiveAttendanceUnavailable(
            "No student record is available: UMS is not connected and the demo student "
            "is missing from the database.",
            status.get("diagnostics", {}),
        )
    return demo


def get_student_profile_tool() -> dict[str, Any]:
    """Live-only identity for the agent. Says so instead of guessing a name."""
    try:
        payload = live_student_payload()
    except UMSLiveAttendanceUnavailable as exc:
        return {
            "available": False,
            "source": "UMS Playwright session",
            "message": str(exc),
            "state": (exc.diagnostics or {}).get("state"),
        }
    return {
        "available": True,
        "source": payload["source"],
        "name": payload["name"],
        "initials": initials(payload["name"]),
        "registration_number": payload["student_id"],
        "program": payload["program"],
        "department": payload["department"],
        "term": payload["term"],
        "semester": payload["semester"],
        "hostel": payload["hostel"],
        "room": payload["room"],
        "read_from": payload["name_source"],
    }
