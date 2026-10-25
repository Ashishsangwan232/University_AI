"""Days, clock times and which class you are in - all decided in Python.

"Which class do I have at 1:40 today?" is three separate pieces of reasoning:
what day is today, what "1:40" means on a 24-hour timetable, and which slot
covers that instant. A language model gets at least one of those wrong sooner or
later, so none of it happens in the model. The model asks for a day and a time;
this module answers with a slot.

No UMS, no database, no network - pure functions over the class list the
timetable tool already returns, so it is unit testable offline.
"""
from __future__ import annotations

import re
import time as _clock
from datetime import date, datetime, time, timedelta
from typing import Any

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
#: Short forms UMS and students both use.
DAY_ALIASES = {
    "mon": "Monday", "monday": "Monday",
    "tue": "Tuesday", "tues": "Tuesday", "tuesday": "Tuesday",
    "wed": "Wednesday", "weds": "Wednesday", "wednesday": "Wednesday",
    "thu": "Thursday", "thur": "Thursday", "thurs": "Thursday", "thursday": "Thursday",
    "fri": "Friday", "friday": "Friday",
    "sat": "Saturday", "saturday": "Saturday",
    "sun": "Sunday", "sunday": "Sunday",
}

#: Teaching hours. Used to read a bare "1:40" as the afternoon, the way a
#: student means it - never to invent a class outside these hours.
COLLEGE_OPENS = time(7, 0)
COLLEGE_CLOSES = time(21, 0)

CLOCK = re.compile(
    r"(?P<hour>\d{1,2})\s*[:.\s]\s*(?P<minute>\d{2})\s*(?P<suffix>am|pm|a\.m\.|p\.m\.)?",
    re.I,
)
BARE_HOUR = re.compile(r"^\s*(?P<hour>\d{1,2})\s*(?P<suffix>am|pm|a\.m\.|p\.m\.)\s*$", re.I)

#: Date shapes UMS prints on notices and messages.
DATE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y",
    "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y",
    "%d/%m/%y", "%d-%b-%Y", "%d-%b-%y", "%d %b %y", "%b %d %y",
)


# ---------------------------------------------------------------------------
# Days
# ---------------------------------------------------------------------------
#: Phrases that mean a fixed number of days from today. Longest first, so
#: "day after tomorrow" is matched before "tomorrow".
RELATIVE_DAYS: tuple[tuple[str, int], ...] = (
    ("day after tomorrow", 2),
    ("day after tommorow", 2),      # a common spelling, and worth accepting
    ("overmorrow", 2),
    ("day before yesterday", -2),
    ("tomorrow", 1),
    ("tommorow", 1),
    ("tmrw", 1),
    ("next day", 1),
    ("yesterday", -1),
    ("today", 0),
    ("tonight", 0),
    ("this evening", 0),
    ("this afternoon", 0),
    ("this morning", 0),
    ("now", 0),
    ("this day", 0),
)

#: "in 3 days", "3 days from now", "after 2 days", "2 days ago".
IN_N_DAYS = re.compile(
    r"^(?:in|after)?\s*(?P<count>\d{1,2})\s*days?\s*(?P<direction>from now|later|ahead|ago|back|before)?$",
    re.I,
)

#: Leading words that only position a weekday: "this friday", "coming monday".
DAY_PREFIX = re.compile(r"^(?:on\s+)?(?P<prefix>next|this|coming|last|previous|upcoming)?\s*(?P<day>.+)$", re.I)


def freshness(updated_at: float | None) -> dict[str, Any]:
    """How old a UMS reading is, so nothing is presented as just-checked.

    CampusAI caches each panel, which is why asking twice in a few minutes does
    not re-open the portal. The model is handed the age and reports it, instead
    of implying it looked again.
    """
    if not updated_at:
        return {"cached": False, "age_seconds": None, "as_of": "just now"}
    age = max(0, int(_clock.time() - updated_at))
    if age < 60:
        readable = "just now"
    elif age < 3600:
        readable = f"{age // 60} minute(s) ago"
    else:
        readable = f"{age // 3600} hour(s) ago"
    return {"cached": age > 5, "age_seconds": age, "as_of": readable}


def today_context(today: date | None = None) -> dict[str, str]:
    """Today, spelled out. Every schedule tool returns this.

    The model has no clock and no calendar, so it is told the date rather than
    left to work one out - which is how "the day after tomorrow" turned into a
    question back to the student instead of an answer.
    """
    today = today or date.today()
    return {
        "today_date": today.isoformat(),
        "today_day": DAY_NAMES[today.weekday()],
        "today_readable": today.strftime("%A, %d %B %Y"),
    }


