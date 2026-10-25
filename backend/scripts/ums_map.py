"""Map the UMS portal so features can be built from evidence instead of guesses.

    python scripts/ums_map.py                    # dashboard only, read-only
    python scripts/ums_map.py --visit            # also open safe message/notice pages
    python scripts/ums_map.py --visit --topics messages,announcements,timetable
    python scripts/ums_map.py --topics all       # inventory tagged for every feature

Run it with UMS open and logged in, in the CampusAI browser.

Without --visit nothing is navigated or clicked at all: it reads the DOM of the
page that is already open. With --visit it additionally opens a few report pages
by direct URL, skipping anything that looks like an action (apply, submit, pay,
delete, ...), then returns the browser to where it started.

The full map is written to data/ums/ums_map.json. That file contains link text
from your portal, which may include your name; long digit runs such as a
registration number are masked automatically. Look it over before sharing it.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[1] / "data" / "ums" / "ums_map.json"


def call(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read() or b"{}")
        detail = body.get("detail")
        message = detail.get("message") if isinstance(detail, dict) else detail
        return {"error": message or f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"backend unreachable at {BASE}: {exc}"}


def show_items(items: list[dict], limit: int, kind: str) -> None:
    if not items:
        print(f"    (no {kind})")
        return
    for item in items[:limit]:
        flags = []
        if not item.get("visible"):
            flags.append("hidden")
        if item.get("action"):
            flags.append("ACTION")
        suffix = f"  [{', '.join(flags)}]" if flags else ""
        print(f"    {item.get('text') or '(no text)'!r}{suffix}")
        if item.get("href"):
            print(f"        href     {item['href']}")
        if item.get("onclick"):
            print(f"        onclick  {item['onclick']}")
        if item.get("section"):
            print(f"        section  #{item['section']}")
        print(f"        selector {item.get('selector', '')}")
    if len(items) > limit:
        print(f"    ... and {len(items) - limit} more (see {OUT.name})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--visit", action="store_true",
                        help="also open safe report pages by URL")
    parser.add_argument("--topics", default="messages,announcements",
                        help="comma-separated topics, or 'all'")
    parser.add_argument("--max-visits", type=int, default=6)
    args = parser.parse_args()

    if args.topics.strip().lower() == "all":
        topics = ["attendance", "messages", "announcements", "timetable", "leave", "exams", "fees"]
    else:
        topics = [t.strip() for t in args.topics.split(",") if t.strip()]

    if args.visit:
        print(f"Opening up to {args.max_visits} safe page(s) for: {', '.join(topics)}\n")
        data = call("/api/ums/map/crawl", {"topics": topics, "max_visits": args.max_visits})
    else:
        data = call("/api/ums/map")

    if data.get("error"):
        print(data["error"])
        return 1

    print(f"page   : {data['origin']}")
    for page in data["pages"]:
        print(f"frame  : {page['title']!r}  {page['url']}")
    counts = data["counts"]
    print(f"found  : {counts['links']} links, {counts['handlers']} click handlers, "
          f"{counts['panels']} panels, {counts['tables']} tables, {counts['functions']} script functions")

    print("\nmenu sections (by link count)")
    for section, count in list(data["sections"].items())[:12]:
        print(f"    #{section:<24} {count}")

    for topic in topics:
        bucket = data["by_topic"].get(topic) or {}
        links = bucket.get("links") or []
        handlers = bucket.get("handlers") or []
        panels = bucket.get("panels") or []
        print(f"\n=== {topic.upper()}  ({len(links)} links, {len(handlers)} handlers, {len(panels)} panels)")
        print("  links:")
        show_items(links, 12, "links")
        print("  click handlers (these load panels in place, like attendance did):")
        show_items(handlers, 8, "handlers")
        if panels:
            print("  panel headings:")
            for panel in panels[:8]:
                print(f"    {panel['text']!r}  #{panel.get('id') or panel.get('section')}")

    interesting = [f for f in data["functions"]
                   if any(k in f.lower() for k in
                          ("msg", "message", "announce", "notice", "news", "alert", "att", "get", "load", "show"))]
    print(f"\ninline script functions that look like loaders ({len(interesting)} of {counts['functions']}):")
    print("   ", ", ".join(interesting[:60]) or "(none)")

    if data.get("visited"):
        print("\n=== PAGES OPENED")
        for visit in data["visited"]:
            print(f"\n  {visit['link_text']!r}  ({visit['topic']})")
            print(f"    url    {visit['landed']}")
            print(f"    title  {visit['title']!r}")
            for table in visit["tables"][:6]:
                if table["headers"]:
                    print(f"    table  {table['rows']} rows  {table['headers']}")
    if data.get("skipped"):
        print("\n  skipped:")
        for skip in data["skipped"]:
            print(f"    {skip['url']}  ({skip['error']})")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\nFull map written to {OUT}")
    print("It contains link text from your portal. Long digit runs are masked; "
          "check it before sharing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
