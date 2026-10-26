"""The one tool registry, shared by every model CampusAI can talk to.

Gemini and Ollama get the same tool list from :data:`TOOL_SPECS` and the same
dispatcher in :func:`execute_tool`, so a tool can never exist for one provider
and not the other, and a fix never has to be made twice.

Every tool is read-only except ``draft_hostel_leave``, which validates a draft
and still writes nothing. Nothing here can submit a leave application, and
nothing here can see a UMS password.

The rule the whole app is built on holds inside every tool: arithmetic, dates
and times are computed in Python and handed to the model finished. The model
chooses which tool to call and puts the answer into words; it does not count,
add up percentages, or work out what day tomorrow is.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.knowledge import search as search_university_info
from app.tools.attendance import (
    calculate_attendance,
    get_attendance_detail,
    get_ums_attendance,
    get_ums_diagnostics,
)
from app.tools.campus import (
    draft_leave_tool,
    get_announcements_tool,
    get_class_at_tool,
    get_day_classes_tool,
    get_leave_tool,
    get_messages_tool,
    get_next_class_tool,
    get_recent_announcements_tool,
    get_timetable_tool,
)
from app.tools.student import get_student_profile_tool
from app.ums.state import UMSLiveAttendanceUnavailable

log = logging.getLogger("campusai.agent")

NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

#: Function declarations in the shape both providers accept. Gemini takes these
#: directly; the Ollama client wraps each one in {"type": "function", ...}.
TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "get_attendance",
        "description": (
            "Get the student's current attendance, read live from UMS: overall percentage and, "
            "per course, attended / total. 'attended' already counts duty leave and the "
            "first-week bonus as present, exactly like UMS's Total Percentage - use it (and "
            "'percentage') as the student's attendance and for calculate_attendance. "
            "attended_in_class and duty_leave are the breakdown; mention duty leave when it "
            "helps (e.g. '20 attended + 2 duty leave = 22/22'). "
            "If UMS is not connected the response has available=false and a message "
            "explaining which step failed."
        ),
        "parameters": NO_ARGS,
    },
    {
        "name": "get_attendance_detail",
        "description": (
            "Get the student's class-by-class attendance log per course: every recorded class "
            "with its date, time, type and whether they were present or absent, plus the list of "
            "classes they missed. Use this when the student asks which classes they missed, when "
            "they were absent, or why a course's percentage is low. Requires a live UMS session."
        ),
        "parameters": NO_ARGS,
    },
    {
        "name": "get_ums_diagnostics",
        "description": (
            "Get the UMS session state machine and diagnostics (browser started, UMS tab found, "
            "authenticated, attendance page found, table found, courses parsed, last error). Use "
            "this when the student asks why their live attendance is not showing."
        ),
        "parameters": NO_ARGS,
    },
    {
        "name": "calculate_attendance",
        "description": (
            "Calculate how many classes the student can miss, or must attend, to reach a target "
            "attendance percentage. Always use this tool instead of doing the arithmetic yourself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "attended": {"type": "integer", "description": "Classes attended so far."},
                "total": {"type": "integer", "description": "Classes held so far."},
                "target_percentage": {"type": "number", "description": "Usually 75."},
            },
            "required": ["attended", "total", "target_percentage"],
        },
    },
    {
        "name": "get_timetable",
        "description": (
            "Get the student's whole weekly timetable: day, start and end time, room, class type "
            "(Lecture/Practical/Tutorial) and course code. For a single day use get_day_classes "
            "instead, and for a specific time use get_class_at - those resolve the day and the "
            "clock for you. Returns live UMS data when the session is authenticated and labelled "
            "demo rows otherwise."
        ),
        "parameters": NO_ARGS,
    },
    {
        "name": "get_day_classes",
        "description": (
            "Get the classes on one day, in order. Pass 'today', 'tomorrow', 'yesterday', a "
            "weekday name like 'friday', or a date like '2026-09-11'. The day is worked out from "
            "the real calendar in backend code - never work out yourself what day today or "
            "tomorrow is."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "when": {
                    "type": "string",
                    "description": (
                        "The student's own words for the day: today, tomorrow, 'the day after "
                        "tomorrow', yesterday, 'in 3 days', 'next friday', or a date. Pass them "
                        "through unchanged - do not convert to a date yourself."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_class_at",
        "description": (
            "Find which class covers a given time - 'what class do I have at 1:40 today'. "
            "The backend reads the time (including deciding that a bare '1:40' means the "
            "afternoon), resolves the day, and compares it against each slot's start and end. "
            "If nothing covers that time it returns the class before and after instead. Never "
            "compare times yourself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "at": {"type": "string", "description": "A clock time, e.g. '1:40', '13:40', '9 am'."},
                "when": {
                    "type": "string",
                    "description": (
                        "Which day, in the student's own words ('today', 'the day after "
                        "tomorrow', 'friday'). Defaults to today."
                    ),
                },
            },
            "required": ["at"],
        },
    },
    {
        "name": "get_next_class",
        "description": (
            "Get the next class from right now, with the day it falls on. The comparison against "
            "the current time happens in backend code."
        ),
        "parameters": NO_ARGS,
    },
    {
        "name": "get_announcements",
        "description": (
            "Get current college announcements and notices, newest first. Prefer "
            "get_recent_announcements when the student asks about a particular day or topic. "
            "Items may carry attachments (PDFs, brochures); mention them by name when relevant. "
            "Each item carries 'when' - the date and time as the backend parsed it - and "
            "'date_iso'; quote 'when', and say the notice carried no readable date when "
            "date_iso is null."
        ),
        "parameters": NO_ARGS,
    },
    {
        "name": "get_recent_announcements",
        "description": (
            "Get announcements filtered in backend code before you see them: by day ('today', "
            "'yesterday', a weekday, a date) and/or by a search term. Use this for questions like "
            "'what notices came today' or 'any announcement about exams'. The response says how "
            "many matched and how many notices had an unreadable date, so report honestly rather "
            "than implying the list is complete when undated_skipped is above zero. Nothing in "
            "the data marks a notice as important - judge that from the wording yourself, and "
            "say it is your reading rather than an official flag."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "when": {
                    "type": "string",
                    "description": (
                        "Which day's notices, in the student's own words. Filters on each "
                        "notice's own parsed date."
                    ),
                },
                "query": {"type": "string", "description": "Words that must all appear."},
                "limit": {"type": "integer", "description": "How many to return. Default 10."},
            },
            "required": [],
        },
    },
    {
        "name": "get_messages",
        "description": (
            "Get the student's UMS messages from their FULL message store (often 1000+ "
            "messages, not just the recent ones), newest first, so limit=5 gives the last five. "
            "To find messages about something (a company, a test, a platform like Hitbullseye, "
            "a deadline), pass query: UMS itself searches the subject AND text of every message "
            "ever received. 'last N messages / msg' means limit=N (the N newest), NOT days; "
            "only 'last N days / din / weeks / months / mahine' means days (e.g. 60 for two "
            "months). When asked how many messages there are in total, give total_in_inbox. "
            "Report total_matching and say how many you show; if more matched than you list, "
            "say so - in plain words, never mention tools, APIs or field names. Each message has a 'when' (its date) - give it, and the sender "
            "when there is one. A date inside the text is a deadline, not the message's date. "
            "If UMS is not connected, say so and ask the student to click Connect UMS. Never "
            "invent messages or senders."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "How many messages to return (max 100). Default 10."},
                "query": {"type": "string", "description": "Search words, e.g. 'hitbullseye' or 'TATA ELXSI'."},
                "days": {"type": "integer", "description": "Only messages from the last N days."},
            },
            "required": [],
        },
    },
    {
        "name": "get_hostel_leave_balance",
        "description": (
            "Get the student's hostel leave balances (day and night: total, availed, remaining), "
            "the leave types their term offers, and who recommends and sanctions their leave. "
            "READ ONLY - CampusAI cannot submit a leave application, so if the student asks to "
            "apply, give them their balance and tell them to submit the form themselves in the "
            "CampusAI browser. Never claim to have applied for leave."
        ),
        "parameters": NO_ARGS,
    },
    {
        "name": "draft_hostel_leave",
        "description": (
            "Check a hostel leave application the student is planning, against their real balance "
            "and the leave types their term offers. Call this once you have all five details: "
            "leave_type, start, end (both as 'YYYY-MM-DD HH:MM'), visit_place and reason. It "
            "returns errors to relay, or a summary with how many leaves it uses and how many "
            "remain. It does NOT submit or fill anything - after a valid draft, tell the student "
            "to open Hostel Leave Application in UMS and submit it themselves. "
            "Never claim to have applied for, submitted or cancelled leave."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "leave_type": {"type": "string"},
                "start": {"type": "string", "description": "YYYY-MM-DD HH:MM"},
                "end": {"type": "string", "description": "YYYY-MM-DD HH:MM"},
                "visit_place": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["leave_type", "start", "end", "visit_place", "reason"],
        },
    },
    {
        "name": "get_student_profile",
        "description": (
            "Get who the student is, read live from UMS: their name, registration number, "
            "programme, term, hostel and room. Use this whenever the student asks about their "
            "own identity or you need their name. If available is false, say the name could not "
            "be read from UMS - never guess a name and never use a name from earlier in the chat."
        ),
        "parameters": NO_ARGS,
    },
    {
        "name": "get_university_info",
        "description": (
            "Look up general LPU information that CampusAI stores itself: contacts and phone "
            "numbers, address, attendance rules (75% minimum), academic calendar and exam dates, "
            "hostel rooms, hostel and mess fees, health centre, security and discipline rules, "
            "library, placements, scholarships and fee payment. Use this for any question about "
            "the university rather than the student's own data. Returns the best matching "
            "sections with their source. Follow the 'guidance' field. Never invent a fee, a "
            "date, a phone number or a policy that is not in the results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The topic in a few keywords, e.g. 'hostel fees' or 'exam dates'.",
                },
            },
            "required": ["query"],
        },
    },
]

TOOL_NAMES = tuple(spec["name"] for spec in TOOL_SPECS)

SYSTEM_INSTRUCTION = (
    "You are CampusAI, a chat assistant for a student at Lovely Professional University (LPU). "
    "Use tools whenever the answer depends on the student's own data or on university facts. "
    "Student data (attendance, timetable, notices, messages, leave, profile) is read live from "
    "the UMS portal. If a UMS tool reports available=false, explain which step failed and tell "
    "the student to click Connect UMS and finish signing in in the CampusAI browser window - "
    "never invent attendance, messages, notices or classes. "
    "Do no arithmetic and no date or time reasoning yourself. For attendance margins call "
    "calculate_attendance; for a day's classes call get_day_classes; for a specific time call "
    "get_class_at; for what is next call get_next_class. "
    "Never ask the student what today's date is, and never ask them to convert a phrase like "
    "'the day after tomorrow' into a date. Pass their words straight to the tool's 'when' "
    "argument - it understands today, tomorrow, the day after tomorrow, yesterday, the day "
    "before yesterday, 'in 3 days', this/next/last plus a weekday, and any date format - and it "
    "returns today_date and today_day, so after one call you know the calendar. Only if the tool "
    "replies understood=false should you ask for a clearer day. "
    "Notices and messages carry a 'when' and a 'date_iso' that the backend parsed: quote 'when' "
    "as the date and time, and if date_iso is null say the notice carried no readable date "
    "rather than leaving the date out or inventing one. "
    "Tool results also carry 'as_of': readings are cached for a few minutes so the student's "
    "browser is not driven around the portal for every question. When as_of is not 'just now', "
    "say the data is from that long ago instead of implying you checked this second. "
    "Call only the tools the question needs - an attendance question needs get_attendance, "
    "not the profile or the class log - so answers come back fast. Call get_student_profile "
    "only when the student asks about their own details (name, registration number, hostel, "
    "room, programme); do not call it just to greet them, and never guess a name. If it "
    "reports available=false, say the detail could not be read from UMS. "
    "When summarising messages or notices, work only from what the tool returned, say how many "
    "you looked at, and name senders and dates exactly as given. "
    "Never ask for, repeat, or store UMS usernames, passwords, or OTPs. "
    "You can read the student's hostel leave balance and check a draft, but you cannot apply for "
    "leave: never say you have submitted, cancelled, or changed a leave application. "
    "Do not expose database details, credentials, API keys, or internal tool mechanics. "
    "For general university information (contacts, rules, calendar, hostel, fees, placements, "
    "scholarships) call get_university_info and answer only from what it returns, mentioning "
    "the source. If the stored information does not cover the exact detail, say so and give "
    "the most relevant contact from it instead of guessing. "
    "Every phone number, email address, fee, date and URL you write must appear exactly in a "
    "tool result from this conversation. Never make one up, never fill in a partial number, "
    "and never name an office or contact that the results do not list - if you need a contact "
    "that is not in the results you have, call get_university_info with 'contact' first. "
    "This conversation has a memory: earlier turns are given to you with each question, so use "
    "what the student already told you instead of asking again. Figures quoted in that history "
    "are from when they were asked - call the tool again rather than repeating one as current. "
    "Answer clearly and concisely. Use short headings, bullet lists and tables where they help. "
    "VISUALS: when numbers are being compared or tracked (attendance per course, fees by room "
    "type, leave used vs left, classes per day), add ONE chart as a fenced block whose language "
    "is chart, containing only JSON like "
    '{"type":"bar","title":"Attendance by course","unit":"%","target":75,'
    '"data":[{"label":"CSE329","value":90.9},{"label":"CSE330","value":88.2}]}. '
    "type is one of bar, line, area, pie, donut, radial (progress rings for percentages of a "
    "whole). For two series per item use keys like {\"label\":\"CSE329\",\"Attended\":20,"
    "\"Delivered\":22}. Every number in a chart must come straight from a tool result - never "
    "compute, estimate or invent one; use the 'percentage' fields tools give you. "
    "For a step-by-step procedure (how to apply for hostel leave, re-evaluation, fee payment) "
    "use a fenced block whose language is steps, containing only JSON like "
    '{"title":"How to apply for hostel leave","steps":[{"title":"Open UMS","detail":"Sign in '
    'at ums.lpu.in"},{"title":"Submit the form","detail":"Your warden then approves it"}]} - '
    "3 to 7 steps, short titles, one-line details - and do NOT repeat the same steps as a "
    "numbered list. Steps must come from get_university_info or another tool result: call it "
    "first, and never invent UMS menu paths, button names, formats or rules. Use a Mermaid diagram (fenced block, language mermaid) only when the "
    "process really branches, e.g. approved vs rejected: flowchart TD, at most 8 nodes, short "
    "labels in double quotes. Use at most one visual of each kind per answer, only when it "
    "adds something, and always still say the key facts in words. "
    "LANGUAGE: reply in the language AND script of the student's latest message - Hindi, "
    "Punjabi, Tamil or any other. If they write Hindi in English letters (Hinglish, e.g. 'bhai "
    "mera attendance kitna hai'), reply in Hinglish in English letters too, never in Devanagari. "
    "Do this unless a reply language is set in the "
    "context below or the student asks for one, which then wins until they change it. Keep "
    "course codes, numbers, dates, names, phone numbers and URLs exactly as given."
)


def _int(args: dict[str, Any], key: str, default: int) -> int:
    """A tool argument as an int. Models sometimes send '5' rather than 5."""
    value = args.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def execute_tool(name: str, args: dict[str, Any], student_id: str, db: Session) -> dict[str, Any]:
    """Run one tool and log how long it took, so a slow answer can be traced to
    the tool that waited (usually a UMS page that was not cached yet)."""
    started = time.perf_counter()
    try:
        return _execute_tool(name, args, student_id, db)
    finally:
        log.info("[agent] tool %s took %.1fs", name, time.perf_counter() - started)


def _execute_tool(name: str, args: dict[str, Any], student_id: str, db: Session) -> dict[str, Any]:
    """Run one tool. The same dispatcher for every provider.

    A UMS outage comes back as data the model can read out, not as an exception
    that ends the conversation - and never as demo data standing in for live.
    """
    args = args or {}
    try:
        if name in ("get_attendance", "get_ums_attendance"):
            return get_ums_attendance()
        if name == "get_attendance_detail":
            return get_attendance_detail()
        if name == "get_ums_diagnostics":
            return get_ums_diagnostics()
        if name == "calculate_attendance":
            return calculate_attendance(
                student_id=student_id,
                attended=int(args["attended"]),
                total=int(args["total"]),
                target_percentage=float(args["target_percentage"]),
            )
        if name == "get_timetable":
            return get_timetable_tool()
        if name == "get_day_classes":
            return get_day_classes_tool(str(args.get("when") or "today"))
        if name == "get_class_at":
            return get_class_at_tool(str(args.get("at") or ""), str(args.get("when") or "today"))
        if name == "get_next_class":
            return get_next_class_tool()
        if name == "get_announcements":
            return get_announcements_tool()
        if name == "get_recent_announcements":
            return get_recent_announcements_tool(
                limit=_int(args, "limit", 10),
                when=(args.get("when") or None),
                query=(args.get("query") or None),
            )
        if name == "get_messages":
            return get_messages_tool(
                limit=_int(args, "limit", 10),
                query=(args.get("query") or None),
                days=(_int(args, "days", 0) or None),
            )
        if name == "get_hostel_leave_balance":
            return get_leave_tool()
        if name == "draft_hostel_leave":
            return draft_leave_tool(args)
        if name == "get_student_profile":
            return get_student_profile_tool()
        if name == "get_university_info":
            return search_university_info(str(args["query"]))
    except UMSLiveAttendanceUnavailable as exc:
        # The model is told the truth rather than being handed demo numbers.
        return {
            "available": False,
            "live": False,
            "error": "live_ums_data_unavailable",
            "message": str(exc),
            "state": (exc.diagnostics or {}).get("state"),
        }
    except KeyError as exc:
        return {"available": False, "error": "missing_argument",
                "message": f"The tool {name} needs {exc} and it was not provided."}
    except Exception as exc:  # noqa: BLE001 - tell the model the truth, don't crash the answer
        log.warning("[agent] tool %s failed: %s", name, exc)
        return {"available": False, "error": "tool_failed",
                "message": ("Reading this from UMS failed just now (UMS is still connected). "
                            "Tell the student to ask again in a moment."),
                "detail": str(exc)[:200]}
    return {"available": False, "error": "unknown_tool",
            "message": f"There is no tool called {name}."}


def intent_from_tools(tools: list[str]) -> str:
    if any("attendance" in tool for tool in tools):
        return "attendance"
    if any(t in tools for t in ("get_hostel_leave_balance", "draft_hostel_leave")):
        return "hostel_leave"
    if "get_messages" in tools:
        return "messages"
    if any(t in tools for t in ("get_timetable", "get_day_classes", "get_class_at", "get_next_class")):
        return "timetable"
    if any(t in tools for t in ("get_announcements", "get_recent_announcements")):
        return "announcements"
    if "get_student_profile" in tools:
        return "student_profile"
    if "get_university_info" in tools:
        return "university_info"
    return "general"


def source_from_tools(tools: list[str], live_used: bool) -> str:
    ums_tools = [t for t in tools if t not in ("get_university_info", "calculate_attendance")]
    if ums_tools:
        return "UMS (live)" if live_used else "UMS (not connected)"
    if "get_university_info" in tools:
        return "Stored university information"
    return "Language model only"
