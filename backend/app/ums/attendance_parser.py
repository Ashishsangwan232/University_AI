"""Pure-python parsing/validation of a UMS attendance table.

Kept free of Playwright imports so it can be unit tested against captured row
matrices without a browser. The extractor hands this module a list of rows,
where each row is a list of cell strings taken from ``th``/``td`` elements.
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger("campusai.ums")

COURSE_CODE = re.compile(r"\b([A-Z]{2,5}\s?\d{3,4}[A-Z]?)\b")
TOTAL_WORDS = ("total", "aggregate", "overall", "grand total", "summary")


def clean(value: Any) -> str:
    return re.sub(r"[ \s]+", " ", str(value or "")).strip()


def to_int(value: str) -> int | None:
    """First integer in the cell. Returns None when the cell has no number."""
    m = re.search(r"-?\d+", clean(value).replace(",", ""))
    return int(m.group(0)) if m else None


TLP_HEADER = re.compile(r"\(\s*t\s*,\s*l\s*,\s*p\s*\)", re.I)
TLP_CELL = re.compile(r"^\d+(?:\s*,\s*\d+)+$")
TOTAL_THEN_SPLIT = re.compile(r"^\s*(\d+)\s*\(")


def to_count(value: str, header: str = "") -> int | None:
    """Class count from a cell, aware of the UMS ``(T,L,P)`` columns.

    LPU UMS labels the columns ``Total Delivered (T,L,P)`` / ``Total Attended
    (T,L,P)``. The cell is either an explicit total followed by the breakdown
    (``45 (30,0,15)``) or the bare breakdown (``30,0,15``). Reading only the
    first number would silently drop lab and tutorial hours for any course that
    has them.
    """
    text = clean(value)
    if not text:
        return None
    explicit = TOTAL_THEN_SPLIT.match(text)
    if explicit:
        return int(explicit.group(1))
    compact = re.sub(r"\s+", "", text)
    if TLP_CELL.fullmatch(compact) and TLP_HEADER.search(header or ""):
        return sum(int(n) for n in compact.split(","))
    # Fall back to the first digit group. Do NOT strip commas first: "30,0,15"
    # in a column that is not declared (T,L,P) means 30, never 30015.
    m = re.search(r"\d+", text)
    return int(m.group(0)) if m else None


def to_percent(value: str) -> float | None:
    """Percentage from a cell.

    UMS renders percentages both as ``96 %`` and as a bare ``96.00``, so a bare
    number in a percentage column is accepted too.
    """
    text = clean(value)
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if m:
        return float(m.group(1))
    m = re.fullmatch(r"(\d+(?:\.\d+)?)", text)
    if m:
        value_f = float(m.group(1))
        return value_f if 0 <= value_f <= 100 else None
    return None


#: Per-course class logs live in the second tab of the attendance modal, one
#: collapsible per course: #collapseCSE329 etc., each holding a table with
#: Date | Time | Type | Attendance | Name | Block Reason.
DETAIL_JS = r"""
(cfg) => {
  const tidy = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const out = [];
  for (const el of Array.from(document.querySelectorAll(cfg.selector)).slice(0, 40)) {
    const table = el.querySelector('table');
    if (!table) continue;
    const rows = Array.from(table.querySelectorAll('tr')).slice(0, 400).map(r =>
      Array.from(r.querySelectorAll('th,td')).map(c => tidy(c.innerText || c.textContent))
    );
    out.push({ id: el.id || '', selector: '#' + (el.id || ''), rows });
  }
  return out;
}
"""

#: "collapseCSE329" -> "CSE329". Case-sensitive on purpose: with IGNORECASE the
#: letter run greedily swallows the tail of "collapse" and yields "SECSE329".
DETAIL_ID = re.compile(r"([A-Z]{2,5}\s?\d{3,4}[A-Z]?)\s*$")

PRESENT_WORDS = ("present", "p", "attended", "yes")
ABSENT_WORDS = ("absent", "a", "no")


def _detail_status(value: str) -> str:
    """Normalise the Attendance column to present / absent / the raw value."""
    text = clean(value).lower()
    if not text:
        return "unknown"
    if any(text == w or text.startswith(w + " ") for w in PRESENT_WORDS):
        return "present"
    if any(text == w or text.startswith(w + " ") for w in ABSENT_WORDS):
        return "absent"
    if "present" in text:
        return "present"
    if "absent" in text:
        return "absent"
    return clean(value)[:40] or "unknown"


def parse_detail_tables(payload: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Per-course class-by-class logs, keyed by course code.

    A collapsible whose table is not a class log is skipped rather than guessed
    at, and UMS renders some of them twice, so the fullest copy wins.
    """
    courses: dict[str, Any] = {}
    for block in payload or []:
        code_match = DETAIL_ID.search(block.get("id") or "")
        if not code_match:
            continue
        code = code_match.group(1).replace(" ", "").upper()
        rows = [[clean(c) for c in row] for row in block.get("rows") or []]
        rows = [row for row in rows if any(row)]
        if len(rows) < 2:
            continue

        headers = [h.lower() for h in rows[0]]
        if not any("date" in h for h in headers) or not any("attend" in h for h in headers):
            continue

        def column(*names: str) -> int:
            for index, header in enumerate(headers):
                if any(name in header for name in names):
                    return index
            return -1

        idx = {
            "date": column("date"),
            "time": column("time"),
            "type": column("type"),
            "status": column("attend"),
            "teacher": column("name", "faculty", "teacher"),
            "reason": column("reason", "remark"),
        }

        entries = []
        for row in rows[1:]:
            def cell(key: str, row=row) -> str:
                position = idx[key]
                return row[position] if 0 <= position < len(row) else ""

            if not cell("date"):
                continue
            entries.append({
                "date": cell("date"),
                "time": cell("time"),
                "type": cell("type"),
                "status": _detail_status(cell("status")),
                "teacher": cell("teacher"),
                "reason": cell("reason"),
            })
        if not entries:
            continue

        existing = courses.get(code)
        if existing and len(existing["entries"]) >= len(entries):
            continue
        courses[code] = {
            "code": code,
            "entries": entries,
            "present": sum(1 for e in entries if e["status"] == "present"),
            "absent": sum(1 for e in entries if e["status"] == "absent"),
            "recorded": len(entries),
            "selector": block.get("selector"),
        }
    return courses


