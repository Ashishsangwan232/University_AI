"""Offline checks for the announcement / message card extractor.

    python scripts/test_panels.py

Uses card shapes matching what the site map found in #tAC and #MyMessage:
sibling <div> cards holding a heading, a date, body lines, and attachment links.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite:///./_panels_test.db")

from app.ums.panels import (  # noqa: E402
    clean_href, dedupe, find_date, is_attachment, parse_card, parse_cards, validate_cards,
)

FAILURES: list[str] = []

ANNOUNCEMENTS_REAL = {
    "selector": "#tAC",
    "children": 110,
    "items": [
        {
            "index": 0,
            "heading": "New Updated Schedule of AON COCUBES Exam of Placement registered "
                       "students of 2027 graduating batch ( LPU/20.2/ST/2024/001/IC/260907/0012 )",
            "dateField": "Sep 07,2026",
            "bodyField": "Dear Students, This is to inform you that Centre for Professional "
                         "Enhancement has rescheduled AON COCUBES- PRE ASSESS-2 Exam.",
            "lines": ["New Updated Schedule of AON COCUBES Exam ...", "Sep 07,2026", "Dear Students, ..."],
            "links": [
                {"text": "Student List.xls",
                 "href": "https://ums.lpu.in/lpuums/umsweb/HR/Announcement/1_Student List.xls"},
            ],
            "selector": "#tAC > :nth-child(1)",
        },
        {
            "index": 1,
            "heading": "New Profile Power-Up- A workshop on crafting your LinkedIn Profile "
                       "( LPU/20.2/ST/2024/001/IC/260907/0011 )",
            "dateField": "Sep 07,2026",
            "bodyField": "Centre for Professional Enhancement in collaboration with School of "
                         "Bio Engineering is going to conduct a workshop.",
            "lines": ["New Profile Power-Up- ...", "Sep 07,2026", "Centre for Professional Enhancement ..."],
            "links": [{"text": "amrit.kaur@lpu.co.in", "href": "http://"},
                      {"text": "form", "href": "http://https://forms.gle/abc"}],
            "selector": "#tAC > :nth-child(3)",
        },
        # the <hr> separators between cards
        {"index": 2, "heading": "", "dateField": "", "bodyField": "", "lines": [], "links": [],
         "selector": "#tAC > :nth-child(2)"},
    ],
}

# The same announcement also appears in the personal tab, with its own ref code.
ANNOUNCEMENTS_PERSONAL = {
    "selector": "#tAM",
    "children": 20,
    "items": [{
        "index": 0,
        "heading": "New Profile Power-Up- A workshop on crafting your LinkedIn Profile "
                   "( LPU/20.2/ST/2024/001/IC/260907/0011 )",
        "dateField": "Sep 07,2026",
        "bodyField": "Centre for Professional Enhancement in collaboration with School of "
                     "Bio Engineering is going to conduct a workshop.",
        "lines": ["New Profile Power-Up- A workshop on crafting your LinkedIn Profile",
                  "Sep 07,2026", "Centre for Professional Enhancement ..."],
        "links": [], "selector": "#tAM > :nth-child(1)",
    }],
}

MESSAGES_REAL = {
    "selector": "#MyMessage",
    "children": 16,
    "items": [
        {
            "index": 0,
            "heading": "AGENTIQ DATATHON 2026 – READY TO CRACK THE DATA? - By Saurav Singh (Sep 07, 2026)",
            "dateField": "",
            "bodyField": "Dear student, Are you curious about Data, Analytics, Dashboards & AI?",
            "lines": ["AGENTIQ DATATHON 2026 ... (Sep 07, 2026)", "Dear student, ..."],
            "links": [], "selector": "#MyMessage > :nth-child(1)",
        },
        {
            "index": 1,
            "heading": "Project - By Project",
            "dateField": "",
            "bodyField": "Dear Student, A new Academic Task is available in your Account",
            "lines": ["Project - By Project", "Dear Student, ..."],
            "links": [], "selector": "#MyMessage > :nth-child(2)",
        },
    ],
}

# The empty "All Messages" modal shell must not become a card.
MESSAGES_MODAL_CHROME = {
    "selector": "#exampleModalRight",
    "children": 1,
    "items": [{
        "index": 0, "heading": "My Messages", "dateField": "", "bodyField": "",
        "lines": ["My Messages", "×", "Close", "Search Messages"],
        "links": [{"text": "Search Messages", "href": "frmStudentsMyMessages.aspx"}],
        "selector": "#exampleModalRight > :nth-child(1)",
    }],
}

ANNOUNCEMENTS = {
    "selector": "#tAC",
    "children": 3,
    "items": [
        {
            "index": 0,
            "heading": "CoCubes Assessment for 2027 Batch",
            "lines": ["CoCubes Assessment for 2027 Batch", "Sep 7, 2026",
                      "All eligible students must report to Block 34 by 9:00 AM.",
                      "Student List.xls", "CoCubes Syllabus.pdf"],
            "links": [
                {"text": "Student List.xls",
                 "href": "https://ums.lpu.in/lpuums/umsweb/HR/Announcement/1_Student List.xls"},
                {"text": "CoCubes Syllabus.pdf",
                 "href": "https://ums.lpu.in/lpuums/umsweb/HR/Announcement/2_CoCubes Syllabus.pdf"},
            ],
            "selector": "#tAC > :nth-child(1)",
        },
        {
            "index": 1,
            "heading": "",
            "lines": ["Campus Drive: Infosys", "07-09-2026",
                      "Registration closes Friday.", "Read more"],
            "links": [{"text": "Read more", "href": "frmDetail.aspx?id=9"}],
            "selector": "#tAC > :nth-child(2)",
        },
        {"index": 2, "heading": "", "lines": [], "links": [], "selector": "#tAC > :nth-child(3)"},
    ],
}

MESSAGES = {
    "selector": "#MyMessage",
    "children": 2,
    "items": [
        {
            "index": 0,
            "heading": "Hostel Room Allotment",
            "lines": ["Hostel Room Allotment", "5 Sep 2026",
                      "Your room has been allotted in BH-4. Collect the key from the warden.",
                      "Click here to view details"],
            "links": [{"text": "Click here to view details",
                       "href": "https://drive.google.com/file/d/abc/view"}],
            "selector": "#MyMessage > :nth-child(1)",
        },
        {
            "index": 1,
            "heading": "Hostel Room Allotment",
            "lines": ["Hostel Room Allotment", "5 Sep 2026",
                      "Your room has been allotted in BH-4. Collect the key from the warden."],
            "links": [],
            "selector": "#exampleModalRight > :nth-child(1)",
        },
    ],
}


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


def main() -> int:
    print("Date detection (UMS uses several formats)")
    for text, expected in [
        (["Sep 7, 2026"], "Sep 7, 2026"),
        (["07-09-2026"], "07-09-2026"),
        (["5 Sep 2026"], "5 Sep 2026"),
        (["2026-09-07"], "2026-09-07"),
        (["no date here"], None),
    ]:
        found, _ = find_date(text)
        check(f"{text[0]!r} -> {found!r}", found == expected, f"expected {expected!r}")

    print("\nAttachment detection")
    check("xls is an attachment", is_attachment({"href": "/a/Student List.xls"}))
    check("pdf is an attachment", is_attachment({"href": "/a/Syllabus.pdf"}))
    check("aspx is not", not is_attachment({"href": "frmDetail.aspx?id=9"}))
    check("drive link is not", not is_attachment({"href": "https://drive.google.com/file/d/abc/view"}))

    print("\nAnnouncements")
    records = parse_cards(ANNOUNCEMENTS, "https://ums.lpu.in/lpuums/StudentDashboard.aspx")
    check("empty card dropped", len(records) == 2, f"got {len(records)}")
    first = records[0]
    check("title from heading", first["title"] == "CoCubes Assessment for 2027 Batch", first["title"])
    check("date parsed", first["date"] == "Sep 7, 2026", str(first["date"]))
    check("body excludes the title", "CoCubes Assessment for 2027" not in first["body"], first["body"])
    check("body keeps the content", "Block 34" in first["body"], first["body"])
    check("two attachments", len(first["attachments"]) == 2, str(first["attachments"]))
    check("attachments not counted as links", len(first["links"]) == 0, str(first["links"]))
    second = records[1]
    check("title inferred with no heading element",
          second["title"] == "Campus Drive: Infosys", second["title"])
    check("'Read more' dropped as chrome", "Read more" not in second["body"], second["body"])
    check("detail link kept", second["links"] and "frmDetail" in second["links"][0]["href"])
    ok, reason = validate_cards(records, "announcements")
    check("announcements validate", ok, reason)

    print("\nMessages (same item appears in the panel and the modal)")
    messages = dedupe(parse_cards(MESSAGES, "x"))
    check("duplicate collapsed", len(messages) == 1, f"got {len(messages)}")
    check("message title", messages[0]["title"] == "Hostel Room Allotment", messages[0]["title"])
    check("message body", "BH-4" in messages[0]["body"], messages[0]["body"])

    print("\nValidation must reject a wrong container")
    ok, reason = validate_cards([], "announcements")
    check("empty rejected", not ok, reason)
    blanks = [{"title": "", "body": "", "date": None} for _ in range(3)]
    ok, reason = validate_cards(blanks, "messages")
    check("all-empty rejected", not ok, reason)
    same = [{"title": "Menu", "body": "", "date": None} for _ in range(5)]
    ok, reason = validate_cards(same, "announcements")
    check("identical titles rejected", not ok, reason)
    check("a single real item is fine",
          validate_cards([{"title": "Real notice", "body": "Something happened", "date": None}],
                         "announcements")[0])

    print("\nNo crash on malformed input")
    check("None payload", parse_cards(None) == [])
    check("no items key", parse_cards({"selector": "#x"}) == [])
    check("card with nothing at all", parse_card({"lines": [], "links": []}) is None)
    check("card with only noise lines but real fields is kept",
          parse_card({"lines": ["..."], "links": [], "heading": "Real subject",
                      "bodyField": "Real body"}) is not None)

    print("\nReal UMS markup: announcements (#tAC)")
    real = parse_cards(ANNOUNCEMENTS_REAL, "u", channel="#tAC")
    check("hr separators dropped", len(real) == 2, f"got {len(real)}")
    first = real[0]
    check("'New' badge stripped from the title",
          first["title"].startswith("Updated Schedule of AON COCUBES"), first["title"])
    check("reference code pulled out of the title",
          first["reference"] == "LPU/20.2/ST/2024/001/IC/260907/0012", first["reference"])
    check("reference no longer in the title", "LPU/" not in first["title"], first["title"])
    check("date from .announcement-date", first["date"] == "Sep 07,2026", str(first["date"]))
    check("body from .panel-body", first["body"].startswith("Dear Students"), first["body"][:40])
    check("body excludes the title", "AON COCUBES Exam of Placement" not in first["body"])
    check("attachment kept", len(first["attachments"]) == 1, str(first["attachments"]))
    second = real[1]
    check("broken 'http://' link dropped",
          all(l["href"] != "http://" for l in second["links"]), str(second["links"]))
    check("'http://https://' link repaired",
          any(l["href"] == "https://forms.gle/abc" for l in second["links"]), str(second["links"]))

    print("\nReal UMS markup: messages (#MyMessage)")
    messages_real = parse_cards(MESSAGES_REAL, "u", channel="#MyMessage")
    check("two messages", len(messages_real) == 2, f"got {len(messages_real)}")
    top = messages_real[0]
    check("sender split out of the header", top["sender"] == "Saurav Singh", top["sender"])
    check("date split out of the header", top["date"] == "Sep 07, 2026", str(top["date"]))
    check("title is just the subject",
          top["title"] == "AGENTIQ DATATHON 2026 – READY TO CRACK THE DATA?", top["title"])
    check("body preserved", top["body"].startswith("Dear student"), top["body"][:30])
    check("header with no date still splits",
          messages_real[1]["sender"] == "Project" and messages_real[1]["title"] == "Project",
          str(messages_real[1]))

    print("\nPanel chrome is not content")
    chrome = parse_cards(MESSAGES_MODAL_CHROME, "u", channel="#exampleModalRight")
    check("empty modal shell dropped", chrome == [], str(chrome))

    print("\nCross-tab duplicates collapse, channels merge")
    merged = dedupe(
        parse_cards(ANNOUNCEMENTS_REAL, "u", channel="#tAC")
        + parse_cards(ANNOUNCEMENTS_PERSONAL, "u", channel="#tAM")
    )
    check("duplicate across #tAC and #tAM collapsed", len(merged) == 2, f"got {len(merged)}")
    both = [r for r in merged if r["reference"].endswith("0011")][0]
    check("channels merged", both["channel"] == "#tAC,#tAM", both["channel"])

    print("\nBroken href repair")
    check("bare http:// dropped", clean_href("http://") == "")
    check("double scheme repaired", clean_href("http://https://x.com/a") == "https://x.com/a")
    check("anchor dropped", clean_href("#") == "")
    check("normal href kept", clean_href("frmDetail.aspx?id=9") == "frmDetail.aspx?id=9")

    print("\nNested reference codes (the ANN(EXAM) trap)")
    nested = parse_card({
        "heading": "New Postponement of Ph.D. Public Pre-Submission Evaluation "
                   "( LPU/10.2/ANN(EXAM)/2024/023(23.4)(Vol-9)/IC/260907/0035 )",
        "dateField": "Sep 07,2026", "bodyField": "The evaluation has been postponed.",
        "lines": ["..."], "links": [],
    })
    check("full nested reference captured",
          nested["reference"] == "LPU/10.2/ANN(EXAM)/2024/023(23.4)(Vol-9)/IC/260907/0035",
          nested["reference"])
    check("no reference fragment left in the title",
          nested["title"] == "Postponement of Ph.D. Public Pre-Submission Evaluation",
          nested["title"])
    other = parse_card({
        "heading": "REGISTRATION REOPENED! Gear UP Season 5 "
                   "( LPU/18.4/CAPB(EBGB)/2024/001(1.2)/IC/260905/0002 )",
        "dateField": "Sep 05,2026", "bodyField": "Register now.", "lines": ["..."], "links": [],
    })
    check("second nested form captured",
          other["reference"] == "LPU/18.4/CAPB(EBGB)/2024/001(1.2)/IC/260905/0002", other["reference"])
    check("unrelated notices keep distinct references",
          nested["reference"] != other["reference"])
    check("distinct references are not merged",
          len(dedupe([nested, other])) == 2, str(len(dedupe([nested, other]))))

    print("\nContent duplicates across tabs collapse even with different references")
    a = parse_card({"heading": "SBI Asha Scholarship ( LPU/20.4/INDU/2026/003/IC/260903/0003 )",
                    "dateField": "Sep 03,2026", "bodyField": "Financial assistance for PG students.",
                    "lines": ["..."], "links": []}, channel="#tAC")
    b = parse_card({"heading": "SBI Asha Scholarship ( LPU/20.4/INDU/2026/003/IC/260903/0008 )",
                    "dateField": "Sep 03,2026", "bodyField": "Financial assistance for PG students.",
                    "lines": ["..."], "links": []}, channel="#tAM")
    merged_two = dedupe([a, b])
    check("same content, different reference -> one item", len(merged_two) == 1, str(len(merged_two)))
    check("channels merged across tabs", merged_two[0]["channel"] == "#tAC,#tAM", merged_two[0]["channel"])

    print("\nA loaded panel wrapper is still not a card")
    loaded_modal = parse_card({
        "heading": "My Messages", "dateField": "", "bodyField": "",
        "lines": ["My Messages", "AGENTIQ DATATHON 2026", "Dear student, ...", "Opening of Labs"],
        "links": [{"text": "Click here", "href": "https://x/1"}],
    })
    check("loaded modal wrapper dropped", loaded_modal is None, str(loaded_modal))

    print("\nA wrapper holding every item is rejected structurally")
    # The loaded "All Messages" modal: one element, 16 messages, 32 .col-sm-12.
    wrapper = parse_card({
        "heading": "AGENTIQ DATATHON 2026 – READY TO CRACK THE DATA? - By Saurav Singh (Sep 07, 2026)",
        "titleCount": 32,
        "dateField": "", "bodyField": "Dear student, ...",
        "lines": ["AGENTIQ DATATHON ...", "Dear student, ...", "Opening of Labs ..."],
        "links": [{"text": "Click here", "href": "https://forms.gle/other-message"}],
    })
    check("32 title elements -> wrapper rejected", wrapper is None, str(wrapper))
    check("a real message row (2 elements) is kept",
          parse_card({"heading": "Opening of Labs - By Niraj Sharma (Sep 07, 2026)", "titleCount": 2,
                      "dateField": "", "bodyField": "Dear Student, labs open till 7 PM.",
                      "lines": ["x"], "links": []}) is not None)
    check("a real announcement (1 element) is kept",
          parse_card({"heading": "Byte Club LPU", "titleCount": 1, "dateField": "Sep 07,2026",
                      "bodyField": "Join the club.", "lines": ["x"], "links": []}) is not None)
    check("no titleCount at all still works",
          parse_card({"heading": "Legacy card", "bodyField": "body", "lines": ["x"],
                      "links": []}) is not None)

    print("\nThe same URL rendered twice is listed once")
    dup = parse_card({
        "heading": "SBI Asha Scholarship", "titleCount": 1, "dateField": "Sep 03,2026",
        "bodyField": "Apply online.", "lines": ["x"],
        "links": [
            {"text": "https://forms.gle/stxQLjd4VJ7HjqBc8", "href": "https://forms.gle/stxQLjd4VJ7HjqBc8"},
            {"text": "stxQLjd4VJ7HjqBc8", "href": "https://forms.gle/stxQLjd4VJ7HjqBc8"},
            {"text": "buddy4study", "href": "https://www.buddy4study.com/page/x"},
        ],
    })
    check("duplicate href collapsed", len(dup["links"]) == 2, str(dup["links"]))
    check("first label kept", dup["links"][0]["text"].startswith("https://forms.gle"), dup["links"][0]["text"])
    check("distinct href kept", dup["links"][1]["href"].endswith("/page/x"))

    print("\nHrefs that run past a newline")
    check("newline in href truncated",
          clean_href("https://drive.google.com/file/d/1K9/view  \n?? NPTEL Guide")
          == "https://drive.google.com/file/d/1K9/view")
    check("filename spaces preserved",
          clean_href("/a/Student List.xls") == "/a/Student List.xls")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: {FAILURES}")
        return 1
    print("All panel checks passed.")
    return 0


if __name__ == "__main__":
    code = main()
    os._exit(code)
