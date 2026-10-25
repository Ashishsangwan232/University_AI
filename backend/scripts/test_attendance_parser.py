"""Offline checks for the UMS attendance parser.

Run from the backend directory:

    python scripts/test_attendance_parser.py

These use realistic ASP.NET GridView row shapes, not live UMS output. They
verify the parser, not the portal.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ums.attendance_parser import (  # noqa: E402
    DETAIL_ID, parse_attendance_rows, parse_detail_tables, validate_attendance, validate_detail,
)

EXPECTED_COURSES = 6
EXPECTED = {"delivered": 72, "attended": 69}

COMBINED_COLUMN = [
    ["Sr.No.", "Course", "Total Delivered", "Total Attended", "Total Percentage", "Last Attended"],
    ["1", "CSE329:PRELUDE TO COMPETITIVE CODING", "9", "9", "100 %", "05 Sep 2026"],
    ["2", "CSE330:COMPETITIVE CODING APPROACHES-TECHNIQUES", "9", "7", "78 %", "04 Sep 2026"],
    ["3", "CSE408:DESIGN AND ANALYSIS OF ALGORITHMS", "9", "9", "100 %", "05 Sep 2026"],
    ["4", "CSE471:DEEP LEARNING FOR COMPUTER VISION", "14", "14", "100 %", "05 Sep 2026"],
    ["5", "CSE472:DEEP LEARNING FOR NATURAL LANGUAGE PROCESSING", "16", "16", "100 %", "05 Sep 2026"],
    ["6", "INT373:AGILE DRIVEN DEVELOPMENT AND PROJECT MANAGEMENT", "15", "14", "93 %", "03 Sep 2026"],
    ["", "Total", "72", "69", "96 %", ""],
]

SPLIT_COLUMNS = [
    ["S.No", "Course Code", "Course Description", "Classes Delivered", "Classes Attended", "Attendance %"],
    ["1", "CSE329", "PRELUDE TO COMPETITIVE CODING", "9", "9", "100.00"],
    ["2", "CSE330", "COMPETITIVE CODING APPROACHES-TECHNIQUES", "9", "7", "77.78"],
    ["3", "CSE408", "DESIGN AND ANALYSIS OF ALGORITHMS", "9", "9", "100.00"],
    ["4", "CSE471", "DEEP LEARNING FOR COMPUTER VISION", "14", "14", "100.00"],
    ["5", "CSE472", "DEEP LEARNING FOR NATURAL LANGUAGE PROCESSING", "16", "16", "100.00"],
    ["6", "INT373", "AGILE DRIVEN DEVELOPMENT AND PROJECT MANAGEMENT", "15", "14", "93.33"],
    ["", "", "Aggregate", "72", "69", "95.83"],
]

# The real LPU UMS shape: (T,L,P) split columns, seen in production diagnostics.
TLP_COLUMNS = [
    ["Course", "Last Attended", "Duty Leave", "Total Delivered (T,L,P)",
     "Total Attended (T,L,P)", "Total Percentage"],
    ["CSE329:PRELUDE TO COMPETITIVE CODING", "05 Sep 2026", "0", "9", "9", "100 %"],
    ["CSE330:COMPETITIVE CODING APPROACHES-TECHNIQUES", "04 Sep 2026", "0", "9", "7", "78 %"],
    ["CSE408:DESIGN AND ANALYSIS OF ALGORITHMS", "05 Sep 2026", "0", "9", "9", "100 %"],
    ["CSE471:DEEP LEARNING FOR COMPUTER VISION", "05 Sep 2026", "0", "9,0,5", "9,0,5", "100 %"],
    ["CSE472:DEEP LEARNING FOR NATURAL LANGUAGE PROCESSING", "05 Sep 2026", "0", "16", "16", "100 %"],
    ["INT373:AGILE DRIVEN DEVELOPMENT AND PROJECT MANAGEMENT", "03 Sep 2026", "0", "15", "14", "93 %"],
]

NO_AGGREGATE_ROW = COMBINED_COLUMN[:-1]

NAVIGATION_TABLE = [
    ["Home", "My Academics", "Attendance", "Examination", "Logout"],
    ["Student Dashboard", "", "", "", ""],
]

LAYOUT_TABLE = [
    ["Welcome, Student"],
    ["Your attendance summary is available under My Academics."],
]

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


def check_table(name: str, rows: list[list[str]], expect_aggregate: dict) -> None:
    print(f"\n{name}")
    parsed = parse_attendance_rows(rows)
    check("parsed", parsed is not None)
    if parsed is None:
        return
    check(
        f"{EXPECTED_COURSES} courses",
        len(parsed["courses"]) == EXPECTED_COURSES,
        f"got {len(parsed['courses'])}",
    )
    agg = parsed["aggregate"]
    check(
        f"aggregate {expect_aggregate}",
        agg["delivered"] == expect_aggregate["delivered"] and agg["attended"] == expect_aggregate["attended"],
        f"got {agg}",
    )
    ok, reason = validate_attendance(parsed)
    check("validates", ok, reason)
    codes = [c["code"] for c in parsed["courses"]]
    check(
        "course codes extracted",
        codes == ["CSE329", "CSE330", "CSE408", "CSE471", "CSE472", "INT373"],
        f"got {codes}",
    )
    first = parsed["courses"][0]
    check("first row 9/9", first["delivered"] == 9 and first["attended"] == 9, f"got {first}")
    second = parsed["courses"][1]
    check("second row 9/7", second["delivered"] == 9 and second["attended"] == 7, f"got {second}")


def main() -> int:
    check_table("Combined code:description column", COMBINED_COLUMN, EXPECTED)
    check_table("Separate code / description columns", SPLIT_COLUMNS, EXPECTED)
    check_table("No aggregate row (computed)", NO_AGGREGATE_ROW, EXPECTED)
    # 9,0,5 is a (T,L,P) breakdown = 14 delivered, so the totals stay 72/69.
    check_table("Real UMS (T,L,P) split columns", TLP_COLUMNS, EXPECTED)

    print("\nNon-attendance tables must be rejected")
    check("navigation table rejected", parse_attendance_rows(NAVIGATION_TABLE) is None)
    check("layout table rejected", parse_attendance_rows(LAYOUT_TABLE) is None)
    check("empty table rejected", parse_attendance_rows([]) is None)

    print("\nValidation must reject impossible numbers")
    bad = {
        "courses": [{"course": "X", "code": "X", "name": "X", "delivered": 5, "attended": 9, "percentage": 180}],
        "aggregate": {"delivered": 5, "attended": 9, "percentage": 180},
    }
    ok, reason = validate_attendance(bad)
    check("attended > delivered rejected", not ok, reason)

    mismatched = {
        "courses": [{"course": "X", "code": "X", "name": "X", "delivered": 10, "attended": 5, "percentage": 50}],
        "aggregate": {"delivered": 72, "attended": 69, "percentage": 96},
    }
    ok, reason = validate_attendance(mismatched)
    check("aggregate/sum mismatch rejected", not ok, reason)

    return 1 if FAILURES else 0


DETAIL_BLOCKS = [
    {"id": "collapseCSE329", "selector": "#collapseCSE329", "rows": [
        ["Date", "Time", "Type", "Attendance", "Name", "Block Reason"],
        ["Sep 5, 2026", "09:00-10:00", "L", "Present", "Dr. Isha", ""],
        ["Sep 3, 2026", "09:00-10:00", "L", "Absent", "Dr. Isha", "Late entry"],
        ["Sep 1, 2026", "09:00-10:00", "P", "Present", "Dr. Isha", ""]]},
    {"id": "collapseINT373", "selector": "#collapseINT373", "rows": [
        ["Date", "Time", "Type", "Attendance", "Name", "Block Reason"],
        ["Sep 4, 2026", "11:00-12:00", "L", "Absent", "Prof. Rao", ""]]},
    # UMS renders some collapsibles twice; the shorter copy must not win.
    {"id": "collapseCSE329", "selector": "#collapseCSE329", "rows": [
        ["Date", "Time", "Type", "Attendance", "Name", "Block Reason"],
        ["Sep 5, 2026", "09:00-10:00", "L", "Present", "Dr. Isha", ""]]},
    # a non-attendance table inside a collapsible
    {"id": "collapseNav", "selector": "#collapseNav", "rows": [["Home", "Logout"], ["a", "b"]]},
]


def check_attendance_detail() -> None:
    """The class-by-class log in the modal's second tab."""
    print("\nCourse code from the collapsible id")
    for element_id, expected in [
        ("collapseCSE329", "CSE329"), ("collapseINT373", "INT373"),
        ("collapse", None), ("tabX", None),
    ]:
        match = DETAIL_ID.search(element_id)
        found = match.group(1) if match else None
        # Case-sensitive: with IGNORECASE this yields "SECSE329".
        check(f"{element_id!r} -> {found!r}", found == expected, f"expected {expected!r}")

    print("\nClass-by-class parsing")
    courses = parse_detail_tables(DETAIL_BLOCKS)
    check("two courses parsed", set(courses) == {"CSE329", "INT373"}, str(set(courses)))
    check("nav table ignored", "NAV" not in courses and len(courses) == 2)
    cse = courses["CSE329"]
    check("fullest duplicate kept", cse["recorded"] == 3, str(cse["recorded"]))
    check("present counted", cse["present"] == 2, str(cse["present"]))
    check("absent counted", cse["absent"] == 1, str(cse["absent"]))
    check("absence reason kept",
          any(e["reason"] == "Late entry" for e in cse["entries"]), str(cse["entries"]))
    check("class type kept", cse["entries"][2]["type"] == "P", cse["entries"][2]["type"])
    ok, reason = validate_detail(courses)
    check("detail validates", ok, reason)
    check("empty detail rejected", not validate_detail({})[0])


