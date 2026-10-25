"""Extraction of UMS card-style panels: announcements and messages.

The site map showed these are not tables. Attendance lives in a ``<table>`` with
headers; announcements live in ``#tAC`` and messages in ``#MyMessage`` as a list
of sibling ``<div>`` cards, each holding a heading, a date, some body text, and
attachment links.

So the extractor is structural rather than column-based: every direct child of a
container is one item, and its own text lines are classified. That survives class
name churn, which a selector-per-field parser would not.

Playwright-free so it can be unit tested against captured DOM dumps.
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger("campusai.ums")

#: One round trip per container: every direct child, with its text lines and links.
CARDS_JS = r"""
(cfg) => {
  const root = document.querySelector(cfg.selector);
  if (!root) return null;
  const tidy = (s) => (s || '').replace(/[ \t ]+/g, ' ').trim();
  const children = Array.from(root.children);
  const items = [];
  for (let i = 0; i < children.length && items.length < cfg.max; i++) {
    const child = children[i];
    const raw = child.innerText || child.textContent || '';
    const lines = raw.split('\n').map(tidy).filter(Boolean);
    if (!lines.length) continue;
    const pick = (selectors) => {
      for (const sel of selectors) {
        const el = child.querySelector(sel);
        if (el) {
          const t = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
          // How many siblings match the SAME selector: 1 for an announcement,
          // 2 for a message row (header + body), many for a wrapper element
          // that contains every item at once.
          if (t) return { text: t, count: child.querySelectorAll(sel).length };
        }
      }
      return { text: '', count: 0 };
    };
    const links = Array.from(child.querySelectorAll('a[href]')).slice(0, 12).map(a => ({
      text: tidy(a.innerText) || (a.getAttribute('href') || '').split('/').pop(),
      href: a.getAttribute('href') || ''
    }));
    const title = pick(cfg.titleSelectors);
    items.push({
      index: i,
      heading: title.text,
      titleCount: title.count,
      dateField: pick(cfg.dateSelectors).text,
      bodyField: pick(cfg.bodySelectors).text,
      lines: lines.slice(0, cfg.maxLines),
      links,
      selector: cfg.selector + ' > :nth-child(' + (i + 1) + ')'
    });
  }
  return { selector: cfg.selector, children: children.length, items };
}
"""

#: Structural probe for designing a parser against an unfamiliar container.
INSPECT_JS = r"""
(cfg) => {
  const tidy = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const root = document.querySelector(cfg.selector);
  if (!root) return { selector: cfg.selector, exists: false };
  const rect = root.getBoundingClientRect();
  const walk = (el, depth) => {
    if (depth > cfg.depth) return null;
    const text = tidy(el.innerText || el.textContent);
    return {
      tag: el.tagName.toLowerCase(),
      id: el.id || '',
      cls: (el.className && el.className.toString ? el.className.toString() : '').slice(0, 90),
      textLength: text.length,
      sample: text.slice(0, 90),
      children: Array.from(el.children).slice(0, cfg.breadth)
        .map(c => walk(c, depth + 1)).filter(Boolean)
    };
  };
  const out = {
    selector: cfg.selector, exists: true,
    visible: rect.width > 0 && rect.height > 0,
    childCount: root.children.length,
    tree: walk(root, 0)
  };
  if (cfg.html) {
    out.samples = Array.from(root.children).slice(0, cfg.samples)
      .map(c => c.outerHTML.slice(0, cfg.htmlChars));
  }
  return out;
}
"""

DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(
        r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,?\s+\d{4}\b", re.I
    ),
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b", re.I
    ),
]

#: Lines that are chrome, not content.
NOISE = re.compile(
    r"^(read more|view details|click here.*|show more|less|more|close|x|×|new|"
    r"my messages|search messages|announcements|uploaded by:?|\W*)$",
    re.I,
)

#: A card made only of these is panel chrome, not content.
CHROME_ONLY = re.compile(r"^(my messages|search messages|close|×|x|announcements)$", re.I)

#: LPU stamps every announcement with a reference code; it belongs in its own
#: field, not in the middle of the title. The codes nest one level of brackets -
#: "LPU/10.2/ANN(EXAM)/2024/023(23.4)(Vol-9)/IC/260907/0035" - so a plain
#: "[^)]*" stops at ANN(EXAM and leaves the rest stranded in the title. Worse,
#: that truncated prefix is shared by dozens of notices, so it collapses
#: unrelated announcements together during dedupe.
REFERENCE = re.compile(r"\(\s*(LPU/(?:[^()]|\([^()]*\))*?)\s*\)")

#: Message headers read "SUBJECT - By SENDER (Sep 07, 2026)".
MESSAGE_HEADER = re.compile(
    r"^(?P<title>.+?)\s+-\s+By\s+(?P<sender>[^()]{1,80}?)\s*"
    r"(?:\(\s*(?P<date>[^)]{4,40})\s*\))?\s*$"
)

ATTACHMENT_EXT = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                  ".jpg", ".jpeg", ".png", ".gif", ".zip", ".csv", ".txt")


def find_date(lines: list[str]) -> tuple[str | None, int]:
    """First line containing a date, and its index."""
    for index, line in enumerate(lines):
        for pattern in DATE_PATTERNS:
            match = pattern.search(line)
            if match:
                return match.group(0), index
    return None, -1


def clean_href(href: str) -> str:
    """UMS emits some broken hrefs: a bare ``http://`` for e-mail text, and
    ``http://https://real-url`` for external links."""
    # Some UMS hrefs run on past a newline into the next line's text.
    href = re.split(r"[\r\n]", href or "")[0].strip()
    if href.startswith("http://https://") or href.startswith("http://http://"):
        href = href[len("http://"):]
    if href in ("http://", "https://", "#", ""):
        return ""
    return href


