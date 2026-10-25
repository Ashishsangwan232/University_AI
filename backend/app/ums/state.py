"""Explicit UMS session state machine.

The whole point of this module is that "session started", "authenticated" and
"attendance extracted" are three *different* facts. Every one of them is a
distinct state, and the backend refuses to infer one from another.
"""
from __future__ import annotations

from enum import Enum


class UMSState(str, Enum):
    IDLE = "IDLE"
    BROWSER_STARTED = "BROWSER_STARTED"
    AUTHENTICATION_PENDING = "AUTHENTICATION_PENDING"
    AUTHENTICATED = "AUTHENTICATED"
    ATTENDANCE_NAVIGATION_STARTED = "ATTENDANCE_NAVIGATION_STARTED"
    ATTENDANCE_PAGE_FOUND = "ATTENDANCE_PAGE_FOUND"
    ATTENDANCE_TABLE_FOUND = "ATTENDANCE_TABLE_FOUND"
    ATTENDANCE_PARSED = "ATTENDANCE_PARSED"
    ATTENDANCE_VALIDATED = "ATTENDANCE_VALIDATED"
    ATTENDANCE_STORED = "ATTENDANCE_STORED"
    READY = "READY"


#: Ordering used only for reporting "how far did we get".
STATE_ORDER: list[UMSState] = [
    UMSState.IDLE,
    UMSState.BROWSER_STARTED,
    UMSState.AUTHENTICATION_PENDING,
    UMSState.AUTHENTICATED,
    UMSState.ATTENDANCE_NAVIGATION_STARTED,
    UMSState.ATTENDANCE_PAGE_FOUND,
    UMSState.ATTENDANCE_TABLE_FOUND,
    UMSState.ATTENDANCE_PARSED,
    UMSState.ATTENDANCE_VALIDATED,
    UMSState.ATTENDANCE_STORED,
    UMSState.READY,
]


def state_rank(state: UMSState | str) -> int:
    try:
        return STATE_ORDER.index(UMSState(state))
    except ValueError:
        return -1


class UMSLiveAttendanceUnavailable(RuntimeError):
    """Raised whenever live UMS attendance cannot be produced.

    Carries the diagnostics snapshot so the caller can tell the student exactly
    which state the pipeline stopped in. This exception must never be swallowed
    into a silent PostgreSQL fallback.
    """

    def __init__(self, message: str, diagnostics: dict | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or {}
