"""Read-only extraction of the UMS hostel leave page.

``frmStudentHostelLeaveApplicationTermWise.aspx`` is a form: term and leave-type
dropdowns, date/time fields, a reason box, an acknowledgement checkbox, and a
Submit button. It also *displays* the two things worth reading - the Day Leave
and Night Leave balances, and who recommends and sanctions your leave.

This module reads that page and nothing else. There is deliberately no code path
here or in the service that fills a field, ticks the checkbox, or clicks Submit
or Reset: applying for leave stays a decision the student makes themselves, in
their own browser. The service opens the page with a plain GET and navigates
back afterwards.

Playwright-free, so it can be unit tested against captured DOM.
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger("campusai.ums")

#: Reads the page. Queries only - no clicks, no typing, no form submission.
LEAVE_JS = r"""
(cfg) => {
  const tidy = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const valueOf = (cell) => {
    const field = cell.querySelector('input,textarea,select');
    if (field) {
      if (field.tagName.toLowerCase() === 'select') {
        const option = field.options[field.selectedIndex];
        return tidy(option ? option.text : '');
      }
      if (field.type === 'checkbox' || field.type === 'radio') return field.checked ? 'yes' : 'no';
      return tidy(field.value);
    }
    return tidy(cell.innerText || cell.textContent);
  };

  // The nearest short piece of text before an element - "Day Leave Details"
  // often sits outside the table it captions.
  const headingFor = (el) => {
    const own = el.querySelector('caption');
    if (own) {
      const text = tidy(own.innerText || own.textContent);
      if (text) return text;
    }
    // Side-by-side layout: "Day Leave Details" and "Night Leave Details" are
    // header cells of the WRAPPER table, one per column, and each column holds
    // one nested balance table. So the caption is the header cell sharing this
    // table's column index - not anything before the table itself.
    const cell = el.closest ? el.closest('td,th') : null;
    if (cell && cell.parentElement) {
      const column = Array.from(cell.parentElement.children).indexOf(cell);
      const wrapper = cell.closest('table');
      if (wrapper) {
        for (const row of Array.from(wrapper.rows || []).slice(0, 3)) {
          const header = row.cells ? row.cells[column] : null;
          if (!header || header.contains(el)) continue;
          const text = tidy(header.innerText || header.textContent);
          if (text && text.length <= 80) return text;
        }
      }
    }
    let node = el, hops = 0;
    while (node && hops < 5) {
      let prev = node.previousElementSibling;
      while (prev) {
        const text = tidy(prev.innerText || prev.textContent);
        if (text && text.length <= 80) return text;
        prev = prev.previousElementSibling;
      }
      node = node.parentElement;
      hops++;
    }
    return '';
  };

  const tables = Array.from(document.querySelectorAll('table')).slice(0, 60).map(t => {
    const rows = Array.from(t.querySelectorAll('tr')).slice(0, 200).map(r =>
      Array.from(r.querySelectorAll('th,td')).map(c => tidy(c.innerText || c.textContent))
    ).filter(r => r.length);
    return {
      rows,
      heading: headingFor(t),
      // A layout wrapper holds other tables; a real balance table does not.
      nested: t.querySelectorAll('table').length > 0
    };
  });

  // Label/value pairs from the form's table layout: "<td>VID :</td><td>124...</td>"
  const fields = [];
  const cells = Array.from(document.querySelectorAll('td,th')).slice(0, 600);
  for (let i = 0; i < cells.length; i++) {
    const label = tidy(cells[i].innerText || cells[i].textContent);
    if (!label || label.length > 60 || !/[:：]\s*$/.test(label)) continue;
    let value = '';
    for (let j = i + 1; j < Math.min(i + 3, cells.length); j++) {
      value = valueOf(cells[j]);
      if (value) break;
    }
    fields.push({ label: label.replace(/[:：]\s*$/, '').trim(), value: value.slice(0, 200) });
    if (fields.length >= 40) break;
  }

  // This page carries several forms (an OTP dialog, a suggestion box), so a
  // dropdown has to be identified by its own label, not by position.
  const labelFor = (el) => {
    if (el.id) {
      const tag = document.querySelector('label[for="' + el.id + '"]');
      if (tag) return tidy(tag.innerText || tag.textContent);
    }
    const cell = el.closest ? el.closest('td,th') : null;
    if (cell && cell.previousElementSibling) {
      return tidy(cell.previousElementSibling.innerText || cell.previousElementSibling.textContent);
    }
    return '';
  };

  const selects = Array.from(document.querySelectorAll('select')).slice(0, 20).map(s => ({
    id: s.id || '', name: s.name || '', label: labelFor(s),
    selected: tidy(s.options[s.selectedIndex] ? s.options[s.selectedIndex].text : ''),
    options: Array.from(s.options).slice(0, 40).map(o => tidy(o.text)).filter(Boolean)
  }));

  // Recorded for transparency only - nothing here is ever clicked.
  const buttons = Array.from(document.querySelectorAll(
    'input[type=submit],input[type=button],button')).slice(0, 12)
    .map(b => tidy(b.value || b.innerText)).filter(Boolean);

  return { url: location.href, title: document.title, tables, fields, selects, buttons };
}
"""

#: Locates the leave form's writable fields BY LABEL, and refuses to return
#: anything else. The refusal is the safety mechanism: a checkbox, submit,
#: button or hidden input is never handed back, so no bug downstream can target
#: the acknowledgement or one of the page's three Submit controls.
LOCATE_JS = r"""
(cfg) => {
  const tidy = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const WRITABLE = new Set(['text', 'textarea', 'search', 'tel', 'url', 'date',
                            'datetime-local', 'time', 'select-one']);
  const pathOf = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 8) {
      if (node.id) { parts.unshift('#' + CSS.escape(node.id)); break; }
      let part = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter(c => c.tagName === node.tagName);
        if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(node) + 1) + ')';
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  };

  const out = [];
  const cells = Array.from(document.querySelectorAll('td,th')).slice(0, 600);
  for (const wanted of cfg.labels) {
    const target = wanted.toLowerCase().replace(/[:：]\s*$/, '').trim();
    let found = null;
    for (let i = 0; i < cells.length && !found; i++) {
      const label = tidy(cells[i].innerText || cells[i].textContent)
        .toLowerCase().replace(/[:：]\s*$/, '').trim();
      if (label !== target) continue;
      for (let j = i + 1; j < Math.min(i + 3, cells.length) && !found; j++) {
        const field = cells[j].querySelector('input,textarea,select');
        if (!field) continue;
        const tag = field.tagName.toLowerCase();
        const kind = tag === 'select' ? 'select-one'
                   : tag === 'textarea' ? 'textarea'
                   : (field.type || 'text').toLowerCase();
        // Anything not plainly writable is refused, not returned.
        if (!WRITABLE.has(kind)) { found = { label: wanted, refused: kind }; break; }
        if (field.disabled || field.readOnly) { found = { label: wanted, refused: 'readonly' }; break; }
        found = {
          label: wanted, selector: pathOf(field), tag, kind,
          options: tag === 'select'
            ? Array.from(field.options).map(o => tidy(o.text)).filter(Boolean) : [],
          value: tag === 'select'
            ? tidy(field.options[field.selectedIndex] ? field.options[field.selectedIndex].text : '')
            : tidy(field.value)
        };
      }
    }
    out.push(found || { label: wanted, missing: true });
  }
  return out;
}
"""

BALANCE_WORDS = ("total", "availed", "used", "balance", "remaining", "pending")
#: A real balance table is caption + header + three rows. Anything longer is a
#: layout wrapper holding both the Day and Night tables at once - and reading
#: that yields the *last* table's figures silently, which is worse than failing.
MAX_BALANCE_ROWS = 8
#: Label that identifies the leave-type dropdown among the page's other forms.
LEAVE_TYPE_LABEL = re.compile(r"leave\s*type", re.I)
TERM_LABEL = re.compile(r"\bterm\b", re.I)
#: Which balance table is which, from its own caption row.
DAY_HINT = re.compile(r"\bday\b", re.I)
NIGHT_HINT = re.compile(r"\bnight\b", re.I)

#: Field labels worth surfacing, mapped to stable keys.
FIELD_MAP = {
    "vid": "student_id",
    "name": "name",
    "hostel": "hostel",
    "room no": "room",
    "select term": "term",
    "term": "term",
    "mobile no": "mobile",
    "visit place": "visit_place",
    "recommending authority": "recommending_authority",
    "sanctioning authority": "sanctioning_authority",
}

#: Labels that are inputs for an application the student has not made yet.
BLANK_FORM_LABELS = {
    "leave type", "start date & time of leave", "leave ending date time", "reason of leaving",
}


def _number(value: str) -> int | None:
    match = re.search(r"-?\d+", (value or "").replace(",", ""))
    return int(match.group(0)) if match else None


def _balance_from_rows(rows: list[list[str]]) -> dict[str, int] | None:
    """A balance table is Type/Count rows: Total, Availed, Balance."""
    found: dict[str, int] = {}
    for row in rows:
        cells = [c.strip() for c in row if c and c.strip()]
        if len(cells) < 2:
            continue
        for index, cell in enumerate(cells):
            key = cell.lower().strip(" :")
            if key not in BALANCE_WORDS:
                continue
            for candidate in cells[index + 1:]:
                number = _number(candidate)
                if number is not None:
                    found[{"used": "availed", "remaining": "balance"}.get(key, key)] = number
                    break
            break
    return found or None


def parse_leave(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Balances, profile context and available leave types. Reads only."""
    if not payload:
        return None

    balances: dict[str, dict[str, int]] = {}
    unlabelled: list[dict[str, int]] = []
    captions: list[dict[str, Any]] = []
    skipped: list[str] = []
    for table in payload.get("tables") or []:
        rows = table.get("rows") or []
        if not rows:
            continue
        if table.get("nested"):
            skipped.append("nested-wrapper")
            continue
        if len(rows) > MAX_BALANCE_ROWS:
            skipped.append(f"too-many-rows:{len(rows)}")
            continue
        parsed = _balance_from_rows(rows)
        if not parsed or "balance" not in parsed:
            continue
        # The caption can be the table's own first rows, a heading beside it, or
        # the wrapper's header cell above its column.
        caption = " ".join([table.get("heading") or ""] + [" ".join(r) for r in rows[:2]])
        captions.append({"caption": caption.strip()[:120], "parsed": parsed})
        if NIGHT_HINT.search(caption):
            balances["night"] = parsed
        elif DAY_HINT.search(caption):
            balances["day"] = parsed
        else:
            # Unidentified, but never thrown away: a second unlabelled table
            # used to overwrite nothing and simply vanish. Keep every one, and
            # report the captions so the mismatch is visible rather than silent.
            unlabelled.append(parsed)

    for index, parsed in enumerate(unlabelled, start=1):
        if parsed in balances.values():
            continue
        balances[f"leave {index}" if len(unlabelled) > 1 else "leave"] = parsed

    profile: dict[str, str] = {}
    other: list[dict[str, str]] = []
    for field in payload.get("fields") or []:
        label = (field.get("label") or "").strip()
        value = (field.get("value") or "").strip()
        key = FIELD_MAP.get(label.lower())
        if key:
            if value and not profile.get(key):
                profile[key] = value
        elif label.lower() not in BLANK_FORM_LABELS and value:
            other.append({"label": label, "value": value})

    # Identify dropdowns by their own label. Guessing by position picked up the
    # suggestion-box dropdown ("Innovation", "Improve Efficiency", ...) instead.
    leave_types: list[str] = []
    terms: list[str] = []
    for select in payload.get("selects") or []:
        options = [
            o for o in select.get("options") or []
            if o.lower().strip() not in ("select", "--select--", "select aim", "-select-")
        ]
        if not options:
            continue
        blob = f"{select.get('label', '')} {select.get('id', '')} {select.get('name', '')}"
        if LEAVE_TYPE_LABEL.search(blob):
            leave_types = leave_types or options
        elif TERM_LABEL.search(blob) or any("term-" in o.lower() for o in options[:3]):
            terms = terms or options

    log.info(
        "[UMS] Leave page: %d balance table(s), %d profile field(s), %d leave type(s)",
        len(balances), len(profile), len(leave_types),
    )
    return {
        "balances": balances,
        "profile": profile,
        "leave_types": leave_types,
        "terms": terms,
        "other_fields": other[:12],
        # De-duplicated: the page carries several forms, each with its own Submit.
        "controls_present": sorted(set(payload.get("buttons") or [])),
        "tables_skipped": skipped,
        # What each accepted balance table was captioned, so a day/night mix-up
        # can be diagnosed from the output instead of another DOM probe.
        "balance_captions": captions,
        "page_url": payload.get("url"),
        "page_title": payload.get("title"),
    }


def validate_leave(record: dict[str, Any] | None) -> tuple[bool, str]:
    if not record:
        return False, "the hostel leave page returned nothing"
    if not record.get("balances"):
        return False, "no leave balance table was found on the page"
    for kind, balance in record["balances"].items():
        if "balance" not in balance:
            return False, f"the {kind} table has no balance figure"
        total, availed = balance.get("total"), balance.get("availed")
        if total is not None and availed is not None:
            if availed > total:
                return False, f"{kind}: availed {availed} exceeds total {total}"
            if balance["balance"] != total - availed:
                return False, (
                    f"{kind}: balance {balance['balance']} does not equal "
                    f"total {total} - availed {availed}"
                )
    return True, "ok"


def summarise(record: dict[str, Any]) -> str:
    """One line a student or the agent can read."""
    parts = []
    for kind, balance in (record.get("balances") or {}).items():
        if not balance:
            continue
        label = kind if kind.startswith("leave") else f"{kind} leave"
        parts.append(
            f"{label} {balance.get('balance')} left"
            + (f" of {balance['total']}" if balance.get("total") is not None else "")
        )
    return "; ".join(parts) or "no leave balances found"
