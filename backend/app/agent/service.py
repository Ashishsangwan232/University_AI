"""Keyword-based replies used only when no language model can be reached.

It calls the same tools as the models, so it reads the same live UMS data and
the same stored university information - it just can't write fluent sentences.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.knowledge import search as search_university_info
from app.tools.attendance import calculate_attendance, get_ums_attendance
from app.tools.campus import get_announcements_tool, get_timetable_tool
from app.ums.state import UMSLiveAttendanceUnavailable

#: Greetings score up to ~0.59 against some sections; real questions ~0.65+.
OFFLINE_MIN_SIMILARITY = 0.6


@dataclass
class AgentResult:
    answer: str
    intent: str
    tool_used: str | None
    source: str
    action: str | None = None


def _attendance_answer(text: str) -> AgentResult:
    data = get_ums_attendance()
    if not data.get("available"):
        return AgentResult(data.get("message", "Live attendance is unavailable."),
                           "attendance", "get_attendance", "UMS (not connected)")
    subjects = data["subjects"]
    if not subjects:
        return AgentResult("No attendance records are available yet.",
                           "attendance", "get_attendance", "UMS (live)")

    attended = sum(s["attended"] for s in subjects)
    total = sum(s["total"] for s in subjects)
    answer = f"Your overall attendance is {data['overall_percentage']:.1f}% ({attended}/{total} classes)."
    lower = text.lower()
    if "miss" in lower or "skip" in lower or "75" in lower:
        margins = [
            (calculate_attendance("", s["attended"], s["total"], 75)["can_miss"], s["short"])
            for s in subjects
        ]
        can_miss = min(m for m, _ in margins)
        tightest = ", ".join(short for m, short in margins if m == can_miss)
        answer += (f" At a 75% target you can miss up to {can_miss} more class(es) before "
                   f"the tightest subject reaches the limit ({tightest}).")
    return AgentResult(answer, "attendance", "get_attendance + calculate_attendance", "UMS (live)")


def _timetable_answer(text: str) -> AgentResult:
    classes = get_timetable_tool()["classes"]
    if not classes:
        return AgentResult("I couldn't find any timetable entries.", "timetable", "get_timetable", "UMS (live)")
    lower = text.lower()
    day = next((d for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
                if d.lower() in lower), None)
    items = [c for c in classes if day and c["day"].lower() == day.lower()] or classes[:6]
    details = "; ".join(f"{c['day']} {c['time']}-{c['end']} {c['subject']} in {c['room']}" for c in items)
    return AgentResult(f"Classes: {details}.", "timetable", "get_timetable", "UMS (live)")


def _announcement_answer() -> AgentResult:
    items = get_announcements_tool(limit=3)["announcements"]
    if not items:
        return AgentResult("There are no announcements right now.", "announcements", "get_announcements", "UMS (live)")
    details = " ".join(f"{x['title']} ({x['when']})." for x in items)
    return AgentResult(f"Latest announcements: {details}", "announcements", "get_announcements", "UMS (live)")


def _info_answer(text: str) -> AgentResult | None:
    # Every message lands here, small talk included, so demand a clear match.
    found = search_university_info(text, limit=1, min_similarity=OFFLINE_MIN_SIMILARITY)
    if not found.get("results"):
        return None
    top = found["results"][0]
    return AgentResult(f"{top['section']}:\n{top['text']}", "university_info",
                       "get_university_info", "Stored university information")


def answer(text: str, student_id: str, db: Session) -> AgentResult:
    lower = text.lower()
    try:
        if any(w in lower for w in ("my attendance", "attendance percentage", "absent", "can i miss", "skip")):
            return _attendance_answer(text)
        if any(w in lower for w in ("timetable", "my classes", "today's classes", "todays classes", "next class")):
            return _timetable_answer(text)
        if any(w in lower for w in ("announcement", "notice")):
            return _announcement_answer()
    except UMSLiveAttendanceUnavailable as exc:
        return AgentResult(str(exc), "ums", None, "UMS (not connected)")

    info = _info_answer(text)
    if info:
        return info
    return AgentResult(
        "I can help with your attendance, timetable, notices, messages and hostel leave from UMS, "
        "and with general LPU information like contacts, rules, exam dates and hostel fees.",
        "general", None, "CampusAI",
    )
