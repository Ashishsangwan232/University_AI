"""Timetable, notices, messages and hostel leave tools for the chat agent.

Everything is read live from UMS. When UMS is not connected these raise
:class:`UMSLiveAttendanceUnavailable`, which the agent turns into a plain
"please connect UMS" answer - there is no demo data.
"""
from __future__ import annotations

from typing import Any

from app.services.schedule import freshness as _freshness
from app.ums.service import UMSLiveAttendanceUnavailable, ums_is_live, ums_playwright


def _require_ums(what: str) -> None:
    if not ums_is_live():
        raise UMSLiveAttendanceUnavailable(
            f"{what} come from UMS, so UMS must be connected and signed in. Click Connect UMS.",
            {},
        )


def get_timetable_tool(day: str | None = None) -> dict:
    """The student's weekly timetable, read live from UMS."""
    _require_ums("Your timetable and classes")
    live = ums_playwright.timetable()
    classes = [
        {
            "id": index,
            "day": item["day"],
            "time": item["time"],
            "end": item["end"],
            "subject": item["subject"],
            "room": item["room"],
            "type": item.get("type_label") or item.get("type") or "",
            "group": item.get("group") or "",
            "teacher": "",
        }
        for index, item in enumerate(live["classes"], start=1)
    ]
    if day:
        classes = [c for c in classes if c["day"].lower() == day.lower()]
    return {
        "classes": classes,
        "source": "UMS (live)",
        "live": True,
        "updated_at": live.get("updated_at"),
    }


def _as_announcement(index: int, record: dict[str, Any]) -> dict[str, Any]:
    text = record.get("body") or ""
    attachments = record.get("attachments") or []
    if attachments:
        names = ", ".join(a["name"] for a in attachments[:4])
        text = f"{text} [attachments: {names}]".strip()
    return _stamped({
        "id": index,
        "title": record.get("title") or "(untitled)",
        "date": record.get("date") or "",
        "reference": record.get("reference") or "",
        "channel": record.get("channel") or "",
        "tag": "UMS",
        "text": text,
        "important": False,
        "attachments": attachments,
        "links": record.get("links") or [],
    })


def get_announcements_tool(limit: int = 20) -> dict:
    """Announcements, read live from UMS, newest first."""
    _require_ums("Announcements")
    live = ums_playwright.announcements()
    return {
        "announcements": [
            _as_announcement(i, r) for i, r in enumerate(live["items"][:limit], start=1)
        ],
        "source": "UMS (live)",
        "live": True,
        "updated_at": live.get("updated_at"),
    }


def _stamped(record: dict[str, Any]) -> dict[str, Any]:
    """Add a normalised date and time to a notice or message.

    UMS prints its stamps several ways. Parsing them here means the model never
    reads a date itself, and a stamp that cannot be read comes back as
    date_iso=None rather than as a guess.
    """
    from app.services.schedule import parse_datetime

    stamp = parse_datetime(record.get("date"))
    return {
        **record,
        "date_iso": stamp["iso"] if stamp else None,
        "time": stamp["time"].strftime("%H:%M") if stamp and stamp["time"] else "",
        "when": stamp["readable"] if stamp else (record.get("date") or "no date given"),
        "date_readable": stamp["readable"] if stamp else "",
    }


def get_day_classes_tool(when: str = "today") -> dict:
    """The classes on one day. The day is resolved in Python, not by the model."""
    from app.services.schedule import classes_on, resolve_day, summarise_day, today_context

    resolved = resolve_day(when)
    if not resolved["understood"]:
        return {
            "understood": False,
            "asked": when,
            "message": (
                f"I could not work out which day {when!r} means. Ask for today, tomorrow, "
                "the day after tomorrow, a weekday name, or a date like 2026-09-11."
            ),
            **today_context(),
        }
    table = get_timetable_tool()
    items = classes_on(table["classes"], resolved["day"])
    return {
        "understood": True,
        "day": resolved["day"],
        "date": resolved["date"],
        "asked_for": resolved["label"],
        "count": len(items),
        "classes": items,
        "summary": summarise_day(resolved["day"], items),
        "source": table["source"],
        "live": table["live"],
        **_freshness(table.get("updated_at")),
        **today_context(),
    }


