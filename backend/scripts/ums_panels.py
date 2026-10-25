"""Print everything CampusAI reads live from UMS.

    python scripts/ums_panels.py                # announcements, messages, timetable, leave
    python scripts/ums_panels.py --announcements
    python scripts/ums_panels.py --messages
    python scripts/ums_panels.py --timetable
    python scripts/ums_panels.py --leave        # balances only; never submits anything
    python scripts/ums_panels.py --force        # re-read instead of using the cache
    python scripts/ums_panels.py --full         # full body text, not the first 300 chars
    python scripts/ums_panels.py --json         # raw JSON

Requires the backend running and UMS connected and signed in.

Exists so you never have to fight PowerShell over curl: on Windows `curl` is an
alias for Invoke-WebRequest, which parses HTML and prompts before doing it. If
you do want to use curl there, call `curl.exe` explicitly.
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path: str) -> dict:
    try:
        with urllib.request.urlopen(BASE + path, timeout=180) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read() or b"{}")
        detail = body.get("detail")
        message = detail.get("message") if isinstance(detail, dict) else detail
        return {"error": message or f"HTTP {exc.code}", "status": exc.code}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"backend unreachable at {BASE}: {exc}"}


def show_timetable(data: dict) -> None:
    print(f"\n{'=' * 70}\nTIMETABLE")
    if data.get("error"):
        print(f"  unavailable: {data['error']}")
        return
    classes = data.get("classes") or []
    print(f"  {len(classes)} slot(s) from {data.get('source')}")
    if data.get("attempts"):
        print(f"  steps: {data['attempts']}")
    day = None
    for item in classes:
        if item["day"] != day:
            day = item["day"]
            print(f"\n  {day or 'Unscheduled'}")
        bits = [item["room"], item.get("type_label") or item.get("type"), item.get("group")]
        detail = " · ".join(b for b in bits if b)
        print(f"     {item['time']}-{item['end']}  {item['subject']:<10} {detail}")


def show_leave(data: dict) -> None:
    print(f"\n{'=' * 70}\nHOSTEL LEAVE  (read only - CampusAI never submits)")
    if data.get("error"):
        print(f"  unavailable: {data['error']}")
        return
    print(f"  source: {data.get('source')}   read_only={data.get('read_only')}")
    for kind, balance in (data.get("balances") or {}).items():
        print(f"  {kind:<6} total={balance.get('total')}  availed={balance.get('availed')}"
              f"  balance={balance.get('balance')}")
    profile = data.get("profile") or {}
    for key in ("hostel", "room", "term", "recommending_authority", "sanctioning_authority"):
        if profile.get(key):
            print(f"  {key:<24} {profile[key]}")
    if data.get("leave_types"):
        print(f"  leave types              {', '.join(data['leave_types'])}")
    if data.get("controls_present"):
        print(f"  controls on the page     {data['controls_present']}  (seen, never clicked)")
    captions = data.get("balance_captions") or []
    if captions and any(k.startswith("leave") for k in (data.get("balances") or {})):
        print("  balance tables could not be identified as day/night; captions seen:")
        for entry in captions:
            print(f"     {entry['caption']!r} -> {entry['parsed']}")
    if data.get("tables_skipped"):
        print(f"  tables skipped           {data['tables_skipped']}")


def show(kind: str, data: dict, full: bool, wrap: int = 96) -> None:
    print(f"\n{'=' * 70}\n{kind.upper()}")
    if data.get("error"):
        print(f"  unavailable: {data['error']}")
        return

    items = data.get("items") or []
    print(f"  {data.get('count', len(items))} item(s) from {data.get('source')}")
    if data.get("attempts"):
        print(f"  containers tried: {data['attempts']}")

    for i, item in enumerate(items, 1):
        print(f"\n  {i}. {item.get('title') or '(untitled)'}")
        if item.get("date"):
            print(f"     date: {item['date']}")
        body = item.get("body") or ""
        if body:
            if not full and len(body) > 300:
                body = body[:300] + " ..."
            for line in textwrap.wrap(body, wrap):
                print(f"     {line}")
        for attachment in item.get("attachments") or []:
            print(f"     [attachment] {attachment['name']}")
            print(f"                  {attachment['href']}")
        for link in item.get("links") or []:
            print(f"     [link] {link['text']}  ->  {link['href']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--announcements", action="store_true")
    parser.add_argument("--messages", action="store_true")
    parser.add_argument("--timetable", action="store_true")
    parser.add_argument("--leave", action="store_true")
    parser.add_argument("--force", action="store_true", help="bypass the cache and re-read UMS")
    parser.add_argument("--full", action="store_true", help="print full body text")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    args = parser.parse_args()

    everything = not (args.announcements or args.messages or args.timetable or args.leave)
    query = "?force=true" if args.force else ""
    results: dict[str, dict] = {}
    if everything or args.announcements:
        results["announcements"] = get("/api/ums/announcements" + query)
    if everything or args.messages:
        results["messages"] = get("/api/ums/messages" + query)
    if everything or args.timetable:
        results["timetable"] = get("/api/ums/timetable" + query)
    if everything or args.leave:
        results["leave"] = get("/api/ums/leave" + query)

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    for kind, data in results.items():
        if kind == "timetable":
            show_timetable(data)
        elif kind == "leave":
            show_leave(data)
        else:
            show(kind, data, args.full)

    if any(d.get("error") for d in results.values()):
        print("\nIf UMS is connected and signed in but a panel is empty, the container "
              "selector is probably wrong. Run:\n    python scripts/ums_inspect.py --open")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
