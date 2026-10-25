"""Offline tests for day/time resolution and the shared tool registry.

No browser, no network, no model. These are the calculations that must never be
left to a language model, so they are pinned here.

    python scripts/test_schedule.py
"""
from __future__ import annotations

import pathlib
import sys
from datetime import date, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.schedule import (  # noqa: E402
    class_at,
    classes_on,
    next_class,
    parse_clock,
    parse_date,
    resolve_day,
    summarise_day,
)

PASSED = 0
FAILED: list[str] = []


def check(label: str, got, want) -> None:
    global PASSED
    if got == want:
        PASSED += 1
    else:
        FAILED.append(f"{label}\n    got:  {got!r}\n    want: {want!r}")


def truthy(label: str, got) -> None:
    check(label, bool(got), True)


# A Wednesday, so "tomorrow" is a Thursday and the week wraps predictably.
TODAY = date(2026, 9, 9)

# --------------------------------------------------------------------------
# Days
# --------------------------------------------------------------------------
check("today is a Wednesday", resolve_day("today", TODAY)["day"], "Wednesday")
check("today's date", resolve_day("today", TODAY)["date"], "2026-09-09")
check("tomorrow is a Thursday", resolve_day("tomorrow", TODAY)["day"], "Thursday")
check("yesterday is a Tuesday", resolve_day("yesterday", TODAY)["day"], "Tuesday")
check("no argument means today", resolve_day(None, TODAY)["day"], "Wednesday")

check("a weekday name looks forward", resolve_day("friday", TODAY)["date"], "2026-09-11")
check("short forms work", resolve_day("fri", TODAY)["day"], "Friday")
# Monday is behind us this week, so it means next Monday.
check("a past weekday rolls forward", resolve_day("monday", TODAY)["date"], "2026-09-14")
# Asking for the day it already is should stay today, not jump a week.
check("today's own weekday stays today", resolve_day("wednesday", TODAY)["date"], "2026-09-09")
check("'next wednesday' does jump a week", resolve_day("next wednesday", TODAY)["date"], "2026-09-16")

check("an ISO date is accepted", resolve_day("2026-09-11", TODAY)["day"], "Friday")
check("a UMS date is accepted", resolve_day("11/09/2026", TODAY)["day"], "Friday")
check("nonsense is refused", resolve_day("whenever", TODAY)["understood"], False)
check("nonsense names no day", resolve_day("whenever", TODAY)["day"], "")

# The phrase that made the model ask the student for a date instead of answering.
check("day after tomorrow", resolve_day("day after tomorrow", TODAY)["date"], "2026-09-11")
check("'the day after tomorrow'", resolve_day("the day after tomorrow", TODAY)["date"], "2026-09-11")
check("a common misspelling still works", resolve_day("day after tommorow", TODAY)["date"], "2026-09-11")
check("overmorrow", resolve_day("overmorrow", TODAY)["date"], "2026-09-11")
check("day before yesterday", resolve_day("day before yesterday", TODAY)["date"], "2026-09-07")
check("'in 3 days'", resolve_day("in 3 days", TODAY)["date"], "2026-09-12")
check("'2 days ago'", resolve_day("2 days ago", TODAY)["date"], "2026-09-07")
check("'this friday'", resolve_day("this friday", TODAY)["date"], "2026-09-11")
check("'last monday' looks back", resolve_day("last monday", TODAY)["date"], "2026-09-07")
check("'on friday' drops the preposition", resolve_day("on friday", TODAY)["date"], "2026-09-11")
check("trailing punctuation is ignored", resolve_day("Tomorrow?", TODAY)["date"], "2026-09-10")

# Every answer carries the calendar, so the model never has to ask for it.
context = resolve_day("day after tomorrow", TODAY)
check("today's date travels with the answer", context["today_date"], "2026-09-09")
check("today's weekday travels with it too", context["today_day"], "Wednesday")
check("even a refusal carries today", resolve_day("whenever", TODAY)["today_date"], "2026-09-09")

check("date parsing: dd/mm/yyyy", parse_date("11/09/2026"), date(2026, 9, 11))
check("date parsing: '11 Sep 2026'", parse_date("11 Sep 2026"), date(2026, 9, 11))
check("date parsing: trailing time trimmed", parse_date("11/09/2026 14:30"), date(2026, 9, 11))
check("date parsing: unreadable", parse_date("last week"), None)
check("date parsing: empty", parse_date(""), None)

# --------------------------------------------------------------------------
# Clock times. This is the "1:40" question.
# --------------------------------------------------------------------------
check("'1:40' prefers the afternoon", parse_clock("1:40")[0].strftime("%H:%M"), "13:40")
check("'1:40' still offers the morning as a second reading",
      [t.strftime("%H:%M") for t in parse_clock("1:40")], ["13:40", "01:40"])
