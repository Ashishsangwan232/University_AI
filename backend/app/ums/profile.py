"""Who the student actually is, read from UMS.

The app shipped with a hardcoded demo identity. This reads the real one.

The dashboard does not expose the name in any link, panel or table - the site
map found nothing - so this looks for it the way a person would: a "Name :"
style label/value pair, a "Welcome, X" greeting, or an element whose class says
it holds a name. When the dashboard yields nothing, the caller falls back to the
hostel leave page, which is known to carry name, registration number, hostel and
room.

Read-only. Playwright-free so it can be unit tested.
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger("campusai.ums")

PROFILE_JS = r"""
() => {
  const tidy = (s) => (s || '').replace(/\s+/g, ' ').trim();

  // Identity labels UMS uses. A label is taken either because it ends in a
  // colon, or because it is one of these - the leave page prints some of them
  // with no colon at all, which is why a colon alone was not enough.
  const KNOWN = /^(name|student\s*name|candidate\s*name|full\s*name|vid|registration\s*(no|number)|reg\.?\s*no|student\s*id|roll\s*(no|number)|programme?|course|department|school|section|term|semester|hostel|room\s*no)$/i;

  // Label/value pairs, the same shape the leave page uses.
  const fields = [];
  const cells = Array.from(document.querySelectorAll('td,th,label,dt,span,div')).slice(0, 1500);
  for (let i = 0; i < cells.length; i++) {
    const label = tidy(cells[i].innerText || cells[i].textContent);
    if (!label || label.length > 50) continue;
    const bare = label.replace(/[:：]\s*$/, '').trim();
    if (!/[:：]\s*$/.test(label) && !KNOWN.test(bare)) continue;
    let value = '';
    for (let j = i + 1; j < Math.min(i + 3, cells.length); j++) {
      const field = cells[j].querySelector && cells[j].querySelector('input,select');
      value = field ? tidy(field.value) : tidy(cells[j].innerText || cells[j].textContent);
      if (value) break;
    }
    if (value) fields.push({ label: label.replace(/[:：]\s*$/, '').trim(), value: value.slice(0, 120) });
    if (fields.length >= 60) break;
  }

  // Elements that advertise themselves as holding an identity.
  const candidates = [];
  const marked = document.querySelectorAll(
    '[class*=name i],[id*=name i],[class*=user i],[id*=user i],' +
    '[class*=profile i],[id*=profile i],[class*=student i],[id*=student i]');
  for (const el of Array.from(marked).slice(0, 120)) {
    const text = tidy(el.innerText || el.textContent);
    if (text && text.length <= 60) {
      candidates.push({ id: el.id || '', cls: String(el.className || '').slice(0, 60), text });
    }
    if (candidates.length >= 40) break;
  }

  // The header identity block. The LPU dashboard prints it as three lines in
  // the top right, with no labels on the name at all:
  //
  //     Ashish
  //     VID: 12413705 | Section: K4P24OF
  //     B.Tech. (Computer Science and Engineering) (P132 )
  //
  // So the anchor is the registration number, and the name is the line above
  // it. Every element small enough to be that block is returned, smallest
  // first, and Python decides which one actually holds a name.
  const ID_HINT = /\b(?:vid|registration\s*no|reg\.?\s*no|student\s*id|roll\s*no)\s*[:：]/i;
  const blocks = [];
  const boxes = Array.from(
    document.querySelectorAll('header,nav,aside,div,section,td,p,span')
  ).slice(0, 3000);
  for (const el of boxes) {
    const raw = el.innerText || '';
    if (raw.length > 400 || !ID_HINT.test(raw)) continue;
    const lines = raw.split('\n').map(tidy).filter(Boolean).slice(0, 12);
    if (lines.length) blocks.push({ lines, length: raw.length });
    if (blocks.length >= 12) break;
  }
  blocks.sort((a, b) => a.length - b.length);

  // "Welcome, X" as a last resort. The word boundary on BOTH sides matters:
  // without it, "hi" matched inside "hiring platform" and the student was
  // named "ring platform.".
  const body = tidy(document.body ? document.body.innerText : '');
  const greeting = body.match(
    /(?:^|[\s>])(?:[Ww]elcome|[Hh]ello|[Gg]ood\s+(?:[Mm]orning|[Aa]fternoon|[Ee]vening))\b[\s,!:-]+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\b/
  );

  return {
    url: location.href, title: document.title,
    fields, candidates, blocks,
    greeting: greeting ? tidy(greeting[1]) : ''
  };
}
"""

NAME_LABELS = ("name", "student name", "candidate name", "full name")
ID_LABELS = ("vid", "registration no", "registration number", "reg no", "reg. no",
             "student id", "roll no", "roll number")
PROGRAM_LABELS = ("program", "programme", "course", "degree")
DEPARTMENT_LABELS = ("department", "school", "discipline")
SECTION_LABELS = ("section", "group")
TERM_LABELS = ("term", "semester")
HOSTEL_LABELS = ("hostel",)
ROOM_LABELS = ("room no", "room", "room number")

#: A registration number, not a phone number or a year.
REG_NUMBER = re.compile(r"\b\d{7,12}\b")
#: Things that look like a name but are page furniture.
NOT_A_NAME = re.compile(
    r"^(student|dashboard|profile|user|name|welcome|home|logout|menu|ums|university|"
    r"admin|academics|administrative|important links|quick links|student services)$",
    re.I,
)
#: Words that give away a sentence pretending to be a name.
NOT_IN_A_NAME = re.compile(
    r"\b(platform|click|here|more|read|view|details|exam|important|please|your|the|and|"
    r"for|with|from|login|password|attendance|course|semester)\b",
    re.I,
)
#: One name-shaped word: starts with a capital, letters and the odd . ' - after.
NAME_WORD = re.compile(r"^[A-Z][A-Za-z.'\-]{0,24}$")

#: The registration number on the header line: "VID: 12413705 | Section: K4P24OF".
BLOCK_ID = re.compile(
    r"\b(?:vid|registration\s*no|reg\.?\s*no|student\s*id|roll\s*no)\s*[:：]\s*([A-Za-z0-9/\-]{4,20})",
    re.I,
)
BLOCK_SECTION = re.compile(r"\bsection\s*[:：]\s*([A-Za-z0-9]{2,12})", re.I)
#: "B.Tech. (Computer Science and Engineering) (P132 )" and friends.
BLOCK_PROGRAM = re.compile(
    r"^((?:B|M)\.?\s?(?:Tech|Sc|Com|A|BA|CA|E|Des|Pharm)\b[^|]*|Ph\.?\s?D\b[^|]*)", re.I
)
#: The programme line usually names the discipline inside brackets.
BRACKETED = re.compile(r"\(([^)]{4,60})\)")


def looks_like_name(text: str) -> bool:
    """Is this a person's name, rather than a slice of page copy?

    A greeting match once produced "ring platform." as the student's name, so
    this is deliberately strict: one to four capitalised words, no digits, no
    sentence words, nothing from the site's own furniture.
    """
    cleaned = (text or "").strip().strip(".,;:").strip()
    if not cleaned or len(cleaned) > 60 or len(cleaned) < 2:
        return False
    if any(character.isdigit() for character in cleaned):
        return False
    if NOT_A_NAME.match(cleaned) or NOT_IN_A_NAME.search(cleaned):
        return False
    words = cleaned.split()
    if not 1 <= len(words) <= 4:
        return False
    return all(NAME_WORD.match(word) for word in words)


def parse_identity_block(blocks: list[dict[str, Any]] | None) -> dict[str, str]:
    """Read the header block: a bare name, then "VID: ... | Section: ...".

    The dashboard gives the name no label of any kind, so the registration
    number is the anchor: find the line carrying it, and the name is the
    nearest line above that reads like one.
    """
    for block in blocks or []:
        lines = [line for line in (block.get("lines") or []) if line]
        anchor = next((i for i, line in enumerate(lines) if BLOCK_ID.search(line)), None)
        if anchor is None:
            continue

        found: dict[str, str] = {}
        id_match = BLOCK_ID.search(lines[anchor])
        if id_match:
            found["student_id"] = id_match.group(1).strip()
        section = BLOCK_SECTION.search(lines[anchor])
        if section:
            found["section"] = section.group(1).strip()

        for line in lines[anchor + 1:anchor + 3]:
            program = BLOCK_PROGRAM.match(line)
            if program:
                found["program"] = program.group(1).strip()
                inside = BRACKETED.search(line)
                if inside:
                    found["department"] = inside.group(1).strip()
                break

        for line in reversed(lines[:anchor]):
            if looks_like_name(line):
                found["name"] = line.strip().strip(".,;:")
                found["name_source"] = "header-block"
                break

        if found.get("name"):
            return found
    return {}


def _pick(fields: list[dict[str, str]], labels: tuple[str, ...]) -> str:
    for field in fields:
        if (field.get("label") or "").strip().lower() in labels:
            value = (field.get("value") or "").strip()
            if value:
                return value
    return ""


def parse_profile(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Best available identity, plus what it was read from.

    Strongest evidence first: a labelled "Name :" field, then the header block
    anchored on the registration number, then an element whose class says it
    holds a name, and only then a greeting - which is the weakest signal on a
    page full of marketing copy, and is checked hardest.
    """
    if not payload:
        return {}
    fields = payload.get("fields") or []

    block = parse_identity_block(payload.get("blocks"))

    name = _pick(fields, NAME_LABELS)
    source = "label" if name else ""

    if not name and block.get("name"):
        name, source = block["name"], "header-block"

    if not name:
        for candidate in payload.get("candidates") or []:
            text = (candidate.get("text") or "").strip()
            if not text or REG_NUMBER.search(text) or not looks_like_name(text):
                continue
            name, source = text, f"element:{candidate.get('id') or candidate.get('cls')}"
            break

    if not name:
        greeting = (payload.get("greeting") or "").strip()
        if looks_like_name(greeting):
            name, source = greeting, "greeting"

    student_id = _pick(fields, ID_LABELS) or block.get("student_id", "")
    if not student_id:
        for candidate in payload.get("candidates") or []:
            match = REG_NUMBER.search(candidate.get("text") or "")
            if match:
                student_id = match.group(0)
                break

    profile = {
        "name": name.strip()[:80],
        "student_id": student_id.strip()[:20],
        "program": (_pick(fields, PROGRAM_LABELS) or block.get("program", ""))[:80],
        "department": (_pick(fields, DEPARTMENT_LABELS) or block.get("department", ""))[:80],
        "section": (_pick(fields, SECTION_LABELS) or block.get("section", ""))[:40],
        "term": _pick(fields, TERM_LABELS)[:60],
        "hostel": _pick(fields, HOSTEL_LABELS)[:60],
        "room": _pick(fields, ROOM_LABELS)[:40],
        "name_source": source,
        "page_url": payload.get("url"),
    }
    log.info(
        "[UMS] Profile: name=%s id=%s (from %s)",
        "yes" if profile["name"] else "no",
        "yes" if profile["student_id"] else "no",
        source or "nothing",
    )
    return profile


