# CampusAI — UMS Playwright integration

Playwright-only. There is no browser extension, no `content.js`, no bridge, no
heartbeat, no snapshot endpoint, and no bridge token anywhere in this codebase.

```
CampusAI frontend
   -> FastAPI
      -> UMSPlaywrightService (app/ums/playwright_service.py)
         -> real installed Chrome/Edge, dedicated user-data-dir, CDP port 9222
            -> student types username + password  (by hand)
            -> student completes human verification (by hand)
            -> Playwright detects authentication, navigates, extracts
               -> backend validates and stores
                  -> /api/attendance -> frontend / Gemini
```

## The bug this release fixes

`/api/attendance`, `app/tools/attendance.py`, and `GeminiAgent._source_from_tools`
all decided live-vs-demo with:

```python
if status.get("bridge_connected") and status.get("authenticated"):
```

`bridge_connected` was a key from the **deleted extension bridge**. The Playwright
status dictionary publishes `browser_connected`. `dict.get` on a missing key
returns `None`, so the condition was **always false** — the live branch was dead
code and every request fell through to the PostgreSQL demo rows (79.6%). The UMS
session itself was working; nothing ever asked it for data.

Fixed by moving the decision into one place (`app.ums.service.ums_is_live`), and
by publishing `bridge_connected` as an alias of `browser_connected` so a stale
reader can never silently evaluate to `False` again.

## State machine

`app/ums/state.py`. "Started", "authenticated" and "attendance extracted" are
three separate facts and none is inferred from another.

```
IDLE
BROWSER_STARTED
AUTHENTICATION_PENDING
AUTHENTICATED
ATTENDANCE_NAVIGATION_STARTED
ATTENDANCE_PAGE_FOUND
ATTENDANCE_TABLE_FOUND
ATTENDANCE_PARSED
ATTENDANCE_VALIDATED
ATTENDANCE_STORED
READY
```

`GET /api/ums/diagnostics` returns exactly how far the pipeline got:

```json
{
  "state": "ATTENDANCE_NAVIGATION_STARTED",
  "browser_started": true,
  "ums_page_found": true,
  "authenticated": true,
  "current_url": "https://ums.lpu.in/lpuums/...",
  "navigation_attempts": ["click:Attendance", "goto:https://..."],
  "attendance_page_found": false,
  "attendance_table_found": false,
  "frame_count": 3,
  "tables_scanned": 11,
  "table_headers": [],
  "courses_parsed": 0,
  "validated": false,
  "validation_error": null,
  "last_error": "..."
}
```

`python scripts/ums_diagnose.py --watch` prints the same thing as a checklist.

## How each step works

**Authentication detection.** Being on a `ums.lpu.in` URL is not evidence of a
login. A session is authenticated only when: the hostname is UMS, no
verification challenge text is on screen, and either an explicit logout control
exists or at least two `UMS_DASHBOARD_MARKERS` appear. A visible
`input[type=password]` with no logout control marks the page as a login page.

**Page selection.** Never `pages[0]` or `pages[-1]` blindly. Every context and
every tab is enumerated and filtered by hostname; a tab whose URL mentions
attendance wins. Only UMS hostnames are recorded — other tabs are counted, never
captured.

**Navigation.** In order: (1) is an attendance table already on this page;
(2) click an `Attendance` link found in any frame, following a popup tab if one
opens; (3) try `UMS_ATTENDANCE_PATHS` directly. Every attempt is recorded in
`navigation_attempts`, with the URL and title logged before and after.

**Frames.** `page.frames` is enumerated and every frame is searched, `<table>`
first and then `[role=grid]`. Frame URLs go into diagnostics.

**Waiting.** Polling on an explicit DOM condition (a table that parses as
attendance), never on `networkidle` — an ASP.NET portal keeps making background
requests.

**Parsing.** `app/ums/attendance_parser.py`, pure Python and unit tested by
`scripts/test_attendance_parser.py`. It scores header rows, maps columns
(`Course Code` / `Course Description` split, or a combined `CODE:NAME` cell),
reads `100 %` and bare `100.00`, separates the aggregate row, and computes the
aggregate when the table has none. Raw headers and the first rows are logged.

**Validation.** `attended <= delivered`, `delivered > 0`, and the aggregate must
agree with the sum of the course rows and with its own percentage. A table that
parses but fails validation is **not discarded silently** — the reason is stored
in `validation_error` and returned to the UI.

**No silent fallback.** When UMS is authenticated, `/api/attendance` returns
either live data or HTTP 409 with the state and diagnostics. Demo rows are used
only when no UMS session is connected *and* `UMS_DEMO_MODE=true`, and they are
labelled `"PostgreSQL demo data (UMS not connected)"` with `live: false`.

## Security

* CampusAI never reads, stores, types, or logs a username, password, or OTP.
* Credentials are never sent to Gemini; Gemini has no UMS tool that accepts them.
* Human verification is never bypassed, solved, or automated — the service waits
  and reports `verification_required`.
* Playwright only acts once authentication is positively detected.
* A dedicated profile (`data/ums/playwright-chrome-profile`) is used, never the
  student's normal Chrome profile.
* No cookie, session token, or authorization header is read or logged.
* UMS is never crawled into the public RAG index.