def resolve_day(when: str | None, today: date | None = None) -> dict[str, Any]:
    """Turn a phrase about a day into a real day.

    Understands today / tomorrow / the day after tomorrow / yesterday / the day
    before yesterday / "in 3 days" / a weekday name, optionally with this, next,
    coming or last / and a date in any format UMS prints.

    Returns ``{"day", "date", "label", "understood", "today_*"}``. ``understood``
    is False only when the phrase really meant nothing.
    """
    today = today or date.today()
    context = today_context(today)
    raw = (when or "today").strip()
    # Normalise "the day after tomorrow", "on Friday", extra spaces.
    text = re.sub(r"\s+", " ", raw.lower()).strip(" ?.!")
    text = re.sub(r"^(?:the|on)\s+", "", text)

    target: date | None = None
    label = text

    for phrase, offset in RELATIVE_DAYS:
        if text == phrase:
            target = today + timedelta(days=offset)
            label = phrase
            break

    if target is None:
        counted = IN_N_DAYS.match(text)
        if counted:
            days = int(counted.group("count"))
            backwards = (counted.group("direction") or "").lower() in ("ago", "back", "before")
            target = today + timedelta(days=-days if backwards else days)
            label = text

    if target is None:
        shaped = DAY_PREFIX.match(text)
        prefix = (shaped.group("prefix") or "").lower() if shaped else ""
        named = DAY_ALIASES.get(shaped.group("day").strip()) if shaped else None
        if named:
            index = DAY_NAMES.index(named)
            if prefix in ("last", "previous"):
                behind = (today.weekday() - index) % 7 or 7
                target = today - timedelta(days=behind)
            else:
                ahead = (index - today.weekday()) % 7
                if prefix == "next" and ahead == 0:
                    ahead = 7
                target = today + timedelta(days=ahead)
            label = f"{prefix} {named}".strip()

    if target is None:
        parsed = parse_date(text)
        if not parsed:
            return {"day": "", "date": "", "label": raw, "understood": False, **context}
        target, label = parsed, parsed.strftime("%d %b %Y")

    return {
        "day": DAY_NAMES[target.weekday()],
        "date": target.isoformat(),
        "label": label,
        "understood": True,
        **context,
    }


#: Words UMS puts around a stamp: "Posted on 05/09/2026", "Dated : 5 Sep 2026".
STAMP_NOISE = re.compile(
    r"^\s*(?:posted|published|created|sent|received|dated|date|on|at|last\s+updated)\b[\s:.-]*",
    re.I,
)
#: The date part of a stamp, in any of the shapes UMS prints.
DATE_IN_TEXT = re.compile(
    r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"           # 05/09/2026
    r"|\d{4}-\d{2}-\d{2}"                            # 2026-09-05
    r"|\d{1,2}[\s\-][A-Za-z]{3,9}[\s\-,]+\d{2,4}"    # 5 Sep 2026, 5-Sep-26
    r"|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4})"         # Sep 5, 2026
)
#: The time part, if the stamp carries one.
TIME_IN_TEXT = re.compile(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm|AM|PM)?")


def parse_date(value: str | None) -> date | None:
    """A date from the formats UMS actually prints, or None. Never a guess."""
    stamp = parse_datetime(value)
    return stamp["date"] if stamp else None


