"""Offline tests for the student identity reader.

No browser, no network, no UMS. Every case here replays a DOM shape the real
dashboard or leave page produced.

    python scripts/test_profile.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.ums.profile import (  # noqa: E402
    PROFILE_JS,
    initials,
    is_strong,
    looks_like_name,
    merge_profile,
    parse_identity_block,
    parse_profile,
    validate_profile,
)

PASSED = 0
FAILED: list[str] = []


def check(label: str, got, want) -> None:
    global PASSED
    if got == want:
        PASSED += 1
    else:
        FAILED.append(f"{label}\n    got:  {got!r}\n    want: {want!r}")


def truthy(label: str, got) -> None:
    check(label, bool(got), True)


# --------------------------------------------------------------------------
# The leave page shape: labelled fields. This is the reading that works today.
# --------------------------------------------------------------------------
LEAVE_PAGE = {
    "url": "https://ums.lpu.in/lpuums/frmStudentHostelLeaveApplicationTermWise.aspx",
    "title": "Hostel Leave Application",
    "fields": [
        {"label": "VID", "value": "12413705"},
        {"label": "Name", "value": "Ashish"},
        {"label": "Hostel", "value": "Boys Hostel-01"},
        {"label": "Room No", "value": "A512-Bed C"},
    ],
    "candidates": [],
    "greeting": "",
}

profile = parse_profile(LEAVE_PAGE)
check("leave page: name", profile["name"], "Ashish")
check("leave page: registration number", profile["student_id"], "12413705")
check("leave page: name source", profile["name_source"], "label")
check("leave page: validates", validate_profile(profile)[0], True)
truthy("leave page: counts as strong evidence", is_strong(profile))

# --------------------------------------------------------------------------
# The real dashboard header. There is no label on the name at all:
#
#     Ashish
#     VID: 12413705 | Section: K4P24OF
#     B.Tech. (Computer Science and Engineering) (P132 )
#
# so the registration number is the anchor and the name is the line above it.
# --------------------------------------------------------------------------
HEADER = {
    "url": "https://ums.lpu.in/lpuums/StudentDashboard.aspx",
    "title": "Student Dashboard",
    "fields": [],
    "candidates": [],
    "greeting": "",
    "blocks": [
        # The smallest element holding the VID has no name in it - the parser
        # has to keep looking at the bigger ones.
        {"lines": ["VID: 12413705 | Section: K4P24OF"], "length": 33},
        {"lines": ["Ashish",
                   "VID: 12413705 | Section: K4P24OF",
                   "B.Tech. (Computer Science and Engineering) (P132 )"], "length": 120},
    ],
}
profile = parse_profile(HEADER)
check("header: name", profile["name"], "Ashish")
check("header: registration number", profile["student_id"], "12413705")
check("header: section", profile["section"], "K4P24OF")
check("header: programme", profile["program"], "B.Tech. (Computer Science and Engineering) (P132 )")
check("header: department out of the brackets", profile["department"], "Computer Science and Engineering")
check("header: source", profile["name_source"], "header-block")
truthy("header: counts as strong evidence", is_strong(profile))

check("header: a block with no id yields nothing",
      parse_identity_block([{"lines": ["Some panel", "with no id"], "length": 20}]), {})
check("header: no blocks at all", parse_identity_block(None), {})
check("header: an id with no name above it yields nothing",
      parse_identity_block([{"lines": ["VID: 12413705"], "length": 13}]), {})

# --------------------------------------------------------------------------
# The bug this replaced: "hi" matched inside "hiring platform", and the
# student was named "ring platform.".
# --------------------------------------------------------------------------
check("a sentence is not a name", looks_like_name("ring platform."), False)
check("marketing copy is not a name", looks_like_name("Why AON CoCubes Exam is important"), False)
check("a lowercase fragment is not a name", looks_like_name("hiring platform"), False)
check("a menu label is not a name", looks_like_name("Student Services"), False)
check("something with a number is not a name", looks_like_name("VID 12413705"), False)
check("an empty string is not a name", looks_like_name(""), False)
check("one word is a name", looks_like_name("Ashish"), True)
check("three words are a name", looks_like_name("Ashish Kumar Sangwan"), True)
check("five words are not", looks_like_name("A B C D E"), False)

# A profile carrying that junk must fail validation rather than reach the UI.
check("junk fails validation", validate_profile({"name": "ring platform."})[0], False)
check("a real name passes", validate_profile({"name": "Ashish"})[0], True)

# --------------------------------------------------------------------------
# A greeting is the fallback when nothing is labelled.
# --------------------------------------------------------------------------
GREETING_ONLY = {
    "url": "https://ums.lpu.in/lpuums/StudentDashboard.aspx",
    "title": "Student Dashboard",
    "fields": [],
    "candidates": [],
    "greeting": "Ashish Sangwan",
}
profile = parse_profile(GREETING_ONLY)
check("greeting: name", profile["name"], "Ashish Sangwan")
check("greeting: source", profile["name_source"], "greeting")
check("greeting: counts as weak, so the leave page is still checked",
      is_strong(profile), False)

# The word "Welcome" on its own is page furniture, not a name.
check(
    "greeting: furniture rejected",
    parse_profile({**GREETING_ONLY, "greeting": "Student"})["name"],
    "",
)

# --------------------------------------------------------------------------
# A marked-up element, when there is no label and no greeting.
# --------------------------------------------------------------------------
MARKED = {
    "url": "https://ums.lpu.in/lpuums/StudentDashboard.aspx",
    "title": "Student Dashboard",
    "fields": [],
    "candidates": [
        {"id": "", "cls": "user-menu-toggle", "text": "Menu"},
        {"id": "lblStudentName", "cls": "profile-name", "text": "Ashish Sangwan"},
    ],
    "greeting": "",
}
profile = parse_profile(MARKED)
check("element: name", profile["name"], "Ashish Sangwan")
truthy("element: source names the element", profile["name_source"].startswith("element:"))

# A registration number is not a name, however it is marked up.
NUMERIC = {
    **MARKED,
    "candidates": [{"id": "lblUserName", "cls": "username", "text": "12413705"}],
}
profile = parse_profile(NUMERIC)
check("element: number is not a name", profile["name"], "")
check("element: number is still an id", profile["student_id"], "12413705")
check("element: no name fails validation", validate_profile(profile)[0], False)

# A whole sentence in a .name element is not a name either.
SENTENCE = {
    **MARKED,
    "candidates": [
        {"id": "", "cls": "student-name-panel",
         "text": "Your name as recorded in the university records is shown"},
    ],
    "greeting": "",
}
check("element: sentence rejected", parse_profile(SENTENCE)["name"], "")

# --------------------------------------------------------------------------
# Merging: the dashboard wins, the leave page fills the blanks.
# --------------------------------------------------------------------------
merged = merge_profile(
    {"name": "Ashish Sangwan", "student_id": "", "hostel": ""},
    {"name": "Ashish", "student_id": "12413705", "hostel": "Boys Hostel-01"},
)
check("merge: keeps the fuller dashboard name", merged["name"], "Ashish Sangwan")
check("merge: fills the missing id", merged["student_id"], "12413705")
check("merge: fills the missing hostel", merged["hostel"], "Boys Hostel-01")

check("merge: tolerates no fallback", merge_profile({"name": "A"}, {})["name"], "A")

# --------------------------------------------------------------------------
# Nothing in, nothing out - never a placeholder identity.
# --------------------------------------------------------------------------
check("empty payload", parse_profile(None), {})
check("empty payload fails validation", validate_profile({})[0], False)
check(
    "empty payload gives no name",
    parse_profile({"fields": [], "candidates": [], "greeting": ""})["name"],
    "",
)

# --------------------------------------------------------------------------
# Initials, for the avatar.
# --------------------------------------------------------------------------
check("initials: two words", initials("Ashish Sangwan"), "AS")
check("initials: one word", initials("Ashish"), "A")
check("initials: three words takes two", initials("Ravi Kumar Sharma"), "RK")
check("initials: nothing", initials(""), "?")

# --------------------------------------------------------------------------
# Term to semester and year, in Python rather than in the model.
# --------------------------------------------------------------------------
from app.ums.profile import term_number  # noqa: E402

check("term: 'Term 5'", term_number("Term 5"), 5)
check("term: bare number", term_number("5"), 5)
check("term: 'Semester 03'", term_number("Semester 03"), 3)
check("term: a session label is not a term", term_number("2025-26 Even Term"), None)
check("term: out of range", term_number("Term 99"), None)
check("term: missing", term_number(None), None)

# --------------------------------------------------------------------------
# Read-only guarantee, enforced against the source rather than promised.
# --------------------------------------------------------------------------
source = pathlib.Path(__file__).resolve().parents[1] / "app" / "ums" / "profile.py"
text = source.read_text(encoding="utf-8")
for forbidden in (".click(", ".fill(", ".submit(", "checked =", "dispatchEvent"):
    check(f"profile.py never writes to the page: {forbidden}", forbidden in text, False)
truthy("PROFILE_JS is a raw string", "PROFILE_JS = r\"\"\"" in text)

service = pathlib.Path(__file__).resolve().parents[1] / "app" / "ums" / "playwright_service.py"
body = service.read_text(encoding="utf-8")
start = body.index("def _capture_profile")
end = body.index("def _capture_leave", start)
capture = body[start:end]
for forbidden in (".click(", ".fill(", ".check(", ".select_option("):
    check(f"_capture_profile never interacts: {forbidden}", forbidden in capture, False)
truthy("_capture_profile falls back to the leave page", "ums_leave_page" in capture)
truthy("the fallback reads the leave page's own fields", "parse_leave(" in capture)
truthy("a failure reports the labels it did see", "profile_labels_seen" in capture)

# Every model may read the identity; none of them can change it. The tool list
# is shared, so this holds for Gemini and Ollama at once.
from app.agent.tools import TOOL_NAMES  # noqa: E402

truthy("the models can read the profile", "get_student_profile" in TOOL_NAMES)
for forbidden in ("set_student", "update_profile", "prefill", "write_"):
    check(f"no write tool exists: {forbidden}",
          any(forbidden in name for name in TOOL_NAMES), False)

print(f"\n{PASSED} checks passed, {len(FAILED)} failed")
for failure in FAILED:
    print("  FAIL " + failure)
sys.exit(1 if FAILED else 0)