check("'13:40' is unambiguous", [t.strftime("%H:%M") for t in parse_clock("13:40")], ["13:40"])
check("'1:40 pm' is explicit", [t.strftime("%H:%M") for t in parse_clock("1:40 pm")], ["13:40"])
check("'9:00 am' is explicit", [t.strftime("%H:%M") for t in parse_clock("9:00 am")], ["09:00"])
check("'9 am' with no minutes", [t.strftime("%H:%M") for t in parse_clock("9 am")], ["09:00"])
check("'8:00' stays morning first", [t.strftime("%H:%M") for t in parse_clock("8:00")],
      ["08:00", "20:00"])
check("a bad minute is refused", parse_clock("13:75"), [])
check("no time at all", parse_clock("later"), [])

# --------------------------------------------------------------------------
# Slots. A real day from the live UMS timetable.
# --------------------------------------------------------------------------
CLASSES = [
    {"day": "Wednesday", "time": "09:00", "end": "09:50", "subject": "CSE329",
     "room": "34-503", "type_label": "Lecture"},
    {"day": "Wednesday", "time": "13:40", "end": "14:30", "subject": "CSE310",
     "room": "38-701", "type_label": "Practical"},
    {"day": "Wednesday", "time": "14:30", "end": "15:20", "subject": "CSE310",
     "room": "38-701", "type_label": "Practical"},
    {"day": "Thursday", "time": "11:00", "end": "11:50", "subject": "MTH302",
     "room": "34-201", "type_label": "Lecture"},
]

check("a day's classes come back in order",
      [c["time"] for c in classes_on(CLASSES, "Wednesday")], ["09:00", "13:40", "14:30"])
check("day matching ignores case", len(classes_on(CLASSES, "wednesday")), 3)
check("a free day is empty, not an error", classes_on(CLASSES, "Sunday"), [])

found = class_at(CLASSES, "Wednesday", "1:40")
check("1:40 finds the afternoon practical", found["matched"], True)
check("1:40 resolves to 13:40", found["asked_time"], "13:40")
check("1:40 finds exactly one class", len(found["classes"]), 1)
check("1:40 finds the right course", found["classes"][0]["subject"], "CSE310")

# Back-to-back periods must not both match at the boundary.
boundary = class_at(CLASSES, "Wednesday", "14:30")
check("a boundary belongs to the later class", len(boundary["classes"]), 1)
check("the boundary picks the class starting then", boundary["classes"][0]["time"], "14:30")

gap = class_at(CLASSES, "Wednesday", "11:00")
check("a gap matches nothing", gap["matched"], False)
check("a gap still reports what came before", gap["before"]["subject"], "CSE329")
check("a gap still reports what comes next", gap["after"]["subject"], "CSE310")

check("an unreadable time reports no readings", class_at(CLASSES, "Wednesday", "soon")["readings"], [])

# next_class walks forward from a moment, including into later days.
upcoming = next_class(CLASSES, datetime(2026, 9, 9, 10, 0))
check("next class after 10:00 Wednesday", upcoming["subject"], "CSE310")
check("next class is on the same day", upcoming["in_days"], 0)
after_hours = next_class(CLASSES, datetime(2026, 9, 9, 20, 0))
check("after the last class, tomorrow's first", after_hours["subject"], "MTH302")
check("and it is one day ahead", after_hours["in_days"], 1)
check("an empty timetable has no next class", next_class([], datetime(2026, 9, 9, 10, 0)), None)

truthy("a day summary names the courses", "CSE310" in summarise_day("Wednesday", classes_on(CLASSES, "Wednesday")))
check("an empty day says so", summarise_day("Sunday", []), "No classes are timetabled for Sunday.")

# --------------------------------------------------------------------------
# Notice and message stamps: the date AND the time, parsed in Python.
# --------------------------------------------------------------------------
from app.services.schedule import freshness, parse_datetime, today_context  # noqa: E402

check("stamp: plain date", parse_datetime("05/09/2026")["iso"], "2026-09-05")
check("stamp: date with a 12-hour time",
      parse_datetime("5 Sep 2026 10:30 AM")["time"].strftime("%H:%M"), "10:30")
check("stamp: pm is converted",
      parse_datetime("01/09/2026 9:05 PM")["time"].strftime("%H:%M"), "21:05")