def parse_datetime(value: str | None) -> dict[str, Any] | None:
    """Pull a date and, when present, a time out of a UMS stamp.

    UMS writes these several ways - "05/09/2026", "5 Sep 2026 10:30 AM",
    "Posted on 2026-09-05" - and a notice with no readable date must come back
    as None rather than as today, so nothing is ever filed under the wrong day.

    Returns ``{"date", "time", "iso", "readable"}`` or None.
    """
    text = re.sub(r"\s+", " ", (value or "")).strip()
    if not text:
        return None
    text = STAMP_NOISE.sub("", text).strip()

    found = DATE_IN_TEXT.search(text)
    if not found:
        return None
    stamp = found.group(1).replace(".", "/").replace(",", "")
    parsed: date | None = None
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(stamp, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return None

    clock: time | None = None
    # Only look for a time after the date, so "05/09" is never read as a time.
    tail = text[found.end():]
    at = TIME_IN_TEXT.search(tail)
    if at:
        hour, minute = int(at.group(1)), int(at.group(2))
        suffix = (at.group(3) or "").lower()
        if suffix == "pm" and hour < 12:
            hour += 12
        elif suffix == "am" and hour == 12:
            hour = 0
        if hour <= 23 and minute <= 59:
            clock = time(hour, minute)

    return {
        "date": parsed,
        "time": clock,
        "iso": parsed.isoformat(),
        "readable": parsed.strftime("%d %b %Y") + (clock.strftime(" %H:%M") if clock else ""),
    }


# ---------------------------------------------------------------------------
# Clock times
# ---------------------------------------------------------------------------
def parse_clock(value: str | None) -> list[time]:
    """Every reasonable reading of a spoken time, most likely first.

    A student who says "1:40" on a 24-hour timetable means 13:40, so that
    reading comes first - but 01:40 is still returned, and the caller picks
    whichever actually matches a class rather than assuming.
    """
    text = (value or "").strip()
    if not text:
        return []

    bare = BARE_HOUR.match(text)
    if bare:
        hour = int(bare.group("hour")) % 12
        if bare.group("suffix").lower().startswith("p"):
            hour += 12
        return [time(hour, 0)] if 0 <= hour <= 23 else []

    match = CLOCK.search(text)
    if not match:
        return []
    hour, minute = int(match.group("hour")), int(match.group("minute"))
    if minute > 59 or hour > 23:
        return []

    suffix = (match.group("suffix") or "").lower().replace(".", "")
    if suffix.startswith("p"):
        return [time((hour % 12) + 12, minute)]
    if suffix.startswith("a"):
        return [time(hour % 12, minute)]

    readings = [time(hour, minute)]
    if hour < 12:
        afternoon = time(hour + 12, minute)
        # Prefer the reading that falls inside teaching hours.
        if not (COLLEGE_OPENS <= readings[0] <= COLLEGE_CLOSES):
            readings.insert(0, afternoon)
        elif afternoon <= COLLEGE_CLOSES:
            readings.append(afternoon)
    return readings


def _as_time(value: str | None) -> time | None:
    try:
        hour, minute = (int(part) for part in (value or "").split(":"))
        return time(hour, minute)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------
def classes_on(classes: list[dict[str, Any]], day: str) -> list[dict[str, Any]]:
    """Every slot on one weekday, in clock order."""
    wanted = (day or "").strip().lower()
    found = [c for c in classes if (c.get("day") or "").strip().lower() == wanted]
    return sorted(found, key=lambda c: _as_time(c.get("time")) or time(0, 0))


def class_at(
    classes: list[dict[str, Any]], day: str, at: str
) -> dict[str, Any]:
    """The class covering a given time, or the nearest one either side.

    Returns ``{"matched", "asked_time", "classes", "before", "after", "readings"}``.
    A slot matches when start <= t < end, so back-to-back periods never both
    match.
    """
    readings = parse_clock(at)
    today = classes_on(classes, day)
    result: dict[str, Any] = {
        "matched": False,
        "asked_time": "",
        "readings": [t.strftime("%H:%M") for t in readings],
        "classes": [],
        "before": None,
        "after": None,
        "day_classes": today,
    }
    if not readings:
        return result

    for reading in readings:
        hits = []
        for item in today:
            start, end = _as_time(item.get("time")), _as_time(item.get("end"))
            if start and end and start <= reading < end:
                hits.append(item)
        if hits:
            result.update(matched=True, asked_time=reading.strftime("%H:%M"), classes=hits)
            return result

    # Nothing covers it: say what is on either side rather than nothing at all.
    reading = readings[0]
    result["asked_time"] = reading.strftime("%H:%M")
    before = [c for c in today if (_as_time(c.get("end")) or time(0, 0)) <= reading]
    after = [c for c in today if (_as_time(c.get("time")) or time(0, 0)) > reading]
    result["before"] = before[-1] if before else None
    result["after"] = after[0] if after else None
    return result


def next_class(
    classes: list[dict[str, Any]], now: datetime | None = None
) -> dict[str, Any] | None:
    """The next slot from this moment, searching up to a week ahead."""
    now = now or datetime.now()
    for offset in range(8):
        moment = now + timedelta(days=offset)
        for item in classes_on(classes, DAY_NAMES[moment.weekday()]):
            start = _as_time(item.get("time"))
            if not start:
                continue
            if offset > 0 or start > now.time():
                return {**item, "date": moment.date().isoformat(),
                        "in_days": offset}
    return None


def summarise_day(day: str, items: list[dict[str, Any]]) -> str:
    """One deterministic line about a day, for the model to build on."""
    if not items:
        return f"No classes are timetabled for {day}."
    parts = [
        f"{c.get('time')}-{c.get('end')} {c.get('subject')}"
        + (f" ({c.get('type_label') or c.get('type')})" if c.get("type_label") or c.get("type") else "")
        + (f" in {c.get('room')}" if c.get("room") else "")
        for c in items
    ]
    return f"{day}: {len(items)} class(es) - " + "; ".join(parts)