def validate_detail(courses: dict[str, Any]) -> tuple[bool, str]:
    if not courses:
        return False, "no per-course class logs were parsed"
    for code, course in courses.items():
        if not course["entries"]:
            return False, f"{code} has no class entries"
        if course["present"] + course["absent"] > course["recorded"]:
            return False, f"{code} status counts exceed its row count"
    return True, "ok"


def _header_score(cells: list[str]) -> int:
    """How strongly a row looks like the header of an attendance table."""
    joined = " | ".join(c.lower() for c in cells)
    score = 0
    if "course" in joined or "subject" in joined:
        score += 2
    if "delivered" in joined or "held" in joined or "conducted" in joined:
        score += 2
    if "attended" in joined or "present" in joined:
        score += 2
    if "percent" in joined or "%" in joined or "attendance" in joined:
        score += 1
    return score


def _map_columns(cells: list[str]) -> dict[str, int]:
    """Map logical fields to column indexes using the header row."""
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(cells):
        cell = raw.lower().strip()
        if not cell:
            continue
        if "code" in cell and ("course" in cell or "subject" in cell):
            mapping.setdefault("code", idx)
        elif ("course" in cell or "subject" in cell) and (
            "descri" in cell or "name" in cell or "title" in cell
        ):
            mapping.setdefault("name", idx)
        elif "course" in cell or "subject" in cell:
            mapping.setdefault("course", idx)
        elif "delivered" in cell or "held" in cell or "conducted" in cell:
            mapping.setdefault("delivered", idx)
        elif "attended" in cell or ("present" in cell and "percent" not in cell):
            if "last" in cell or "duty" in cell:
                continue
            mapping.setdefault("attended", idx)
        elif "percent" in cell or cell in {"%", "%age"} or cell.endswith("%"):
            mapping.setdefault("percentage", idx)
    return mapping


def _row_is_total(cells: list[str], course_text: str) -> bool:
    head = clean(course_text).lower()
    joined = " ".join(cells).lower()
    if COURSE_CODE.search(course_text or ""):
        return False
    return any(word in head for word in TOTAL_WORDS) or (
        not head and any(word in joined for word in TOTAL_WORDS)
    )


