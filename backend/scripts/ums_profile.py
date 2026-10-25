"""Show exactly what CampusAI can read about who you are.

    python scripts/ums_profile.py            # what /api/student returns
    python scripts/ums_profile.py --force    # ignore the cache and read UMS again
    python scripts/ums_profile.py --json     # raw JSON

Requires the backend running and UMS connected and signed in.

When the name cannot be read, this prints the labels that WERE on the dashboard
and the leave page. That list is the fix: whichever label actually holds the
name goes into NAME_LABELS in app/ums/profile.py, and the guessing stops.
"""
from __future__ import annotations

import argparse
import json
import sys
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
        if isinstance(detail, dict):
            return {"error": detail.get("message") or f"HTTP {exc.code}",
                    "status": exc.code, "diagnostics": detail.get("diagnostics") or {}}
        return {"error": detail or f"HTTP {exc.code}", "status": exc.code}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"backend unreachable at {BASE}: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-read UMS, ignoring the cache")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    args = parser.parse_args()

    raw = get(f"/api/ums/profile?force={'true' if args.force else 'false'}")
    student = get("/api/student")

    if args.json:
        print(json.dumps({"ums_profile": raw, "student": student}, indent=2))
        return 0 if not raw.get("error") else 1

    print("=" * 70)
    print("WHO UMS SAYS YOU ARE")
    print("=" * 70)

    if raw.get("error"):
        print(f"  Could not read it: {raw['error']}")
        diagnostics = raw.get("diagnostics") or {}
        attempts = diagnostics.get("profile_attempts") or []
        labels = diagnostics.get("profile_labels_seen") or []
        if attempts:
            print(f"\n  What it tried:  {' -> '.join(attempts)}")
        if labels:
            print("\n  Labels found on those pages (one of these should hold the name):")
            for label in labels:
                print(f"    - {label}")
        else:
            print("\n  No label/value pairs were found at all, which usually means the page "
                  "had not finished loading or UMS is not signed in.")
        print(f"\n  UMS state: {diagnostics.get('state')}")
        print(f"  Current page: {diagnostics.get('current_url')}")
    else:
        profile = raw.get("profile") or {}
        for key in ("name", "student_id", "program", "department", "section",
                    "term", "hostel", "room"):
            if profile.get(key):
                print(f"  {key:12} {profile[key]}")
        print(f"\n  Name came from: {profile.get('name_source') or 'unknown'}")
        print(f"  Read by:        {' -> '.join(raw.get('attempts') or [])}")
        labels = raw.get("labels_seen") or []
        if labels:
            print(f"  Labels seen:    {', '.join(labels[:15])}")

    print("\n" + "=" * 70)
    print("WHAT THE APP SHOWS (/api/student)")
    print("=" * 70)
    if student.get("error"):
        print(f"  {student['error']}")
    else:
        live = student.get("live")
        print(f"  {student.get('name') or '(no name)'} - "
              f"{'live from UMS' if live else 'DEMO DATA, UMS not connected'}")
        print(f"  source: {student.get('source')}")
    return 1 if raw.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