def is_attachment(link: dict[str, Any]) -> bool:
    href = clean_href(link.get("href")).lower().split("?")[0]
    return href.endswith(ATTACHMENT_EXT)


#: A card holding more title elements than this is a wrapper around many items,
#: not an item. The "All Messages" modal loads every message into one element;
#: without this guard it becomes a single bogus card whose links and body are
#: scavenged from unrelated messages.
MAX_TITLE_ELEMENTS = 4


def parse_card(
    item: dict[str, Any], source_url: str = "", channel: str = "", max_titles: int = MAX_TITLE_ELEMENTS
) -> dict[str, Any] | None:
    """Turn one container child into a titled, dated, attributed record.

    Prefers the fields UMS actually marks up - ``.announcement-subject``,
    ``.announcement-date``, ``.panel-body``, ``p.text-small`` - and only falls
    back to classifying raw text lines when a container has no such markup.
    """
    if (item.get("titleCount") or 0) > max_titles:
        log.info(
            "[UMS] Skipping %s: %d title elements means it wraps many items, not one",
            item.get("selector"), item["titleCount"],
        )
        return None

    raw_lines = item.get("lines") or []
    lines = [line for line in raw_lines if line and not NOISE.fullmatch(line)]
    # A card whose visible lines are all chrome can still be real when UMS marked
    # up the fields properly, so only bail out when there is nothing at all.
    if not lines and not (item.get("heading") or item.get("bodyField")):
        return None

    heading = (item.get("heading") or "").strip()
    date = (item.get("dateField") or "").strip() or None
    body = (item.get("bodyField") or "").strip()
    line_date, date_index = find_date(raw_lines)

    if not heading:
        for index, line in enumerate(lines):
            if index != date_index and len(line) <= 160:
                heading = line
                break
        heading = heading or lines[0]

    # "SUBJECT - By SENDER (Sep 07, 2026)" -> three fields.
    sender = ""
    match = MESSAGE_HEADER.match(heading)
    if match and match.group("sender"):
        heading = match.group("title").strip()
        sender = match.group("sender").strip()
        date = date or (match.group("date") or "").strip() or None

    # "New" is a badge, not part of the subject.
    heading = re.sub(r"^new\s+", "", heading, flags=re.I).strip()

    reference = ""
    ref_match = REFERENCE.search(heading)
    if ref_match:
        reference = ref_match.group(1).strip()
        heading = REFERENCE.sub("", heading).strip(" -–—:")

    if not body:
        body_lines = [
            line for line in lines
            if line != heading
            and (line_date is None or line_date not in line or len(line) > len(line_date) + 40)
        ]
        body = " ".join(body_lines).strip()
    if not reference:
        ref_match = REFERENCE.search(body)
        if ref_match:
            reference = ref_match.group(1).strip()
    date = date or line_date

    # A panel wrapper is never a card. Once "All Messages" loads, the modal
    # holds every message at once, which would otherwise become one giant
    # bogus item titled "My Messages".
    if CHROME_ONLY.match(heading or ""):
        return None

    links: list[dict[str, str]] = []
    attachments: list[dict[str, str]] = []
    seen_hrefs: set[str] = set()
    for link in item.get("links") or []:
        href = clean_href(link.get("href"))
        if not href or href in seen_hrefs:
            # UMS often renders the same URL twice - once with the full address
            # as the link text and once with a fragment of it. Keep the first.
            continue
        seen_hrefs.add(href)
        name = (link.get("text") or href.split("/")[-1]).strip()
        if is_attachment({"href": href}):
            attachments.append({"name": name[:160], "href": href})
        else:
            links.append({"text": name[:120], "href": href})

    record = {
        "title": (heading or "")[:300],
        "sender": sender[:120],
        "date": date,
        "reference": reference[:160],
        "body": body[:4000],
        "attachments": attachments[:8],
        "links": links[:6],
        "channel": channel,
        "source_url": source_url,
        "selector": item.get("selector"),
    }
    if not record["title"] and not record["body"]:
        return None
    return record


