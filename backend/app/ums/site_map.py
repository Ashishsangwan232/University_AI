"""Read-only inventory of a UMS page: links, click handlers, panels, script names.

This exists because guessing at a portal's structure does not work. The
attendance table turned out to have no URL at all - it is loaded into a modal by
an inline ``getAtt()`` handler - and no amount of navigating would have found it.
Rather than repeat that for messages and announcements, this module dumps what is
actually on the page so the right target can be chosen from evidence.

It never clicks, submits, navigates, or changes anything. It reads the DOM.
"""
from __future__ import annotations

import re
from typing import Any

#: Everything on the page worth knowing about, in one round trip per frame.
MAP_JS = r"""
() => {
  const cssPath = (el) => {
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
  const sectionOf = (el) => {
    let node = el.parentElement;
    while (node) {
      if (node.id) return node.id;
      node = node.parentElement;
    }
    return '';
  };
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const seen = (rect) => rect.width > 0 && rect.height > 0;

  const links = [];
  for (const el of Array.from(document.querySelectorAll('a[href]')).slice(0, 1200)) {
    const href = el.getAttribute('href') || '';
    const text = clean(el.innerText || el.getAttribute('title') || el.getAttribute('aria-label'));
    if (!text && !href) continue;
    links.push({
      text: text.slice(0, 140), href: href.slice(0, 300), id: el.id || '',
      section: sectionOf(el), selector: cssPath(el), visible: seen(el.getBoundingClientRect())
    });
  }

  const handlers = [];
  for (const el of Array.from(document.querySelectorAll('[onclick]')).slice(0, 400)) {
    handlers.push({
      tag: el.tagName.toLowerCase(), id: el.id || '',
      text: clean(el.innerText || el.value).slice(0, 120),
      onclick: String(el.getAttribute('onclick') || '').slice(0, 240),
      selector: cssPath(el), visible: seen(el.getBoundingClientRect())
    });
  }

  const functions = [];
  for (const sc of Array.from(document.querySelectorAll('script:not([src])')).slice(0, 60)) {
    const code = sc.textContent || '';
    const re = /function\s+([A-Za-z_$][\w$]*)\s*\(/g;
    let m;
    while ((m = re.exec(code)) !== null && functions.length < 300) functions.push(m[1]);
  }

  const panels = [];
  for (const el of Array.from(document.querySelectorAll(
      'h1,h2,h3,h4,legend,.card-header,.panel-heading,.modal-title,.box-title')).slice(0, 300)) {
    const text = clean(el.innerText);
    if (!text || text.length > 90) continue;
    panels.push({
      tag: el.tagName.toLowerCase(), id: el.id || '', text,
      section: sectionOf(el), selector: cssPath(el), visible: seen(el.getBoundingClientRect())
    });
  }

  const tables = [];
  for (const t of Array.from(document.querySelectorAll('table')).slice(0, 60)) {
    const head = Array.from(t.querySelectorAll('tr')).slice(0, 1)
      .map(r => Array.from(r.querySelectorAll('th,td')).map(c => clean(c.innerText)).slice(0, 12))[0] || [];
    tables.push({
      id: t.id || '', selector: cssPath(t), rows: t.querySelectorAll('tr').length,
      headers: head, visible: seen(t.getBoundingClientRect())
    });
  }

  const ids = Array.from(document.querySelectorAll('[id]')).slice(0, 800)
    .map(e => e.id).filter(Boolean);

  return {
    url: location.href, title: document.title,
    links, handlers, functions: Array.from(new Set(functions)), panels, tables, ids
  };
}
"""

#: Feature -> words that would appear in a link, handler, or panel for it.
TOPICS: dict[str, tuple[str, ...]] = {
    "attendance": ("attend",),
    "messages": ("message", "inbox", "mail", "communicat", "chat", "compose", "sent items"),
    "announcements": ("announce", "notice", "circular", "bulletin", "news", "alert", "notification"),
    "timetable": ("timetable", "time table", "schedule", "datesheet", "date sheet", "class plan"),
    "leave": ("leave", "gate pass", "gatepass", "hostel out", "outing"),
    "exams": ("exam", "result", "grade", "marks", "cgpa", "reappear"),
    "fees": ("fee", "payment", "dues", "receipt", "challan"),
}

#: A link matching any of these is treated as an action, never auto-followed.
ACTION_WORDS = (
    "apply", "submit", "delete", "remove", "cancel", "pay", "logout", "sign out",
    "update", "save", "register", "withdraw", "request", "generate", "print",
    "upload", "confirm", "approve", "reject", "mark ",
)

DIGITS = re.compile(r"\b\d{6,}\b")


def _haystack(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("text", "href", "onclick", "id", "selector", "section")
    ).lower()


def is_action(item: dict[str, Any]) -> bool:
    """True when following this link could change something in the portal."""
    hay = _haystack(item)
    return any(word in hay for word in ACTION_WORDS)


def classify(item: dict[str, Any]) -> list[str]:
    hay = _haystack(item)
    return [topic for topic, words in TOPICS.items() if any(w in hay for w in words)]


def redact(value: str) -> str:
    """Mask long digit runs (registration numbers) before the map leaves the machine."""
    return DIGITS.sub("<digits>", value or "")


def build(frames: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine per-frame dumps into one map, tagged by topic."""
    links: list[dict[str, Any]] = []
    handlers: list[dict[str, Any]] = []
    panels: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    functions: set[str] = set()
    sections: dict[str, int] = {}

    for frame in frames:
        frame_url = frame.get("url", "")
        for item in frame.get("links", []):
            item["frame_url"] = frame_url
            item["topics"] = classify(item)
            item["action"] = is_action(item)
            item["text"] = redact(item.get("text", ""))
            sections[item.get("section") or "(none)"] = sections.get(item.get("section") or "(none)", 0) + 1
            links.append(item)
        for item in frame.get("handlers", []):
            item["frame_url"] = frame_url
            item["topics"] = classify(item)
            item["text"] = redact(item.get("text", ""))
            handlers.append(item)
        for item in frame.get("panels", []):
            item["frame_url"] = frame_url
            item["topics"] = classify(item)
            item["text"] = redact(item.get("text", ""))
            panels.append(item)
        for item in frame.get("tables", []):
            item["frame_url"] = frame_url
            item["headers"] = [redact(h) for h in item.get("headers", [])]
            tables.append(item)
        functions.update(frame.get("functions", []))

    by_topic = {
        topic: {
            "links": [item for item in links if topic in item["topics"]],
            "handlers": [item for item in handlers if topic in item["topics"]],
            "panels": [item for item in panels if topic in item["topics"]],
        }
        for topic in TOPICS
    }

    return {
        "pages": [{"url": f.get("url"), "title": f.get("title")} for f in frames],
        "counts": {
            "links": len(links), "handlers": len(handlers),
            "panels": len(panels), "tables": len(tables), "functions": len(functions),
        },
        "sections": dict(sorted(sections.items(), key=lambda kv: -kv[1])),
        "functions": sorted(functions),
        "by_topic": by_topic,
        "tables": tables,
        "links": links,
        "handlers": handlers,
        "panels": panels,
    }