def parse_attendance_rows(rows: list[list[str]]) -> dict[str, Any] | None:
    """Parse a candidate table into ``{courses, aggregate, headers}``.

    Returns ``None`` when the table is clearly not an attendance table. Never
    raises: an unparseable table is a diagnostic, not a crash.
    """
    normalized = [[clean(c) for c in row] for row in rows]
    normalized = [row for row in normalized if any(row)]
    if len(normalized) < 2:
        return None

    header_index, best_score = -1, 0
    for i, row in enumerate(normalized[:15]):
        score = _header_score(row)
        if score > best_score:
            header_index, best_score = i, score
    if header_index < 0 or best_score < 4:
        return None

    headers = normalized[header_index]
    mapping = _map_columns(headers)
    log.info("[UMS] Headers %s", headers)
    log.info("[UMS] Column mapping %s", mapping)

    if "delivered" not in mapping or "attended" not in mapping:
        log.info("[UMS] Table rejected: no delivered/attended columns in headers")
        return None

    courses: list[dict[str, Any]] = []
    aggregate: dict[str, Any] | None = None

    for row in normalized[header_index + 1:]:
        if len(row) < 2:
            continue

        def cell(key: str) -> str:
            idx = mapping.get(key, -1)
            return row[idx] if 0 <= idx < len(row) else ""

        def header_for(key: str) -> str:
            idx = mapping.get(key, -1)
            return headers[idx] if 0 <= idx < len(headers) else ""

        delivered = to_count(cell("delivered"), header_for("delivered"))
        attended = to_count(cell("attended"), header_for("attended"))
        if delivered is None or attended is None:
            continue

        code = cell("code")
        name = cell("name")
        course = cell("course")
        label = " ".join(x for x in (code, name) if x).strip() or course
        if not label:
            # Some GridViews put the course in the first column with no header.
            label = row[0]

        pct = to_percent(cell("percentage"))
        if pct is None:
            pct = to_percent(" ".join(row))

        if _row_is_total(row, label):
            if delivered > 0:
                aggregate = {
                    "delivered": delivered,
                    "attended": attended,
                    "percentage": pct,
                }
            continue

        if delivered <= 0:
            continue
        code_match = COURSE_CODE.search(label)
        courses.append({
            "course": label,
            "code": clean(code) or (code_match.group(1).replace(" ", "") if code_match else ""),
            "name": clean(name) or label,
            "delivered": delivered,
            "attended": attended,
            "percentage": pct if pct is not None else round(attended / delivered * 100, 1),
        })

    if not courses:
        log.info("[UMS] Table rejected: header matched but no usable course rows")
        return None

    if aggregate is None:
        delivered = sum(c["delivered"] for c in courses)
        attended = sum(c["attended"] for c in courses)
        aggregate = {
            "delivered": delivered,
            "attended": attended,
            "percentage": round(attended / delivered * 100, 1) if delivered else 0.0,
        }
    elif aggregate.get("percentage") is None and aggregate["delivered"]:
        aggregate["percentage"] = round(
            aggregate["attended"] / aggregate["delivered"] * 100, 1
        )

    return {
        "courses": courses,
        "aggregate": aggregate,
        "headers": headers,
        "raw_rows": normalized[header_index + 1: header_index + 4],
    }


def validate_attendance(parsed: dict[str, Any]) -> tuple[bool, str]:
    """Sanity-check parsed attendance. Returns ``(ok, reason)``.

    Validation exists to reject a mis-parsed table, not to reject unusual but
    real numbers, so aggregate mismatch is reported rather than fatal unless it
    is wildly inconsistent.
    """
    courses = parsed.get("courses") or []
    aggregate = parsed.get("aggregate") or {}

    if not courses:
        return False, "no course rows were parsed"

    for course in courses:
        delivered, attended = course["delivered"], course["attended"]
        if delivered <= 0:
            return False, f"{course['course']!r} has delivered={delivered}"
        if attended < 0 or attended > delivered:
            return False, (
                f"{course['course']!r} has attended={attended} > delivered={delivered}"
            )

    sum_delivered = sum(c["delivered"] for c in courses)
    sum_attended = sum(c["attended"] for c in courses)
    agg_delivered = aggregate.get("delivered") or 0
    agg_attended = aggregate.get("attended") or 0

    if agg_delivered and abs(agg_delivered - sum_delivered) > max(2, sum_delivered * 0.1):
        return False, (
            f"aggregate delivered {agg_delivered} does not match the sum of course "
            f"rows {sum_delivered}"
        )
    if agg_attended and abs(agg_attended - sum_attended) > max(2, sum_attended * 0.1):
        return False, (
            f"aggregate attended {agg_attended} does not match the sum of course "
            f"rows {sum_attended}"
        )

    pct = aggregate.get("percentage")
    if pct is not None and agg_delivered:
        computed = agg_attended / agg_delivered * 100
        if abs(computed - pct) > 2.0:
            return False, (
                f"aggregate percentage {pct} disagrees with {agg_attended}/"
                f"{agg_delivered} = {computed:.1f}"
            )

    return True, "ok"


def looks_like_attendance_text(text: str) -> bool:
    """Cheap pre-check used while waiting for the table to render."""
    lowered = (text or "").lower()
    if not COURSE_CODE.search(text or ""):
        return False
    return ("attend" in lowered) and ("deliver" in lowered or "%" in lowered)