def merge_profile(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Fill blanks in the dashboard reading from the leave page reading."""
    merged = dict(primary)
    for key, value in (fallback or {}).items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


#: Sources good enough to stop looking. A greeting is not one of them: it is a
#: regex over page copy, so the leave page is still consulted to confirm it.
STRONG_SOURCES = ("label", "header-block", "leave-page-fields")


def validate_profile(profile: dict[str, Any]) -> tuple[bool, str]:
    if not profile or not profile.get("name"):
        return False, "no student name could be read from UMS"
    if not looks_like_name(profile["name"]):
        return False, f"what was read does not look like a name: {profile['name']!r}"
    return True, "ok"


def is_strong(profile: dict[str, Any]) -> bool:
    """True when the name came from a labelled field or the header block."""
    return bool(profile) and (profile.get("name_source") or "") in STRONG_SOURCES


#: "Term 5", "5", "Semester 5" - a term number we can turn into a year.
TERM_NUMBER = re.compile(r"(?:term|semester|sem)?\s*0*(\d{1,2})\s*$", re.I)


def term_number(term: str | None) -> int | None:
    """The term as an integer, or None. Deliberately strict.

    "Term 5" and "5" give 5; "2025-26 Even Term" gives nothing, because guessing
    a semester from a session label would put a made-up number on the dashboard.
    """
    match = TERM_NUMBER.fullmatch((term or "").strip())
    if not match:
        return None
    value = int(match.group(1))
    return value if 1 <= value <= 12 else None


def initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"
