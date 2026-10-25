"""Validation of a hostel leave draft, before anything touches UMS.

The language model collects the details; this module decides whether they are
usable. Every rule here is deterministic Python - dates, durations and balance
arithmetic are never left to the model, for the same reason attendance
percentages aren't.

A draft lives in the backend only. Nothing in this file writes to UMS.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

#: Accepted input formats, most explicit first. The model is told to send ISO.
INPUT_FORMATS = (
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M",
    "%d %b %Y %H:%M",
    "%d %B %Y %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y",
)

NIGHT = re.compile(r"night", re.I)
DAY = re.compile(r"\bday\b", re.I)


def parse_when(value: str) -> datetime | None:
    text = (value or "").strip().replace("  ", " ")
    if not text:
        return None
    for fmt in INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _kind_of(leave_type: str) -> str:
    """Which balance a leave type draws on."""
    if NIGHT.search(leave_type or ""):
        return "night"
    if DAY.search(leave_type or ""):
        return "day"
    return "leave"


def validate_draft(
    draft: dict[str, Any],
    balances: dict[str, dict[str, int]] | None = None,
    leave_types: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Check a draft and compute its cost. Returns errors rather than raising.

    ``{"ok", "errors", "warnings", "draft", "computed"}`` - ``computed`` carries
    the units used, the balance kind they come from, and what is left after.
    """
    errors: list[str] = []
    warnings: list[str] = []
    balances = balances or {}
    leave_types = leave_types or []
    now = now or datetime.now()

    leave_type = (draft.get("leave_type") or "").strip()
    if not leave_type:
        errors.append("Choose a leave type.")
    elif leave_types and leave_type not in leave_types:
        errors.append(
            f"{leave_type!r} is not a leave type your term offers. "
            f"Available: {', '.join(leave_types)}."
        )

    start = parse_when(draft.get("start", ""))
    end = parse_when(draft.get("end", ""))
    if not start:
        errors.append("Start date and time is missing or could not be read (use YYYY-MM-DD HH:MM).")
    if not end:
        errors.append("End date and time is missing or could not be read (use YYYY-MM-DD HH:MM).")

    reason = (draft.get("reason") or "").strip()
    if len(reason) < 5:
        errors.append("Give a reason for the leave (at least a short sentence).")

    place = (draft.get("visit_place") or "").strip()
    if not place:
        errors.append("Give the place you are visiting.")

    computed: dict[str, Any] = {}
    if start and end:
        if end <= start:
            errors.append("The leave must end after it starts.")
        else:
            kind = _kind_of(leave_type)
            nights = (end.date() - start.date()).days
            if kind == "day":
                if nights > 0:
                    errors.append(
                        "Day leave has to start and end on the same day. "
                        "For an overnight trip choose a night leave type."
                    )
                units, unit_name = 1, "day"
            elif kind == "night":
                if nights < 1:
                    errors.append(
                        "Night leave has to cover at least one night. "
                        "For a same-day trip choose a day leave type."
                    )
                units, unit_name = max(nights, 0), "night"
            else:
                units, unit_name = max(nights, 1), "day"

            balance = balances.get(kind) or {}
            available = balance.get("balance")
            computed = {
                "kind": kind,
                "units": units,
                "unit_name": unit_name,
                "hours": round((end - start).total_seconds() / 3600, 1),
                "available_before": available,
                "available_after": (available - units) if available is not None else None,
            }
            if available is not None and units > available:
                errors.append(
                    f"That is {units} {unit_name}(s) but you only have {available} "
                    f"{kind} leave(s) left."
                )
            if start < now:
                warnings.append("The start time is in the past.")
            if (end - start).days > 30:
                warnings.append("That is a long leave - check the dates are right.")

    clean = {
        "leave_type": leave_type,
        "start": start.strftime("%Y-%m-%d %H:%M") if start else "",
        "end": end.strftime("%Y-%m-%d %H:%M") if end else "",
        "visit_place": place[:200],
        "reason": reason[:500],
    }
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "draft": clean,
        "computed": computed,
    }


def summarise_draft(result: dict[str, Any]) -> str:
    """One line for the review card and for the agent to read back."""
    draft, computed = result["draft"], result.get("computed") or {}
    if not result["ok"]:
        return "; ".join(result["errors"])
    bits = [f"{draft['leave_type']} from {draft['start']} to {draft['end']}"]
    if computed.get("units") is not None:
        bits.append(f"{computed['units']} {computed['unit_name']}(s)")
    if computed.get("available_after") is not None:
        bits.append(f"{computed['available_after']} {computed['kind']} leave(s) left after this")
    return ", ".join(bits)


def format_for_ums(value: str, fmt: str) -> str:
    """Render a validated datetime in whatever format the UMS field expects."""
    parsed = parse_when(value)
    return parsed.strftime(fmt) if parsed else ""
