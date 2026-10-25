"""Deterministic local agent used when Gemini is unavailable.

It calls the same backend tools, so it inherits the same live-vs-demo rule and
the same "no silent fallback" behaviour.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.tools.attendance import calculate_attendance, get_attendance
from app.tools.campus import get_announcements_tool, get_services_tool, get_timetable_tool
from app.ums.state import UMSLiveAttendanceUnavailable


@dataclass
class AgentResult:
    answer: str
    intent: str
    tool_used: str | None
    source: str
    action: str | None = None


def _attendance_answer(data: dict, text: str) -> AgentResult:
    subjects = data["subjects"]
    source = data.get("source", "Attendance data")
    live = data.get("live", False)
    lower = text.lower()
    label = "" if live else " (demo data - UMS is not connected)"

    if not subjects:
        return AgentResult(
            "No attendance records are available yet.", "attendance", "get_attendance", source, "attendance"
        )

    if "miss" in lower or "skip" in lower or "75" in lower:
        margins = []
        for subject in subjects:
            result = calculate_attendance(
                student_id="student-demo",
                attended=subject["attended"],
                total=subject["total"],
                target_percentage=75,
            )
            margins.append((result["can_miss"], subject["short"]))
        can_miss = min((item[0] for item in margins), default=0)
        limiting = ", ".join(short for misses, short in margins if misses == can_miss)
        return AgentResult(
            answer=(
                f"Your overall attendance is {data['overall_percentage']:.1f}%{label}. "
                f"At a 75% target you can miss up to {can_miss} more class(es) before the tightest "
                f"subject reaches the limit ({limiting}). Open Attendance for the full breakdown."
            ),
            intent="attendance",
            tool_used="get_attendance + calculate_attendance",
            source=source,
            action="attendance",
        )

    attended = sum(s["attended"] for s in subjects)
    total = sum(s["total"] for s in subjects)
    return AgentResult(
        answer=(
            f"Your overall attendance is {data['overall_percentage']:.1f}% "
            f"({attended}/{total} classes){label}."
        ),
        intent="attendance",
        tool_used="get_attendance",
        source=source,
        action="attendance",
    )


def _timetable_answer(data: dict, text: str) -> AgentResult:
    classes = data["classes"]
    if not classes:
        return AgentResult("I couldn't find any timetable entries for that request.", "timetable", "get_timetable", "PostgreSQL timetable data", "timetable")
    lower = text.lower()
    day = next((d for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday") if d.lower() in lower), None)
    if day:
        items = [item for item in classes if item["day"].lower() == day.lower()]
        if items:
            details = "; ".join(f"{x['time']}-{x['end']} {x['subject']} in {x['room']}" for x in items)
            return AgentResult(f"{day}'s classes: {details}.", "timetable", "get_timetable", "PostgreSQL timetable data", "timetable")
    first = classes[:4]
    details = "; ".join(f"{x['day']} {x['time']} {x['subject']} in {x['room']}" for x in first)
    suffix = "" if len(classes) <= 4 else f" I found {len(classes)} total entries."
    return AgentResult(f"Here are some timetable entries: {details}.{suffix}", "timetable", "get_timetable", "PostgreSQL timetable data", "timetable")


def _announcement_answer(data: dict, text: str) -> AgentResult:
    items = data["announcements"]
    if not items:
        return AgentResult("There are no announcements available right now.", "announcements", "get_announcements", "PostgreSQL announcements data", "announcements")
    lower = text.lower()
    important = [item for item in items if item["important"]]
    selected = important if ("important" in lower or "urgent" in lower) and important else items[:3]
    details = " ".join(f"{x['title']} ({x['date']}): {x['text']}" for x in selected)
    return AgentResult(f"Here are the latest announcements. {details}", "announcements", "get_announcements", "PostgreSQL announcements data", "announcements")


def _services_answer(data: dict, text: str) -> AgentResult:
    items = data["services"]
    if not items:
        return AgentResult("I couldn't find a college service matching that request.", "services", "get_services", "PostgreSQL college services data", "services")
    details = "; ".join(f"{x['name']} — {x['description']}" for x in items[:5])
    return AgentResult(f"I found these college services: {details}.", "services", "get_services", "PostgreSQL college services data", "services")


def answer(text: str, student_id: str, db: Session) -> AgentResult:
    lower = text.lower()
    if any(word in lower for word in ("attendance", "absent", "miss", "skip")):
        try:
            return _attendance_answer(get_attendance(student_id, db), text)
        except UMSLiveAttendanceUnavailable as exc:
            return AgentResult(
                str(exc), "attendance", "get_attendance", "UMS Playwright session (unavailable)", "attendance"
            )
    if any(word in lower for word in ("timetable", "schedule", "today's classes", "todays classes", "what classes", "class")):
        return _timetable_answer(get_timetable_tool(student_id, db), text)
    if any(word in lower for word in ("announcement", "notice", "latest news", "important notice")):
        return _announcement_answer(get_announcements_tool(db), text)
    if "service" in lower or any(word in lower for word in ("certificate", "fee", "exam registration", "it support", "accounts office")):
        return _services_answer(get_services_tool(db, None), text)
    if "leave" in lower:
        return AgentResult(
            "I can prepare a hostel leave application. The portal form and Playwright tool will be connected in a later step.",
            "hostel_leave", None, "CampusAI", "leave",
        )
    return AgentResult(
        "I can help with attendance, timetable, announcements, hostel leave, and college services. Ask me what you need.",
        "general", None, "CampusAI", None,
    )