check("stamp: 'Posted on' is stripped", parse_datetime("Posted on 2026-09-05")["iso"], "2026-09-05")
check("stamp: 'Dated :' is stripped", parse_datetime("Dated : 5-Sep-26")["iso"], "2026-09-05")
check("stamp: month-name first", parse_datetime("Sep 5, 2026")["iso"], "2026-09-05")
check("stamp: 24-hour time", parse_datetime("05-09-2026 14:05")["readable"], "05 Sep 2026 14:05")
check("stamp: no date means None, never today", parse_datetime("no date here"), None)
check("stamp: empty means None", parse_datetime(""), None)
check("stamp: a date without a time has no time", parse_datetime("05/09/2026")["time"], None)

# --------------------------------------------------------------------------
# Freshness: a cached reading is never presented as a fresh look.
# --------------------------------------------------------------------------
import time as _time  # noqa: E402

check("freshness: no timestamp", freshness(None)["cached"], False)
check("freshness: seconds old reads as just now", freshness(_time.time())["as_of"], "just now")
recent = freshness(_time.time() - 240)
check("freshness: four minutes old is cached", recent["cached"], True)
check("freshness: and says so", recent["as_of"], "4 minute(s) ago")
check("freshness: two hours old", freshness(_time.time() - 7200)["as_of"], "2 hour(s) ago")

truthy("today_context spells the date out", today_context(TODAY)["today_readable"].startswith("Wednesday"))

# Caching must actually be configured, or every question re-opens the portal.
from app.core.config import settings  # noqa: E402

truthy("attendance is cached for at least 5 minutes", settings.ums_attendance_ttl_seconds >= 300)
truthy("panels are cached for at least 5 minutes", settings.ums_panel_ttl_seconds >= 300)
truthy("the name is cached for longer still",
       settings.ums_profile_ttl_seconds >= settings.ums_panel_ttl_seconds)

# --------------------------------------------------------------------------
# One tool registry, shared by every provider.
# --------------------------------------------------------------------------
from app.agent.tools import SYSTEM_INSTRUCTION, TOOL_NAMES, TOOL_SPECS  # noqa: E402

check("every tool has a unique name", len(set(TOOL_NAMES)), len(TOOL_NAMES))
for spec in TOOL_SPECS:
    truthy(f"{spec['name']} has a description", len(spec["description"]) > 30)
    check(f"{spec['name']} declares an object schema", spec["parameters"]["type"], "object")
    for required in spec["parameters"].get("required", []):
        truthy(f"{spec['name']}: required {required!r} is declared",
               required in spec["parameters"]["properties"])

for expected in ("get_day_classes", "get_class_at", "get_next_class",
                 "get_recent_announcements", "get_messages", "get_student_profile"):
    truthy(f"the registry has {expected}", expected in TOOL_NAMES)

# Nothing that writes to UMS may ever be reachable by a model.
for forbidden in ("prefill", "submit_leave", "apply_leave", "set_", "delete_"):
    check(f"no write tool named {forbidden!r}",
          any(forbidden in name for name in TOOL_NAMES), False)

truthy("the model is told not to do arithmetic", "Do no arithmetic" in SYSTEM_INSTRUCTION)
truthy("the model is told never to ask for today's date",
       "Never ask the student what today's date is" in SYSTEM_INSTRUCTION)
truthy("the model is told to quote a notice's date", "date_iso" in SYSTEM_INSTRUCTION)
truthy("the model is told to report cache age", "as_of" in SYSTEM_INSTRUCTION)
truthy("the model is told it cannot apply for leave", "cannot apply for" in SYSTEM_INSTRUCTION)
truthy("the model is told never to ask for passwords", "passwords" in SYSTEM_INSTRUCTION)

# Both providers must expose the identical tool list - that is the whole point
# of the shared registry.
root = pathlib.Path(__file__).resolve().parents[1]
gemini = (root / "app" / "agent" / "gemini_service.py").read_text(encoding="utf-8")
ollama = (root / "app" / "agent" / "ollama_service.py").read_text(encoding="utf-8")
for source, who in ((gemini, "gemini"), (ollama, "ollama")):
    truthy(f"{who} imports the shared tool specs", "from app.agent.tools import" in source)
    truthy(f"{who} uses the shared dispatcher", "execute_tool" in source)
    truthy(f"{who} uses the shared system instruction", "SYSTEM_INSTRUCTION" in source)
    check(f"{who} declares no tools of its own", "\"description\": (" in source, False)

# The Ollama client must not log or leak the key.
truthy("the key is sent as a bearer header", 'f"Bearer {settings.ollama_api_key}"' in ollama)
for forbidden in ("log.info(headers", "print(headers", "log.debug(payload"):
    check(f"the Ollama client never logs {forbidden!r}", forbidden in ollama, False)

print(f"\n{PASSED} checks passed, {len(FAILED)} failed")
for failure in FAILED:
    print("  FAIL " + failure)
sys.exit(1 if FAILED else 0)