def get_class_at_tool(at: str, when: str = "today") -> dict:
    """Which class covers a given time - "what do I have at 1:40 today".

    The day, the 12-vs-24 hour reading of the time, and the start <= t < end
    comparison all happen here in code.
    """
    from app.services.schedule import class_at, resolve_day, today_context

    resolved = resolve_day(when)
    if not resolved["understood"]:
        return {"understood": False, "asked": when,
                "message": f"I could not work out which day {when!r} means.",
                **today_context()}

    table = get_timetable_tool()
    found = class_at(table["classes"], resolved["day"], at)
    if not found["readings"]:
        return {"understood": False, "asked": at,
                "message": f"I could not read {at!r} as a time. Try something like 1:40 pm or 13:40."}

    return {
        "understood": True,
        "day": resolved["day"],
        "date": resolved["date"],
        "asked_for": resolved["label"],
        "asked_time": found["asked_time"],
        "time_readings_tried": found["readings"],
        "matched": found["matched"],
        "classes": found["classes"],
        "class_before": found["before"],
        "class_after": found["after"],
        "classes_that_day": found["day_classes"],
        "source": table["source"],
        "live": table["live"],
        **_freshness(table.get("updated_at")),
        **today_context(),
    }


def get_next_class_tool() -> dict:
    """The next class from right now, looked up in code."""
    from app.services.schedule import next_class, today_context

    table = get_timetable_tool()
    upcoming = next_class(table["classes"])
    return {
        "found": upcoming is not None,
        "next_class": upcoming,
        "source": table["source"],
        "live": table["live"],
        **_freshness(table.get("updated_at")),
        **today_context(),
    }


