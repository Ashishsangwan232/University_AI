"""Print the UMS pipeline state without opening the frontend.

    python scripts/ums_diagnose.py            # one snapshot
    python scripts/ums_diagnose.py --watch    # poll every 2s

Requires the backend to be running (uvicorn app.main:app --reload).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"

ORDER = [
    ("browser_started", "1. Browser started"),
    ("ums_page_found", "2. UMS tab found"),
    ("authenticated", "3. Authenticated"),
    ("attendance_page_found", "4. Attendance page reached"),
    ("attendance_table_found", "5. Attendance table found"),
    ("validated", "6. Parsed and validated"),
]


def get(path: str) -> dict:
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read() or b"{}")
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def snapshot() -> None:
    diag = get("/api/ums/diagnostics")
    if "error" in diag:
        print(f"Backend unreachable at {BASE}: {diag['error']}")
        return

    print(f"\nState: {diag.get('state')}")
    for key, label in ORDER:
        print(f"  {'OK  ' if diag.get(key) else 'no  '}{label}")
    print(f"  tabs open: {diag.get('page_count')} (UMS: {diag.get('ums_page_count')})")
    print(f"  current url: {diag.get('current_url')}")
    print(f"  verification showing: {diag.get('verification_required')}")
    print(f"  navigation attempts: {diag.get('navigation_attempts')}")
    print(f"  attendance url: {diag.get('attendance_url')}")
    print(f"  frames: {diag.get('frame_count')}  tables scanned: {diag.get('tables_scanned')}")
    print(f"  headers: {diag.get('table_headers')}")
    print(f"  courses parsed: {diag.get('courses_parsed')}  sample: {diag.get('table_sample_rows')}")
    print(f"  raw rows: {diag.get('table_raw_rows')}")
    print(f"  validation error: {diag.get('validation_error')}")
    print(f"  last error: {diag.get('last_error')}")
    candidates = diag.get("attendance_candidates") or []
    if candidates:
        print("  controls considered:")
        for c in candidates[:6]:
            print(f"    score={c.get('score'):>3}  {str(c.get('text'))[:44]!r:<48} {str(c.get('href'))[:50]}")

    att = get("/api/attendance")
    if "detail" in att:
        detail = att["detail"]
        message = detail.get("message") if isinstance(detail, dict) else detail
        print(f"\n/api/attendance -> BLOCKED: {message}")
    else:
        print(
            f"\n/api/attendance -> {att.get('overall_percentage')}% "
            f"live={att.get('live')} source={att.get('source')!r}"
        )
        for subject in att.get("subjects", []):
            print(f"    {subject['short']:<8} {subject['attended']}/{subject['total']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    if not args.watch:
        snapshot()
        return 0
    try:
        while True:
            snapshot()
            time.sleep(2)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
