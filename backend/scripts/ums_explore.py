"""Show every attendance-looking control CampusAI can see, and how it ranks them.

    python scripts/ums_explore.py

Read-only — it clicks nothing. Run it while the UMS dashboard is open in the
CampusAI browser. `would_click = True` marks the controls Playwright is willing
to try, in order.

If the right control is not in the list, or the wrong one is on top, paste this
output and the ranking can be corrected with UMS_ATTENDANCE_BLOCK_WORDS or by
pinning the selector.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def main() -> int:
    try:
        with urllib.request.urlopen(f"{BASE}/api/ums/explore", timeout=30) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        print(json.loads(exc.read() or b"{}"))
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Backend unreachable at {BASE}: {exc}")
        return 1

    if data.get("error"):
        print(data["error"])
        return 1

    print(f"page   : {data['page_url']}")
    print(f"title  : {data['title']}")
    print(f"frames : {len(data['frame_urls'])}")
    for url in data["frame_urls"]:
        print(f"         {url}")
    remembered = data.get("remembered_target")
    print(f"learned: {remembered.get('selector') if remembered else None}")

    candidates = data.get("candidates") or []
    if not candidates:
        print("\nNo control mentioning 'attend' was found in any frame.")
        print("The attendance link may be behind a menu — open it once by hand and re-run.")
        return 0

    print(f"\n{len(candidates)} candidate(s), best first:\n")
    for i, c in enumerate(candidates, 1):
        mark = "CLICK" if c["would_click"] else "skip "
        print(f"{i:>2}. [{mark}] score={c['score']:>3}  <{c['tag']}> {c['text']!r}")
        if c["href"]:
            print(f"        href     {c['href']}")
        if c["onclick"]:
            print(f"        onclick  {c['onclick']}")
        print(f"        selector {c['selector']}")
        if not c["visible"]:
            print("        (not visible)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