def _matches(record: dict[str, Any], query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    haystack = " ".join(
        str(record.get(key) or "") for key in ("title", "text", "sender", "reference", "channel")
    ).lower()
    return all(word in haystack for word in needle.split())


def get_recent_announcements_tool(
    limit: int = 10, when: str | None = None, query: str | None = None
) -> dict:
    """Announcements narrowed in code before the model ever sees them.

    ``when`` accepts today/yesterday/a weekday/a date and filters on the notice's
    own date; notices whose date cannot be parsed are kept and flagged rather
    than silently dropped.
    """
    from app.services.schedule import resolve_day, today_context

    everything = get_announcements_tool(limit=200)
    items = everything["announcements"]

    day_filter = None
    undated = 0
    if when:
        resolved = resolve_day(when)
        if not resolved["understood"]:
            return {"understood": False, "asked": when,
                    "message": f"I could not work out which day {when!r} means.",
                    **today_context()}
        day_filter = resolved["date"]
        kept = []
        for item in items:
            # date_iso was parsed when the notice was read, in Python.
            if not item.get("date_iso"):
                undated += 1
                continue
            if item["date_iso"] == day_filter:
                kept.append(item)
        items = kept

    if query:
        items = [item for item in items if _matches(item, query)]

    return {
        "understood": True,
        "announcements": items[:limit],
        "total_matching": len(items),
        "filtered_by_day": day_filter,
        "undated_skipped": undated,
        "query": query or "",
        "source": everything["source"],
        "live": everything["live"],
        **_freshness(everything.get("updated_at")),
        **today_context(),
    }


def get_messages_tool(limit: int = 10, query: str | None = None, days: int | None = None) -> dict:
    """The student's UMS messages from the full message store.

    No query and no day range: the latest messages (cached by the background
    reader). With a query: UMS searches subject and text of the WHOLE history.
    With days: only messages from the last N days (paging back as needed).
    """
    from app.services.schedule import today_context

    if not ums_is_live():
        raise UMSLiveAttendanceUnavailable(
            "Messages come from your UMS inbox, so UMS must be connected and signed in. "
            "Click Connect UMS.",
            {},
        )
    limit = max(1, min(int(limit or 10), 100))
    days = max(1, min(int(days), 730)) if days else None
    query = (query or "").strip() or None

    latest = ums_playwright.messages()
    if query or days or limit > len(latest.get("items") or []):
        live = ums_playwright.search_messages(query or "", days=days, max_rows=max(limit, 20) if not days else 300)
        searched = (
            f"UMS searched the subject and text of all {latest.get('total_in_store') or 'your'} messages"
            if query else "messages read from the UMS message store, newest first"
        )
    else:
        live = latest
        searched = "the latest messages from the UMS message store"

    items = (live.get("items") or [])[:limit]
    # Tool results reach the model cut at ~20k characters. Share that between
    # the messages so a long list is never chopped off half-way (which also hid
    # the totals): few messages keep long texts, many get shorter previews.
    budget = max(240, min(4000, 13000 // max(1, len(items))))
    records = []
    for index, record in enumerate(items, start=1):
        text = record.get("body") or ""
        if len(text) > budget:
            text = text[:budget].rstrip() + " … (shortened - full text in UMS)"
        records.append(_stamped({
            "id": index,
            "title": record.get("title") or "(no subject)",
            "sender": record.get("sender") or "",
            "date": record.get("date") or "",
            "text": text,
            "attachments": record.get("attachments") or [],
            "links": (record.get("links") or [])[:3],
        }))
    # Summary first, messages last: if anything is ever cut, it is the tail.
    return {
        "total_in_inbox": latest.get("total_in_store") or len(latest.get("items") or []),
        # Only meaningful when something was searched or a day range was given.
        **({"total_matching": live.get("total_matching", len(live.get("items") or []))} if (query or days) else {}),
        "returned": len(records),
        "query": query or "",
        "days": days,
        "searched": searched,
        "messages": records,
        "source": "UMS (live)",
        "live": True,
        "updated_at": live.get("updated_at"),
        **_freshness(live.get("updated_at")),
        **today_context(),
    }


def get_leave_tool() -> dict:
    """Hostel leave balances. Read only - there is no apply-for-leave tool."""
    if not ums_is_live():
        raise UMSLiveAttendanceUnavailable(
            "Leave balances come from your UMS hostel leave page, so UMS must be connected "
            "and signed in. Click Connect UMS.",
            {},
        )
    from app.services.schedule import today_context
    from app.ums.leave import summarise

    live = ums_playwright.leave()
    return {
        "balances": live.get("balances", {}),
        "summary": summarise(live),
        "leave_types": live.get("leave_types", []),
        "term": (live.get("profile") or {}).get("term", ""),
        "hostel": (live.get("profile") or {}).get("hostel", ""),
        "room": (live.get("profile") or {}).get("room", ""),
        "recommending_authority": (live.get("profile") or {}).get("recommending_authority", ""),
        "sanctioning_authority": (live.get("profile") or {}).get("sanctioning_authority", ""),
        "read_only": True,
        "how_to_apply": (
            "CampusAI cannot submit a leave application. Open the CampusAI browser, go to "
            "Hostel Leave Application in UMS, and fill and submit it yourself."
        ),
        "source": "UMS (live)",
        "live": True,
        "updated_at": live.get("updated_at"),
        **_freshness(live.get("updated_at")),
        **today_context(),
    }


def draft_leave_tool(draft: dict[str, Any]) -> dict[str, Any]:
    """Validate a leave draft against the student's real balances and types.

    Reads UMS for the balances; writes nothing. There is no companion tool that
    submits or fills the form - that is a button the student presses.
    """
    balances: dict[str, Any] = {}
    leave_types: list[str] = []
    if ums_is_live():
        try:
            live = ums_playwright.leave()
            balances = live.get("balances", {})
            leave_types = live.get("leave_types", [])
        except UMSLiveAttendanceUnavailable:
            pass  # validate what we can; the balance check is simply skipped

    from app.ums.leave_draft import summarise_draft, validate_draft

    result = validate_draft(draft, balances, leave_types)
    result["summary"] = summarise_draft(result)
    result["can_submit_from_campusai"] = False
    result["next_step"] = (
        "CampusAI cannot submit this. Once the draft looks right, open Hostel Leave "
        "Application in UMS, fill it in, tick the acknowledgement and press Submit yourself."
    )
    result["leave_types"] = leave_types
    result["balances"] = balances
    return result
