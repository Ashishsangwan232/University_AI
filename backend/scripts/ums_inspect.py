"""Probe specific UMS containers to see how a panel is actually built.

    python scripts/ums_inspect.py                       # #tAC and #MyMessage
    python scripts/ums_inspect.py --open                # click the panel openers first
    python scripts/ums_inspect.py --html                # include sample markup
    python scripts/ums_inspect.py --selectors "#tAC,#tAM,#MyMessage,#divMessage"
    python scripts/ums_inspect.py --url frmMyCurrentTimeTable.aspx \
        --openers "[onclick*='GetTimeTableData1']" --selectors body --depth 4

Reads the DOM and, with --open or --openers, clicks the named controls to render
a panel. With --url it also opens one UMS page first, by direct GET, and returns
the browser to where it started; anything that looks like an action, or is off
the UMS host, is refused. Nothing is ever submitted.

Use this when announcements or messages come back empty or wrong: it shows the
child structure the extractor is walking, so the container can be corrected in
.env instead of guessed at.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
DEFAULT_SELECTORS = "#tAC,#tAM,#MyMessage,#divMessage,#exampleModalRight"
DEFAULT_OPENERS = "#AnnouncementLink,#MyMessageLink,[onclick*='getMyAllMessages']"


def post(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read() or b"{}")
        detail = body.get("detail")
        return {"error": (detail.get("message") if isinstance(detail, dict) else detail) or f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"backend unreachable at {BASE}: {exc}"}


def draw(node: dict, indent: int = 0) -> None:
    pad = "  " * indent
    label = node["tag"]
    if node["id"]:
        label += f"#{node['id']}"
    if node["cls"]:
        label += f".{node['cls'].split()[0]}" if node["cls"].split() else ""
    sample = f"  {node['sample']!r}" if node["sample"] else ""
    print(f"{pad}{label}  ({node['textLength']} chars){sample}")
    for child in node.get("children") or []:
        draw(child, indent + 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selectors", default=DEFAULT_SELECTORS)
    parser.add_argument("--openers", default="")
    parser.add_argument("--open", action="store_true", help="click the default panel openers first")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--html", action="store_true", help="include sample markup")
    parser.add_argument("--url", default="",
                        help="open this UMS page first (a plain GET; actions are refused)")
    parser.add_argument("--wait", type=float, default=2.0,
                        help="seconds to wait after navigating / clicking, for AJAX content")
    args = parser.parse_args()

    openers = args.openers or (DEFAULT_OPENERS if args.open else "")
    data = post("/api/ums/inspect", {
        "selectors": [s.strip() for s in args.selectors.split(",") if s.strip()],
        "openers": [o.strip() for o in openers.split(",") if o.strip()],
        "depth": args.depth,
        "html": args.html,
        "url": args.url,
        "wait": args.wait,
    })

    if data.get("error"):
        print(data["error"])
        return 1

    print(f"page    : {data['page_url']}")
    print(f"title   : {data.get('title')!r}")
    print(f"openers : {data['openers'] or '(none clicked)'}")
    for result in data["results"]:
        print(f"\n=== {result['selector']}")
        if not result.get("exists"):
            print("    not present on this page")
            continue
        print(f"    visible={result['visible']}  direct children={result['childCount']}"
              f"  frame={result.get('frame_url', '')}")
        if result.get("tree"):
            draw(result["tree"])
        for i, html in enumerate(result.get("samples") or [], 1):
            print(f"\n    --- sample child {i} markup ---")
            print("    " + html.replace("\n", "\n    ")[:3000])
    print("\nEach direct child of a container is treated as one card. If the cards are "
          "nested one level deeper, point the container at that inner element in .env "
          "(UMS_ANNOUNCEMENT_CONTAINERS / UMS_MESSAGE_CONTAINERS).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
