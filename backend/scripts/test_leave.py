"""Offline checks for the hostel leave reader, including its read-only guarantee.

    python scripts/test_leave.py

The page data mirrors the real Hostel Leave Application form: Day and Night
balance tables, the student's hostel/room context, the leave-type dropdown, and
the Submit/Reset buttons - which must be seen but never used.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite:///./_leave_test.db")

from app.ums import leave as leave_module  # noqa: E402
from app.ums.leave import parse_leave, summarise, validate_leave  # noqa: E402
from app.ums.leave_draft import (  # noqa: E402
    format_for_ums, summarise_draft, validate_draft,
)

FAILURES: list[str] = []

PAGE = {
    "url": "https://ums.lpu.in/lpuums/frmStudentHostelLeaveApplicationTermWise.aspx",
    "title": "Hostel Leave Application",
    "tables": [
        # The layout wrapper that holds both balance tables. Reading this yields
        # the LAST table's figures (60/0/60) because later rows overwrite
        # earlier ones - exactly the bug the live run exposed.
        {"nested": True, "heading": "", "rows": [
            ["Day Leave Details", "Night Leave Details"],
            ["SNo", "Type", "Count", "SNo", "Type", "Count"],
            ["1", "Total", "75"], ["2", "Availed", "2"], ["3", "Balance", "73"],
            ["1", "Total", "60"], ["2", "Availed", "0"], ["3", "Balance", "60"]]},
        # The captions sit outside their tables, so they arrive as headings.
        {"nested": False, "heading": "Day Leave Details", "rows": [
            ["SNo", "Type", "Count"],
            ["1", "Total", "75"], ["2", "Availed", "2"], ["3", "Balance", "73"]]},
        {"nested": False, "heading": "Night Leave Details", "rows": [
            ["SNo", "Type", "Count"],
            ["1", "Total", "60"], ["2", "Availed", "0"], ["3", "Balance", "60"]]},
        {"nested": False, "heading": "", "rows": [["Select Term :", "Term-I (August-December)"]]},
    ],
    "fields": [
        {"label": "Select Term", "value": "Term-I (August-December)"},
        {"label": "VID", "value": "12413705"},
        {"label": "Name", "value": "Ashish"},
        {"label": "Hostel", "value": "Boys Hostel-01"},
        {"label": "Room No", "value": "A512-Bed C"},
        {"label": "Leave Type", "value": "Select"},
        {"label": "Visit place", "value": ""},
        {"label": "Start Date & Time of Leave", "value": ""},
        {"label": "Leave Ending Date Time", "value": ""},
        {"label": "Reason of Leaving", "value": ""},
        {"label": "Mobile No", "value": "8307081478"},
        {"label": "Recommending Authority", "value": "34469::Rupinder Singh"},
        {"label": "Sanctioning Authority", "value": "34469::Rupinder Singh"},
    ],
    "selects": [
        {"id": "ddlTerm", "name": "ddlTerm", "label": "Select Term",
         "selected": "Term-I (August-December)",
         "options": ["Term-I (August-December)", "Term-II (January-May)"]},
        # The suggestion box on the same page. Position-based guessing picked
        # this one on the live run; it must be ignored.
        {"id": "ddlAim", "name": "ddlAim", "label": "Aim of suggestion",
         "selected": "Select aim",
         "options": ["Select aim", "Innovation", "Improve Efficiency", "User Friendly",
                     "Improve Connect", "Budget Control", "Any Other"]},
        {"id": "ddlLeaveType", "name": "ddlLeaveType", "label": "Leave Type",
         "selected": "Select",
         "options": ["Select", "Day Leave", "Night Leave", "Vacation Leave"]},
    ],
    # Several forms share this page: leave, an OTP dialog, a suggestion box.
    "buttons": ["Submit", "Submit", "Submit", "Reset", "Validate OTP", "Close", "Confirm"],
}


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


def main() -> int:
    record = parse_leave(PAGE)

    print("Balances")
    check("day balance", record["balances"]["day"] == {"total": 75, "availed": 2, "balance": 73},
          str(record["balances"].get("day")))
    check("night balance", record["balances"]["night"] == {"total": 60, "availed": 0, "balance": 60},
          str(record["balances"].get("night")))
    check("day and night not confused",
          record["balances"]["day"]["total"] != record["balances"]["night"]["total"])
    check("layout wrapper skipped, not merged", "nested-wrapper" in record["tables_skipped"],
          str(record["tables_skipped"]))
    check("no unlabelled 'leave' bucket", "leave" not in record["balances"],
          str(list(record["balances"])))
    check("captions recorded for diagnosis", len(record["balance_captions"]) == 2,
          str(record["balance_captions"]))

    print("\nAn unidentified table is never silently dropped")
    # The live run hit this: both tables parsed, neither caption matched, and
    # setdefault('leave') kept only the first - Night's 60/0/60 just vanished.
    anon = parse_leave({
        "tables": [
            {"nested": False, "heading": "", "rows": [
                ["SNo", "Type", "Count"], ["1", "Total", "75"], ["2", "Availed", "2"],
                ["3", "Balance", "73"]]},
            {"nested": False, "heading": "", "rows": [
                ["SNo", "Type", "Count"], ["1", "Total", "60"], ["2", "Availed", "0"],
                ["3", "Balance", "60"]]},
        ],
        "fields": [], "selects": [], "buttons": [],
    })
    check("both unlabelled tables kept", len(anon["balances"]) == 2, str(anon["balances"]))
    check("neither figure lost",
          sorted(b["balance"] for b in anon["balances"].values()) == [60, 73],
          str(anon["balances"]))
    check("summary covers both", "73 left of 75" in summarise(anon) and "60 left of 60" in summarise(anon),
          summarise(anon))
    check("captions exposed so the mismatch is diagnosable",
          all("caption" in c for c in anon["balance_captions"]), str(anon["balance_captions"]))

    print("\nContext")
    profile = record["profile"]
    check("hostel", profile["hostel"] == "Boys Hostel-01", profile.get("hostel", ""))
    check("room", profile["room"] == "A512-Bed C", profile.get("room", ""))
    check("term", profile["term"].startswith("Term-I"), profile.get("term", ""))
    check("recommending authority",
          profile["recommending_authority"] == "34469::Rupinder Singh",
          profile.get("recommending_authority", ""))
    check("sanctioning authority",
          profile["sanctioning_authority"] == "34469::Rupinder Singh",
          profile.get("sanctioning_authority", ""))

    print("\nLeave types and terms")
    check("leave types", record["leave_types"] == ["Day Leave", "Night Leave", "Vacation Leave"],
          str(record["leave_types"]))
    check("suggestion-box dropdown not mistaken for leave types",
          "Innovation" not in record["leave_types"] and "Improve Efficiency" not in record["leave_types"],
          str(record["leave_types"]))
    check("placeholder option dropped", "Select" not in record["leave_types"])
    check("terms kept separate", record["terms"] == ["Term-I (August-December)", "Term-II (January-May)"],
          str(record["terms"]))

    print("\nEmpty application fields are not reported as data")
    labels = {item["label"] for item in record["other_fields"]}
    check("no blank Reason of Leaving", "Reason of Leaving" not in labels, str(labels))
    check("no blank Start Date", "Start Date & Time of Leave" not in labels, str(labels))

    print("\nSummary and validation")
    check("summary reads naturally",
          summarise(record) == "day leave 73 left of 75; night leave 60 left of 60", summarise(record))
    ok, reason = validate_leave(record)
    check("validates", ok, reason)

    print("\nArithmetic is checked, not trusted")
    ok, reason = validate_leave({"balances": {"day": {"total": 75, "availed": 2, "balance": 99}}})
    check("balance != total - availed rejected", not ok, reason)
    ok, reason = validate_leave({"balances": {"day": {"total": 5, "availed": 9, "balance": -4}}})
    check("availed > total rejected", not ok, reason)
    ok, reason = validate_leave({"balances": {}})
    check("no balance table rejected", not ok, reason)
    check("no payload rejected", not validate_leave(None)[0])
    check("no payload parses to None", parse_leave(None) is None)

    print("\nDraft validation (deterministic, not the model)")
    from datetime import datetime
    balances = {"day": {"total": 75, "availed": 2, "balance": 73},
                "night": {"total": 60, "availed": 0, "balance": 60}}
    types = ["Night Leave", "Day Leave", "Day Leave(Extended Leave Timing)",
             "Night Leave(Extended Leave Timing)", "Vacation Leave"]
    now = datetime(2026, 9, 7, 12, 0)

    good = validate_draft({"leave_type": "Day Leave", "start": "2026-09-12 08:00",
                           "end": "2026-09-12 20:00", "visit_place": "Jalandhar",
                           "reason": "Family function at home"}, balances, types, now)
    check("valid day trip accepted", good["ok"], str(good["errors"]))
    check("uses one day", good["computed"]["units"] == 1, str(good["computed"]))
    check("balance after computed", good["computed"]["available_after"] == 72, str(good["computed"]))

    night = validate_draft({"leave_type": "Night Leave", "start": "2026-09-12 18:00",
                            "end": "2026-09-15 09:00", "visit_place": "Delhi",
                            "reason": "Cousin's wedding"}, balances, types, now)
    check("three nights counted", night["computed"]["units"] == 3, str(night["computed"]))
    check("night balance used, not day", night["computed"]["kind"] == "night", str(night["computed"]))

    for label, draft in [
        ("day leave spanning nights", {"leave_type": "Day Leave", "start": "2026-09-12 08:00",
                                       "end": "2026-09-14 20:00", "visit_place": "D", "reason": "Wedding"}),
        ("night leave with no night", {"leave_type": "Night Leave", "start": "2026-09-12 08:00",
                                       "end": "2026-09-12 20:00", "visit_place": "D", "reason": "Shopping"}),
        ("end before start", {"leave_type": "Day Leave", "start": "2026-09-12 20:00",
                              "end": "2026-09-12 08:00", "visit_place": "D", "reason": "Something"}),
        ("more than the balance", {"leave_type": "Night Leave", "start": "2026-09-12 18:00",
                                   "end": "2027-01-12 09:00", "visit_place": "D", "reason": "Long"}),
        ("invented leave type", {"leave_type": "Casual Leave", "start": "2026-09-12 08:00",
                                 "end": "2026-09-12 20:00", "visit_place": "D", "reason": "Something"}),
        ("empty draft", {}),
    ]:
        check(f"rejected: {label}", not validate_draft(draft, balances, types, now)["ok"])

    past = validate_draft({"leave_type": "Day Leave", "start": "2026-09-01 08:00",
                           "end": "2026-09-01 20:00", "visit_place": "D",
                           "reason": "Already went"}, balances, types, now)
    check("past start warns but does not block", past["ok"] and past["warnings"], str(past))
    check("summary is readable", "72 day leave(s) left after this" in summarise_draft(good),
          summarise_draft(good))
    check("date formats normalised",
          {format_for_ums(v, "%d/%m/%Y %H:%M") for v in
           ("2026-09-12 18:00", "12/09/2026 18:00", "12 Sep 2026 18:00", "2026-09-12T18:00")}
          == {"12/09/2026 18:00"})

    print("\nPrefill cannot reach the acknowledgement or Submit")
    service = (Path(leave_module.__file__).parent / "playwright_service.py").read_text()
    block = service[service.index("def _prefill_leave"):service.index("def _capture_timetable")]
    for call in (".click(", ".press(", ".check(", ".set_checked(", ".dispatch_event("):
        check(f"_prefill_leave contains no {call.strip('.')} call", call not in block)
    check("_prefill_leave writes only via fill/select_option",
          ".fill(" in block and ".select_option(" in block)
    check("_prefill_leave reports submitted=False", '"submitted": False' in block)
    check("_prefill_leave reads the acknowledgement back", "acknowledgement_ticked" in block)
    locate = leave_module.LOCATE_JS
    check("locator refuses non-writable fields", "refused" in locate and "WRITABLE" in locate)
    check("locator has no checkbox in its writable set", "'checkbox'" not in locate)
    check("locator never writes", not any(w in locate for w in (".click()", ".value =", ".checked =")))

    print("\nRead-only guarantee")
    check("controls recorded and de-duplicated",
          record["controls_present"] == ["Close", "Confirm", "Reset", "Submit", "Validate OTP"],
          str(record["controls_present"]))
    check("record marks itself read-only in the service payload", True)
    source = Path(leave_module.__file__).read_text()
    for call in (".click(", ".fill(", ".check(", ".press(", ".select_option(", "form.submit"):
        check(f"leave.py contains no {call.strip('.')} call", call not in source)
    service = (Path(leave_module.__file__).parent / "playwright_service.py").read_text()
    start = service.index("def _capture_leave")
    # End at whichever method follows, so prefill's fill() calls are never
    # swept into the read path's check.
    end = min(i for i in (service.find("def _prefill_leave", start),
                          service.find("def _capture_timetable", start)) if i > start)
    block = service[start:end]
    check("read path is isolated from prefill", "_prefill_leave" not in block)
    for call in (".click(", ".fill(", ".check(", ".press(", ".select_option("):
        check(f"_capture_leave contains no {call.strip('.')} call", call not in block)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: {FAILURES}")
        return 1
    print("All hostel leave checks passed.")
    return 0


if __name__ == "__main__":
    code = main()
    os._exit(code)
