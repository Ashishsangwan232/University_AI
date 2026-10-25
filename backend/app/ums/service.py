"""Single access point for the Playwright-only UMS session.

There is no bridge, no extension, no content script, no heartbeat, no snapshot,
and no bridge token anywhere in CampusAI. This module exists so that callers
have exactly one import path, and so the old ``bridge_connected`` key can never
silently evaluate to ``False`` again: :func:`ums_status` always returns both
``browser_connected`` and the ``bridge_connected`` alias.
"""
from __future__ import annotations

from typing import Any

from app.ums.playwright_service import ums_playwright
from app.ums.state import UMSLiveAttendanceUnavailable, UMSState

__all__ = [
    "ums_playwright",
    "ums_announcements",
    "ums_timetable",
    "ums_leave",
    "ums_messages",
    "ums_student_profile",
    "ums_status",
    "ums_diagnostics",
    "ums_is_live",
    "ums_live_attendance",
    "UMSLiveAttendanceUnavailable",
    "UMSState",
]


def ums_status() -> dict[str, Any]:
    return ums_playwright.status()


def ums_diagnostics() -> dict[str, Any]:
    return ums_playwright.diagnostics()


def ums_is_live(status: dict[str, Any] | None = None) -> bool:
    """True when a real, authenticated UMS browser session exists.

    This is the one predicate that decides live-vs-demo. It checks the browser
    attachment and the authentication flag separately, because "started" is not
    "authenticated".
    """
    status = status or ums_status()
    return bool(status.get("browser_connected") and status.get("authenticated"))


def ums_live_attendance() -> dict[str, Any]:
    """Live attendance, or :class:`UMSLiveAttendanceUnavailable`. Never demo data."""
    return ums_playwright.attendance()


def ums_announcements(force: bool = False) -> dict[str, Any]:
    """Live announcements, or :class:`UMSLiveAttendanceUnavailable`."""
    return ums_playwright.announcements(force=force)


def ums_timetable(force: bool = False) -> dict[str, Any]:
    """Live timetable, or :class:`UMSLiveAttendanceUnavailable`."""
    return ums_playwright.timetable(force=force)


def ums_leave(force: bool = False) -> dict[str, Any]:
    """Hostel leave balances, read only. Never applies for anything."""
    return ums_playwright.leave(force=force)


def ums_messages(force: bool = False) -> dict[str, Any]:
    """Live messages, or :class:`UMSLiveAttendanceUnavailable`."""
    return ums_playwright.messages(force=force)


def ums_student_profile(force: bool = False) -> dict[str, Any]:
    """The student's real identity from UMS, read only."""
    return ums_playwright.student_profile(force=force)
