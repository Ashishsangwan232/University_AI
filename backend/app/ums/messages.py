"""The student's full UMS message store ("My Messages Repository").

The dashboard's "My Messages" panel only shows the latest ~15 messages. UMS
keeps the whole history (often 1000+) behind frmStudentsMyMessages.aspx, which
its own page reads through a JSON page method, 20 rows at a time, with optional
subject / description search done by UMS itself.

CampusAI calls that same method from the already-open UMS page with fetch():
read-only, no navigation and no clicks.
"""
from __future__ import annotations

import html
import re
from typing import Any

#: Runs inside the UMS page: same origin, the student's own session.
STORE_JS = r"""async ({ url, pageIndex, subject, description }) => {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ pageIndex, Subject: subject, Description: description }),
  });
  const text = await response.text();
  try {
    const data = JSON.parse(text);
    return { status: response.status, rows: data.d || data };
  } catch (e) {
    return { status: response.status, error: text.slice(0, 200) };
  }
}"""

_TAG = re.compile(r"<[^>]+>")
_BREAK = re.compile(r"<\s*(br|/p|/div|/li|/tr)\s*/?>", re.I)
_HREF = re.compile(r"""<a\b[^>]*href\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)


def html_to_text(raw: str) -> str:
    text = _BREAK.sub("\n", raw or "")
    text = html.unescape(_TAG.sub(" ", text))
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def links_in(raw: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for href, label in _HREF.findall(raw or ""):
        href = html.unescape(href).strip()
        if not href.lower().startswith(("http://", "https://")) or href in seen:
            continue
        seen.add(href)
        out.append({"text": html_to_text(label)[:120] or href, "href": href})
    return out[:6]


def no_records(rows: list[dict[str, Any]]) -> bool:
    return not rows or str(rows[0].get("Subject") or "").strip().lower() == "no record found"


def parse_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Repository rows -> CampusAI message records (newest first, as UMS sends them)."""
    if no_records(rows):
        return []
    records = []
    for row in rows:
        body_html = str(row.get("Announcement") or "")
        file_name = str(row.get("FileName") or "").strip()
        records.append({
            "sr_no": str(row.get("SrNo") or ""),
            "title": html_to_text(str(row.get("Subject") or ""))[:300] or "(no subject)",
            "sender": "",
            "date": str(row.get("AnnouncementDate") or "").strip(),
            "body": html_to_text(body_html)[:4000],
            "links": links_in(body_html),
            # The file itself is downloaded from the UMS messages page.
            "attachments": [{"name": file_name, "href": ""}] if file_name and file_name != "undefined" else [],
            "channel": "repository",
        })
    return records


def dedupe_messages(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per message. SrNo is only a row number within one search, so
    it cannot identify a message; subject + date + text can. UMS also stores
    some notices twice - those are shown once too."""
    seen: set[str] = set()
    out = []
    for record in records:
        key = "|".join((
            re.sub(r"\s+", " ", record.get("title") or "").strip().lower(),
            (record.get("date") or "").strip(),
            re.sub(r"\s+", " ", record.get("body") or "").strip().lower()[:300],
        ))
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def row_totals(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """(total messages matching, page count) as UMS reports them."""
    if no_records(rows):
        return 0, 0
    first = rows[0]
    try:
        return int(first.get("TotalMessages") or 0), int(first.get("PageCount") or 0)
    except (TypeError, ValueError):
        return len(rows), 1