def check_candidate_ranking() -> None:
    """A UMS dashboard has several 'attendance' controls; only some are right."""
    from app.ums.navigation import rank_candidates, score_candidate

    cases = [
        ("wanted", {"tag": "a", "text": "Attendance Summary", "visible": True,
                    "href": "frmStudentCourseWiseAttendanceSummary.aspx", "onclick": "", "id": ""}),
        ("wanted", {"tag": "a", "text": "Attendance", "visible": True,
                    "href": "javascript:__doPostBack('ctl00$lnkAtt','')", "onclick": "", "id": "lnkAttendance"}),
        ("wanted", {"tag": "a", "text": "My Attendance", "visible": True,
                    "href": "/lpuums/StudentAttendance.aspx", "onclick": "", "id": ""}),
        ("rejected", {"tag": "a", "text": "Event QR Attendance", "visible": True,
                      "href": "https://studentums.lpu.in/dashboard/EventQRAttendance", "onclick": "", "id": ""}),
        ("rejected", {"tag": "a", "text": "Mark Attendance", "visible": True,
                      "href": "/biometric", "onclick": "", "id": ""}),
        ("rejected", {"tag": "a", "text": "Attendance Correction Request", "visible": True,
                      "href": "/request", "onclick": "", "id": ""}),
        ("rejected", {"tag": "a", "text": "Attendance", "visible": True,
                      "href": "https://other.example.com/attendance", "onclick": "", "id": ""}),
    ]
    print("\nAttendance control ranking (only 'wanted' may be clicked)")
    for expectation, item in cases:
        score = score_candidate(item)
        check(
            f"{expectation:<8} score={score:>3}  {item['text']!r}",
            (score >= 1) == (expectation == "wanted"),
        )

    # The real LPU dashboard: everything that scores well is hidden inside a
    # closed modal or a collapsed menu. The only clickable control is the tile
    # whose onclick loads the panel, so it must rank first.
    dashboard = [
        {"tag": "a", "text": "Attendance Summary", "href": "#firstFull",
         "onclick": "", "id": "first-tab", "visible": False},
        {"tag": "li", "text": "Attendance Summary", "href": "", "onclick": "", "id": "", "visible": False},
        {"tag": "a", "text": "View Attendance", "href": "Reports/rptCourseWiseStudentAttendance.aspx",
         "onclick": "", "id": "", "visible": False},
        {"tag": "a", "text": "Examination Attendance", "href": "frmStudentExamAttendanceDisplay.aspx",
         "onclick": "", "id": "", "visible": False},
        {"tag": "div", "text": "ATTENDANCE : 97%", "href": "", "onclick": "getAtt()",
         "id": "AttPercent", "visible": True},
    ]
    ranked = rank_candidates(dashboard)
    print("\nReal LPU dashboard ordering")
    for item in ranked:
        print(f"    visible={str(item['visible']):<5} score={item['score']:>3}  {item['text']!r}")
    check("the AJAX tile ranks first", ranked[0]["id"] == "AttPercent", f"got {ranked[0]['text']!r}")
    check("the tile is clickable", ranked[0]["score"] >= 1, f"score {ranked[0]['score']}")
    clickable = [i for i in ranked if i["visible"] and i["score"] >= 1]
    check("exactly one clickable control", len(clickable) == 1, f"got {len(clickable)}")


def run_all() -> int:
    code = main()
    check_attendance_detail()
    check_candidate_ranking()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: {FAILURES}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
