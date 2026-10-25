"""Offline checks for the UMS site map and its crawl-safety rules.

    python scripts/test_site_map.py

Uses a synthetic UMS-shaped DOM dump. Verifies that links are tagged to the
right feature, that anything that could change the portal is flagged as an
action and never auto-visited, and that registration numbers are masked.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite:///./_site_map_test.db")

from app.ums.site_map import build, is_action, redact  # noqa: E402

FAILURES: list[str] = []

FRAMES = [
    {
        "url": "https://ums.lpu.in/lpuums/StudentDashboard.aspx",
        "title": "Student Dashboard",
        "links": [
            {"text": "View Attendance", "href": "Reports/rptCourseWiseStudentAttendance.aspx",
             "id": "", "section": "Academics", "selector": "#a0", "visible": False},
            {"text": "Inbox", "href": "frmStudentMessage.aspx",
             "id": "", "section": "StudentServices", "selector": "#a1", "visible": True},
            {"text": "Apply for Hostel Leave", "href": "frmApplyLeave.aspx",
             "id": "", "section": "StudentServices", "selector": "#a2", "visible": True},
            {"text": "Notices & Circulars", "href": "frmNotice.aspx",
             "id": "", "section": "ImportantLinks", "selector": "#a3", "visible": True},
            {"text": "Fee Receipt", "href": "frmReceipt.pdf",
             "id": "", "section": "Accounts", "selector": "#a4", "visible": True},
            {"text": "Open next app", "href": "openapp.aspx?toApp=nextproject",
             "id": "", "section": "Academics", "selector": "#a5", "visible": True},
            {"text": "Student 12345678 profile", "href": "profile.aspx",
             "id": "", "section": "", "selector": "#a6", "visible": True},
        ],
        "handlers": [
            {"tag": "div", "id": "AttPercent", "text": "ATTENDANCE : 97%",
             "onclick": "getAtt()", "selector": "#AttPercent", "visible": True},
            {"tag": "div", "id": "MsgCount", "text": "MESSAGES : 3",
             "onclick": "getMsg()", "selector": "#MsgCount", "visible": True},
        ],
        "functions": ["getAtt", "getMsg", "loadNotice", "__doPostBack"],
        "panels": [{"tag": "h3", "id": "first-tab", "text": "Attendance Summary",
                    "section": "mdatt", "selector": "#first-tab", "visible": False}],
        "tables": [{"id": "", "selector": "#t1", "rows": 8, "visible": True,
                    "headers": ["Course", "Total Delivered (T,L,P)"]}],
        "ids": ["AttPercent", "mdatt"],
    },
    {"url": "https://snapwidget.com/embed/1", "title": "widget",
     "links": [], "handlers": [], "functions": [], "panels": [], "tables": [], "ids": []},
]


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


def main() -> int:
    mapped = build(FRAMES)

    print("Feature tagging")
    texts = lambda topic: [i["text"] for i in mapped["by_topic"][topic]["links"]]  # noqa: E731
    check("messages link found", texts("messages") == ["Inbox"], texts("messages"))
    check("announcements link found", texts("announcements") == ["Notices & Circulars"],
          texts("announcements"))
    check("attendance link found", texts("attendance") == ["View Attendance"], texts("attendance"))
    check("message loader handler found",
          [h["onclick"] for h in mapped["by_topic"]["messages"]["handlers"]] == ["getMsg()"])
    check("frames merged", mapped["counts"]["links"] == 7, mapped["counts"])
    check("sections counted", mapped["sections"]["StudentServices"] == 2, mapped["sections"])

    print("\nAnything that could change the portal is flagged")
    check("apply-leave flagged as an action", is_action({"text": "Apply for Hostel Leave", "href": "frmApplyLeave.aspx"}))
    check("submit flagged", is_action({"text": "Submit feedback", "href": "x.aspx"}))
    check("pay flagged", is_action({"text": "Pay dues", "href": "x.aspx"}))
    check("inbox not flagged", not is_action({"text": "Inbox", "href": "frmStudentMessage.aspx"}))
    check("notices not flagged", not is_action({"text": "Notices & Circulars", "href": "frmNotice.aspx"}))

    print("\nCrawl target selection")
    from app.ums.playwright_service import UMSPlaywrightService

    pick = UMSPlaywrightService._visit_targets.__get__(object.__new__(UMSPlaywrightService))
    urls = [t["url"] for t in pick(mapped, ["messages", "announcements", "leave", "fees"], 10)]
    print(f"    would open: {urls}")
    check("opens the inbox page", any("frmStudentMessage.aspx" in u for u in urls))
    check("opens the notices page", any("frmNotice.aspx" in u for u in urls))
    check("never opens an action page", not any("frmApplyLeave" in u for u in urls))
    check("never opens a pdf", not any(".pdf" in u for u in urls))
    check("never opens the cross-app launcher", not any("openapp" in u for u in urls))
    check("all targets stay on the UMS host", all("ums.lpu.in" in u for u in urls))

    print("\nPrivacy")
    check("registration numbers masked", "<digits>" in redact("Student 12345678 profile"))
    check("short numbers kept", redact("97% in 6 courses") == "97% in 6 courses")
    check("map is masked", any("<digits>" in i["text"] for i in mapped["links"]))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: {FAILURES}")
        return 1
    print("All site-map checks passed.")
    return 0


if __name__ == "__main__":
    code = main()
    os._exit(code)