def parse_cards(
    payload: dict[str, Any] | None,
    source_url: str = "",
    channel: str = "",
    max_titles: int = MAX_TITLE_ELEMENTS,
) -> list[dict[str, Any]]:
    if not payload:
        return []
    records = [
        parse_card(item, source_url, channel, max_titles)
        for item in payload.get("items") or []
    ]
    return [record for record in records if record]


def _merge(existing: dict[str, Any], record: dict[str, Any]) -> None:
    """Fold a duplicate into the copy already kept."""
    channels = {c for c in (existing.get("channel"), record.get("channel")) if c}
    existing["channel"] = ",".join(sorted(channels))
    if len(record.get("body") or "") > len(existing.get("body") or ""):
        existing["body"] = record["body"]
    if not existing.get("date") and record.get("date"):
        existing["date"] = record["date"]
    if not existing.get("sender") and record.get("sender"):
        existing["sender"] = record["sender"]
    for key in ("attachments", "links"):
        for entry in record.get(key) or []:
            if entry not in existing[key]:
                existing[key].append(entry)


def _collapse(records: list[dict[str, Any]], key_of) -> list[dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for record in records:
        key = (key_of(record) or "").lower().strip()
        if not key:
            order.append(f"__unique_{len(order)}")
            index[order[-1]] = record
            continue
        if key in index:
            _merge(index[key], record)
            continue
        index[key] = record
        order.append(key)
    return [index[key] for key in order]


def dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse repeats in two passes.

    First by reference code, which catches the same notice read from both the
    dashboard panel and the modal. Then by content, because LPU also posts the
    identical announcement into the general and personal tabs under *different*
    reference codes - the SBI scholarship and the dMAT notice each appear twice
    that way. Channels, attachments and links are merged, so nothing is lost.
    """
    by_reference = _collapse(records, lambda r: r.get("reference") or "")
    return _collapse(
        by_reference,
        lambda r: f"{(r.get('title') or '')[:120]}|{(r.get('body') or '')[:200]}",
    )


def validate_cards(records: list[dict[str, Any]], kind: str) -> tuple[bool, str]:
    """Reject an empty or obviously wrong extraction rather than serving junk."""
    if not records:
        return False, f"no {kind} were parsed from the panel"
    substantive = [r for r in records if len(r["title"]) > 3 or len(r["body"]) > 10]
    if not substantive:
        return False, f"{len(records)} {kind} found but all were empty"
    if all(r["title"] == records[0]["title"] for r in records) and len(records) > 3:
        return False, f"every parsed {kind} has the same title - the container is probably wrong"
    return True, "ok"
