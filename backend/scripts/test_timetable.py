"""Offline checks for the UMS timetable parser.

    python scripts/test_timetable.py

The primary case is the exact text the live #timetable container produced, so
this verifies the parser against real output rather than an invented shape.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite:///./_timetable_test.db")

from app.ums.timetable import (  # noqa: E402
    group_by_day, parse_timetable, validate_timetable,
)

FAILURES: list[str] = []

# Captured from frmMyCurrentTimeTable.aspx after GetTimeTableData1() ran.
LIVE_TEXT = (
    "Monday 10:20 - 11:10 33-301 - L - CSE472 K2EM001 11:10 -12:00 33-301 - L - CSE472 K2EM001"
)

MULTI_DAY = (
    "Monday 10:20 - 11:10 33-301 - L - CSE472 K2EM001 11:10 -12:00 33-301 - L - CSE472 K2EM001 "
    "Tuesday 09:30 - 10:20 26-305 - P - CSE471 K2EM001 "
    "Wednesday 08:40 - 09:30 33-201 - T - INT373 K2EM001 "
    "Thursday "
    "Friday 14:00 - 14:50 26-306 - L - CSE408 K2EM001"
)

PER_LINE = [
    "Monday",
    "10:20 - 11:10 33-301 - L - CSE472 K2EM001",
    "11:10 - 12:00 33-302 - P - CSE471 K2EM001",
]


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


def main() -> int:
    print("The exact text the live page produced")
    live = parse_timetable({"text": LIVE_TEXT, "lines": [LIVE_TEXT], "children": 5})
    check("two slots parsed", len(live) == 2, f"got {len(live)}")
    first = live[0]
    check("day", first["day"] == "Monday", first["day"])
    check("start/end", (first["time"], first["end"]) == ("10:20", "11:10"), str(first))
    check("room with its hyphen", first["room"] == "33-301", first["room"])
    check("class type expanded", first["type_label"] == "Lecture", first["type_label"])
    check("course code", first["subject"] == "CSE472", first["subject"])
    check("group", first["group"] == "K2EM001", first["group"])
    # UMS writes "11:10 -12:00" with no space before the dash.
    check("inconsistent dash spacing handled",
          (live[1]["time"], live[1]["end"]) == ("11:10", "12:00"), str(live[1]))
    check("live text validates", validate_timetable(live)[0])

    print("\nSeveral days, one of them empty")
    week = parse_timetable({"text": MULTI_DAY})
    check("five slots", len(week) == 5, f"got {len(week)}")
    grouped = group_by_day(week)
    check("grouped in weekday order",
          list(grouped) == ["Monday", "Tuesday", "Wednesday", "Friday"], str(list(grouped)))
    check("empty day contributes nothing", "Thursday" not in grouped)
    check("practical recognised", week[2]["type_label"] == "Practical", week[2]["type_label"])
    check("tutorial recognised", week[3]["type_label"] == "Tutorial", week[3]["type_label"])

    print("\nOne slot per line renders the same result")
    lines = parse_timetable({"lines": PER_LINE, "text": " ".join(PER_LINE)})
    check("two slots", len(lines) == 2, f"got {len(lines)}")
    check("second room", lines[1]["room"] == "33-302", lines[1]["room"])

    print("\nDuplicates from reading the container twice")
    doubled = parse_timetable({"text": f"{LIVE_TEXT} {LIVE_TEXT}"})
    check("exact duplicates dropped", len(doubled) == 2, f"got {len(doubled)}")

    print("\nNothing is invented")
    check("no payload", parse_timetable(None) == [])
    check("empty text", parse_timetable({"text": ""}) == [])
    check("prose only", parse_timetable({"text": "No timetable has been published yet."}) == [])
    check("impossible clock time rejected",
          parse_timetable({"text": "Monday 99:99 - 10:10 33-301 - L - CSE472"}) == [])
    ok, reason = validate_timetable([])
    check("empty result rejected by validation", not ok, reason)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: {FAILURES}")
        return 1
    print("All timetable checks passed.")
    return 0


if __name__ == "__main__":
    code = main()
    os._exit(code)
