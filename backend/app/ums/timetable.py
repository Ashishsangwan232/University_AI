"""Extraction of the UMS timetable.

``frmMyCurrentTimeTable.aspx`` ships empty and fills ``#timetable`` by AJAX when
its "Timetable" control calls ``GetTimeTableData1()`` - the same pattern as the
attendance modal. The rendered content is not a table; it is text of the form::

    Monday
    10:20 - 11:10   33-301 - L - CSE472   K2EM001
    11:10 - 12:00   33-301 - L - CSE472   K2EM001
    Tuesday
    ...

so the parser is regex-driven over the container's text, tolerant of whether the
slots arrive one per line or run together, and of the inconsistent spacing UMS
puts around the time dash ("11:10 -12:00").

Playwright-free, so it can be unit tested against captured text.
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger("campusai.ums")

#: Reads the timetable container's text, keeping line breaks.
TIMETABLE_JS = r"""
(cfg) => {
  const root = document.querySelector(cfg.selector);
  if (!root) return null;
  const raw = root.innerText || root.textContent || '';
  return {
    selector: cfg.selector,
    lines: raw.split('\n').map(s => s.replace(/[ \t ]+/g, ' ').trim()).filter(Boolean),
    text: raw.replace(/\s+/g, ' ').trim(),
    children: root.children.length
  };
}
"""

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_RE = re.compile(r"\b(" + "|".join(DAYS) + r")\b", re.I)

#: "10:20 - 11:10  33-301 - L - CSE472  K2EM001"
#: room may carry hyphens, so the separators around type and code are what anchor it.
SLOT_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2})\s*-\s*(?P<end>\d{1,2}:\d{2})\s+"
    r"(?P<room>[\w\-/().]+)\s*-\s*(?P<type>[A-Za-z]{1,3})\s*-\s*"
    r"(?P<code>[A-Z]{2,5}\s?\d{3,4}[A-Z]?)"
    r"(?:\s+(?P<group>[A-Z0-9]{3,12}))?"
)

#: Fallback when the room/type/code shape differs: at least a time range and a code.
LOOSE_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2})\s*-\s*(?P<end>\d{1,2}:\d{2})"
    r"(?P<middle>.{0,60}?)(?P<code>[A-Z]{2,5}\s?\d{3,4}[A-Z]?)\b"
)

CLASS_TYPES = {"L": "Lecture", "P": "Practical", "T": "Tutorial", "S": "Seminar"}


def _valid_time(value: str) -> bool:
    try:
        hour, minute = (int(part) for part in value.split(":"))
    except ValueError:
        return False
    return 0 <= hour <= 23 and 0 <= minute <= 59


def _slot(match: re.Match[str], day: str) -> dict[str, Any] | None:
    start, end = match.group("start"), match.group("end")
    if not _valid_time(start) or not _valid_time(end):
        return None
    groups = match.groupdict()
    code = (groups.get("code") or "").replace(" ", "").upper()
    class_type = (groups.get("type") or "").upper()
    return {
        "day": day,
        "time": start,
        "end": end,
        "room": (groups.get("room") or "").strip(" -"),
        "type": class_type,
        "type_label": CLASS_TYPES.get(class_type, class_type or ""),
        "subject": code,
        "group": (groups.get("group") or "").strip(),
    }


def parse_timetable(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return one record per class slot, in the order UMS lists them.

    Returns an empty list rather than guessing when nothing matches.
    """
    if not payload:
        return []
    text = payload.get("text") or " ".join(payload.get("lines") or [])
    if not text.strip():
        return []

    # Split the text into day sections, keeping each day's own name.
    marks = [(m.start(), m.group(1).capitalize()) for m in DAY_RE.finditer(text)]
    sections: list[tuple[str, str]] = []
    if marks:
        for index, (position, day) in enumerate(marks):
            end = marks[index + 1][0] if index + 1 < len(marks) else len(text)
            sections.append((day, text[position:end]))
    else:
        sections.append(("", text))

    classes: list[dict[str, Any]] = []
    for day, section in sections:
        found = [_slot(m, day) for m in SLOT_RE.finditer(section)]
        found = [slot for slot in found if slot]
        if not found:
            found = [_slot(m, day) for m in LOOSE_RE.finditer(section)]
            found = [slot for slot in found if slot]
        classes.extend(found)

    # UMS repeats a slot when a class spans two periods; keep both but drop exact
    # duplicates, which come from the container being read twice.
    unique: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for item in classes:
        key = (item["day"], item["time"], item["end"], item["subject"], item["room"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    log.info("[UMS] Timetable: %d slot(s) across %d day section(s)", len(unique), len(sections))
    return unique


def validate_timetable(classes: list[dict[str, Any]]) -> tuple[bool, str]:
    if not classes:
        return False, "no class slots were parsed from the timetable panel"
    if not any(item["subject"] for item in classes):
        return False, "slots were found but none carry a course code"
    for item in classes:
        if not _valid_time(item["time"]) or not _valid_time(item["end"]):
            return False, f"implausible time {item['time']}-{item['end']}"
    days = {item["day"] for item in classes if item["day"]}
    if len(classes) > 4 and not days:
        return False, "no day headings were found, so slots cannot be placed"
    return True, "ok"


def group_by_day(classes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Day -> slots, in weekday order, for the UI."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in classes:
        grouped.setdefault(item["day"] or "Unscheduled", []).append(item)
    ordered = {day: grouped[day] for day in DAYS if day in grouped}
    for day, items in grouped.items():
        if day not in ordered:
            ordered[day] = items
    return ordered
