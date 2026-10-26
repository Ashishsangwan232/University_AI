"""Attendance tools for the chat agent. Live UMS data only - there is no demo data.

All attendance arithmetic stays in :mod:`app.services.attendance`; the LLM never
computes it.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.attendance import calculate
from app.services.schedule import freshness as _freshness
from app.ums.service import (
    UMSLiveAttendanceUnavailable,
    ums_live_attendance,
)

COURSE_CODE = re.compile(r"^\s*([A-Z]{2,5}\s?\d{2,4}[A-Z]?)\s*[:\-]?\s*(.*)$")


def _subject_from_course(item: dict[str, Any]) -> dict[str, Any] | None:
    """Turn one parsed UMS row into a CampusAI subject record."""
    try:
        attended = int(item["attended"])
        total = int(item["delivered"])
    except (KeyError, TypeError, ValueError):
        return None
    if total <= 0 or attended < 0 or attended > total:
        return None

    code = str(item.get("code") or "").strip()
    label = str(item.get("course") or item.get("name") or "").strip()
    name = str(item.get("name") or "").strip() or label

    if not code:
        match = COURSE_CODE.match(label)
        if match:
            code = match.group(1).replace(" ", "")
            name = match.group(2).strip() or label
    else:
        stripped = name
        match = COURSE_CODE.match(name)
        if match and match.group(1).replace(" ", "") == code.replace(" ", ""):
            stripped = match.group(2).strip() or name
        name = stripped

    return {
        "name": name or code or "UMS course",
        "short": (code or "UMS").replace(" ", ""),
        "attended": attended,
        "total": total,
        # Worked out here so a chart never depends on the model's arithmetic.
        "percentage": round(attended / total * 100, 1),
        "teacher": "",
    }


def live_attendance_payload() -> dict[str, Any]:
    """Live UMS attendance in CampusAI's response shape. Raises when unavailable."""
    live = ums_live_attendance()
    subjects = [s for s in (_subject_from_course(c) for c in live.get("courses") or []) if s]
    if not subjects:
        raise UMSLiveAttendanceUnavailable(
            "UMS is connected and authenticated, but no usable course rows were parsed from the "
            "attendance table.",
            live.get("diagnostics", {}),
        )

    aggregate = live.get("aggregate") or {}
    pct = aggregate.get("percentage")
    if pct in (None, ""):
        attended = sum(s["attended"] for s in subjects)
        total = sum(s["total"] for s in subjects)
        pct = round(attended / total * 100, 1) if total else 0.0

    return {
        "overall_percentage": float(str(pct).replace("%", "").strip()),
        # Set when UMS's overall figure differs from attended/delivered -
        # usually because UMS counts duty leave. Both are real; say which is which.
        "counted_percentage": aggregate.get("counted_percentage"),
        "note": aggregate.get("note"),
        "subjects": subjects,
        "source": "UMS Playwright session (live)",
        "live": True,
        "state": live.get("state"),
        "source_url": live.get("source_url"),
        "updated_at": live.get("updated_at"),
        # How old this reading is. CampusAI caches it, so a second question in
        # the same few minutes reuses it instead of re-opening UMS - and the
        # model says "as of 4 minutes ago" rather than implying a fresh look.
        **_freshness(live.get("updated_at")),
    }


def get_ums_attendance() -> dict[str, Any]:
    """Live attendance for the agent. Reports unavailability instead of guessing."""
    try:
        return {"available": True, **live_attendance_payload()}
    except UMSLiveAttendanceUnavailable as exc:
        return {
            "available": False,
            "source": "UMS Playwright session",
            "message": str(exc),
            "state": (exc.diagnostics or {}).get("state"),
        }


def get_attendance_detail() -> dict[str, Any]:
    """Class-by-class attendance. Live-only; reports unavailability honestly."""
    from app.ums.service import ums_playwright

    try:
        live = ums_playwright.attendance_detail()
    except UMSLiveAttendanceUnavailable as exc:
        return {"available": False, "message": str(exc),
                "state": (exc.diagnostics or {}).get("state")}
    return {
        "available": True,
        "live": True,
        "source": live["source"],
        **_freshness(live.get("updated_at")),
        "courses": [
            {
                "code": course["code"],
                "recorded": course["recorded"],
                "present": course["present"],
                "absent": course["absent"],
                "missed_classes": [
                    {k: e[k] for k in ("date", "time", "type", "reason")}
                    for e in course["entries"] if e["status"] == "absent"
                ],
            }
            for course in live["courses"].values()
        ],
    }


def get_ums_diagnostics() -> dict[str, Any]:
    from app.ums.service import ums_diagnostics

    return ums_diagnostics()


def calculate_attendance(student_id: str, attended: int, total: int, target_percentage: float) -> dict[str, Any]:
    # student_id is accepted so every agent tool has the same future auth shape.
    return calculate(attended, total, target_percentage)
