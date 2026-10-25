"""Who the student is, read live from UMS. There is no demo student."""
from __future__ import annotations

from typing import Any

from app.ums.profile import initials, term_number
from app.ums.service import (
    UMSLiveAttendanceUnavailable,
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
        "source": record.get("source") or "UMS (live)",
        "name_source": profile.get("name_source") or None,
    }


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
