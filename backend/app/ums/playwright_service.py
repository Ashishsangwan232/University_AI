"""Playwright-only UMS session.

Architecture (no browser extension, no bridge, no content script, no token):

    FastAPI -> UMSPlaywrightService -> real installed Chrome/Edge
    -> dedicated user-data-dir -> student logs in and clears Cloudflare BY HAND
    -> Playwright attaches over CDP -> navigates -> extracts attendance.

Security rules enforced here:
  * credentials are never read, stored, typed, or logged by this process;
  * Cloudflare is never bypassed, solved, or automated - the service simply
    waits and reports ``verification_required``;
  * Playwright only acts after authentication has been positively detected;
  * a dedicated profile directory is used, never the student's normal profile;
  * no cookie, header, token, or storage value is ever logged.

The service models BROWSER_STARTED / AUTHENTICATION_PENDING / AUTHENTICATED /
ATTENDANCE_* / READY as separate states and never infers one from another.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from playwright.sync_api import Browser, Frame, Page, sync_playwright

from app.core.config import settings
from app.ums.attendance_parser import (
    DETAIL_JS,
    parse_attendance_rows,
    parse_detail_tables,
    validate_attendance,
    validate_detail,
)
from app.ums.navigation import host_of, rank_candidates
from app.ums.panels import (
    CARDS_JS,
    INSPECT_JS,
    dedupe,
    parse_cards,
    validate_cards,
)
from app.ums.site_map import MAP_JS, build as build_site_map, is_action
from app.ums.messages import STORE_JS as MESSAGE_STORE_JS, dedupe_messages, parse_rows as parse_message_rows, row_totals as message_totals
from app.ums.leave import LEAVE_JS, LOCATE_JS, parse_leave, validate_leave
from app.ums.leave_draft import format_for_ums
from app.ums.profile import (
    PROFILE_JS,
    is_strong,
    merge_profile,
    parse_profile,
    validate_profile,
)
from app.ums.timetable import TIMETABLE_JS, parse_timetable, validate_timetable
from app.ums.state import UMSLiveAttendanceUnavailable, UMSState

log = logging.getLogger("campusai.ums")

ATTENDANCE_WORD = re.compile(r"attendance", re.I)

# One round trip per frame: returns every table as a matrix of cell strings.
TABLES_JS = r"""
() => {
  const out = [];
  // Skip the per-course class logs (109 tables in LPU's attendance modal);
  // they are read separately and would push the summary past the limit.
  const tables = Array.from(document.querySelectorAll('table'))
    .filter(t => !t.closest('[id^=collapse]')).slice(0, 60);
  for (const t of tables) {
    const rows = Array.from(t.querySelectorAll('tr')).slice(0, 400).map(r =>
      Array.from(r.querySelectorAll('th,td')).map(c =>
        (c.innerText || c.textContent || '').replace(/\s+/g, ' ').trim()
      )
    );
    out.push(rows);
  }
  return out;
}
"""

# ARIA-grid fallback for portals that render rows with divs instead of tables.
GRID_JS = r"""
() => {
  const grids = Array.from(document.querySelectorAll('[role=grid],[role=table]')).slice(0, 10);
  return grids.map(g => Array.from(g.querySelectorAll('[role=row]')).slice(0, 400).map(r =>
    Array.from(r.querySelectorAll('[role=cell],[role=columnheader],[role=gridcell]')).map(c =>
      (c.innerText || c.textContent || '').replace(/\s+/g, ' ').trim()
    )
  ));
}
"""

# Every clickable thing whose text/href/onclick/id mentions attendance, with a
# CSS path so the winning control can be clicked again directly next time.
EXPLORE_JS = r"""
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
  const SEL = 'a,button,input[type=button],input[type=submit],[role=menuitem],[role=link],'
    + '[role=tab],[onclick],li,td,h3,h4,.card,.tile,.panel,.nav-link,.menu-item,.dropdown-item';
  const out = [];
  const seen = new Set();
  for (const el of Array.from(document.querySelectorAll(SEL)).slice(0, 5000)) {
    const text = (el.innerText || el.value || el.getAttribute('title')
      || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
    const href = el.getAttribute('href') || '';
    const onclick = String(el.getAttribute('onclick') || '');
    const id = el.id || '';
    const hay = (text + ' ' + href + ' ' + onclick + ' ' + id).toLowerCase();
    if (!hay.includes('attend')) continue;
    // A long innerText means this is a container, not the control itself.
    if (text.length > 120) continue;
    const path = cssPath(el);
    if (seen.has(path)) continue;
    seen.add(path);
    const rect = el.getBoundingClientRect();
    out.push({
      tag: el.tagName.toLowerCase(), id, text: text.slice(0, 120),
      href: href.slice(0, 300), onclick: onclick.slice(0, 200), selector: path,
      visible: rect.width > 0 && rect.height > 0
    });
    if (out.length >= 60) break;
  }
  return out;
}
"""

# Menu openers that may need one click before the attendance control exists.
MENU_JS = r"""
(keywords) => {
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
  const SEL = 'a,button,[role=menuitem],[role=tab],[onclick],.nav-link,.menu-item,.dropdown-toggle,li';
  const out = [];
  const seen = new Set();
  for (const el of Array.from(document.querySelectorAll(SEL)).slice(0, 3000)) {
    const text = (el.innerText || el.value || '').replace(/\s+/g, ' ').trim();
    if (!text || text.length > 40) continue;
    const lowered = text.toLowerCase();
    if (!keywords.some(k => lowered.includes(k))) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    const path = cssPath(el);
    if (seen.has(path)) continue;
    seen.add(path);
    out.push({ text, selector: path });
    if (out.length >= 8) break;
  }
  return out;
}
"""


#: Alias so this module keeps its short internal name.
_host = host_of


class UMSPlaywrightService:
    """Owns the UMS browser lifecycle on a dedicated Playwright worker thread."""

    _pw: Any = None
    _browser: Browser | None = None
    _chrome_process: subprocess.Popen | None = None
    _profile: Path = Path("data/ums/playwright-chrome-profile")

    def __init__(self) -> None:
        self._status_lock = threading.RLock()
        self._commands: queue.Queue[tuple[Callable[[], Any], queue.Queue[Any]]] = queue.Queue()
        self._state: UMSState = UMSState.IDLE
        self._diagnostics: dict[str, Any] = self._blank_diagnostics()
        self._attendance: dict[str, Any] | None = None
        self._attendance_updated_at: float | None = None
        self._message = "UMS Playwright session is not started."
        self._last_error: str | None = None
        self._auth_flags = {"authenticated": False, "verification_required": False, "login_page": False}
        self._page_info = {"url": None, "title": None}
        self._browser_connected = False
        self._running = False
        self._auto_capture_done = False
        self._auto_capture_attempts = 0
        self._panels: dict[str, dict[str, Any]] = {}
        self._last_seen_at: float | None = None
        #: Background prefetch: which item is being read right now, and the
        #: last failure per item (time, message) so a failing page is retried
        #: later instead of on every idle tick. Memory only.
        self._prefetch_current: str | None = None
        #: kind -> (failed at, message, consecutive failures)
        self._prefetch_errors: dict[str, tuple[float, str, int]] = {}
        #: Recent searches of the message store, by query/days/size.
        self._message_searches: dict[str, dict[str, Any]] = {}
        #: Refresh bumps the generation; an item read in an older generation is
        #: re-read in the background. A counter, not a clock, so it is exact.
        self._generation = 0
        self._item_generation: dict[str, int] = {}
        self._was_authenticated = False
        self._unauth_streak = 0
        self._last_heal_at = 0.0
        self._thread = threading.Thread(target=self._worker, name="campusai-ums-playwright", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ state

    @staticmethod
    def _blank_diagnostics() -> dict[str, Any]:
        return {
            "state": UMSState.IDLE.value,
            "browser_started": False,
            "cdp_endpoint": None,
            "context_count": 0,
            "page_count": 0,
            "ums_page_count": 0,
            "ums_page_urls": [],
            "ums_page_found": False,
            "authenticated": False,
            "verification_required": False,
            "login_page": False,
            "current_url": None,
            "current_title": None,
            "navigation_attempts": [],
            "attendance_page_found": False,
            "attendance_url": None,
            "frame_count": 0,
            "frame_urls": [],
            "tables_scanned": 0,
            "attendance_table_found": False,
            "table_headers": [],
            "table_sample_rows": [],
            "table_raw_rows": [],
            "attendance_candidates": [],
            "courses_parsed": 0,
            "validated": False,
            "validation_error": None,
            "attendance_updated_at": None,
            "last_error": None,
        }

    def _set_state(self, state: UMSState, message: str | None = None) -> None:
        with self._status_lock:
            if self._state is not state:
                log.info("[UMS] state %s -> %s", self._state.value, state.value)
            self._state = state
            self._diagnostics["state"] = state.value
            if message:
                self._message = message

    def _diag(self, **values: Any) -> None:
        with self._status_lock:
            self._diagnostics.update(values)

    def status(self) -> dict[str, Any]:
        with self._status_lock:
            diagnostics = json.loads(json.dumps(self._diagnostics))
            attendance = json.loads(json.dumps(self._attendance)) if self._attendance else None
            return {
                "state": self._state.value,
                "running": self._running,
                "browser_connected": self._browser_connected,
                # Legacy alias kept so nothing that still reads the old bridge
                # key silently evaluates to False.
                "bridge_connected": self._browser_connected,
                "authenticated": self._auth_flags["authenticated"],
                "verification_required": self._auth_flags["verification_required"],
                "login_page": self._auth_flags["login_page"],
                "url": self._page_info["url"],
                "title": self._page_info["title"],
                "message": self._message,
                "attendance_captured": attendance is not None,
                "attendance_course_count": len(attendance["courses"]) if attendance else 0,
                "attendance": attendance,
                "attendance_source_url": diagnostics.get("attendance_url"),
                "attendance_updated_at": self._attendance_updated_at,
                "last_error": self._last_error,
                "last_seen_at": self._last_seen_at,
                "prefetch": self._prefetch_status(),
                "diagnostics": diagnostics,
            }

    def diagnostics(self) -> dict[str, Any]:
        with self._status_lock:
            return json.loads(json.dumps(self._diagnostics))

    # ------------------------------------------------------------- public API

    def start(self) -> dict[str, Any]:
        return self._call(self._start, timeout=60)

    def stop(self) -> dict[str, Any]:
        return self._call(self._stop, timeout=30)

    def refresh(self) -> dict[str, Any]:
        return self._call(self._refresh, timeout=settings.ums_capture_timeout_seconds + 30)

    def navigate(self, target: str) -> dict[str, Any]:
        return self._call(lambda: self._navigate(target), timeout=60)

    def attendance(self, *, max_age_seconds: float | None = None) -> dict[str, Any]:
        """Return live attendance, refreshing it when authenticated and stale.

        Raises :class:`UMSLiveAttendanceUnavailable` instead of ever returning
        demo data.
        """
        snapshot = self.status()
        ttl = settings.ums_cache_max_age_seconds if max_age_seconds is None else max_age_seconds
        stale = (
            snapshot["attendance"] is None
            or snapshot["attendance_updated_at"] is None
            or (time.time() - snapshot["attendance_updated_at"]) > ttl
        )
        if stale and snapshot["browser_connected"] and snapshot["authenticated"]:
            # Read attendance only - not a full Refresh, which would also mark
            # every other item for re-reading and keep UMS busy for a minute.
            def run() -> None:
                # The background prefetch may have read it while this waited.
                age = self._age("attendance")
                if age is None or age > ttl:
                    self._fetch_now("attendance")

            try:
                self._call(run, timeout=settings.ums_capture_timeout_seconds + 30)
            except Exception as exc:  # noqa: BLE001 - reported through diagnostics
                log.info("[UMS] reading attendance for a question failed: %s", exc)
            snapshot = self.status()

        if snapshot["attendance"] is None:
            raise UMSLiveAttendanceUnavailable(
                self._unavailable_reason(snapshot), snapshot["diagnostics"]
            )
        return {
            "available": True,
            "source": "UMS Playwright session",
            "state": snapshot["state"],
            "updated_at": snapshot["attendance_updated_at"],
            "source_url": snapshot["attendance_source_url"],
            **snapshot["attendance"],
        }

    @staticmethod
    def _unavailable_reason(snapshot: dict[str, Any]) -> str:
        diag = snapshot["diagnostics"]
        state = snapshot["state"]
        if not snapshot["running"]:
            return "The UMS browser has not been started. Click Connect UMS first."
        if not snapshot["browser_connected"]:
            return "The UMS browser is open but Playwright is not attached to it yet."
        if not diag.get("ums_page_found"):
            return (
                f"Playwright is attached but no tab on {settings.ums_host} is open. "
                "Open UMS in the CampusAI browser window."
            )
        if snapshot["verification_required"]:
            return "UMS is showing a human-verification page. Complete it yourself in the CampusAI browser window."
        if snapshot["login_page"] or not snapshot["authenticated"]:
            return "UMS is open but not logged in yet. Sign in manually in the CampusAI browser window."
        if not diag.get("attendance_page_found"):
            return (
                "UMS is connected and authenticated, but the Attendance Summary page could not be "
                f"reached. Attendance page: {state}. Tried: {diag.get('navigation_attempts')}."
            )
        if not diag.get("attendance_table_found"):
            return (
                "UMS is connected and authenticated, but no attendance table was found on "
                f"{diag.get('attendance_url')}. Attendance page: {state}. "
                f"Frames searched: {diag.get('frame_count')}, tables scanned: {diag.get('tables_scanned')}."
            )
        if diag.get("validation_error"):
            return (
                "UMS is connected and authenticated, and an attendance table was parsed, but it "
                f"failed validation: {diag['validation_error']}. Attendance page: {state}."
            )
        return (
            "UMS is connected and authenticated, but live attendance could not be extracted. "
            f"Attendance page: {state}. Last error: {snapshot['last_error']}."
        )

    # ---------------------------------------------------------- worker thread

    def _worker(self) -> None:
        with sync_playwright() as pw:
            self._pw = pw
            self._browser: Browser | None = None
            self._chrome_process: subprocess.Popen | None = None
            self._profile = Path(settings.ums_browser_profile).resolve()
            while True:
                try:
                    fn, result_q = self._commands.get(timeout=settings.ums_monitor_interval_seconds)
                except queue.Empty:
                    try:
                        self._monitor()
                    except Exception as exc:  # noqa: BLE001 - monitor must not die
                        log.debug("[UMS] monitor tick failed: %s", exc)
                    continue
                try:
                    result_q.put((True, fn()))
                except Exception as exc:  # noqa: BLE001 - forwarded to caller
                    with self._status_lock:
                        self._last_error = str(exc)
                        self._diagnostics["last_error"] = str(exc)
                    result_q.put((False, exc))

    def _call(self, fn: Callable[[], Any], timeout: float) -> Any:
        result_q: queue.Queue[Any] = queue.Queue(maxsize=1)
        self._commands.put((fn, result_q))
        try:
            ok, result = result_q.get(timeout=timeout)
        except queue.Empty as exc:
            raise UMSLiveAttendanceUnavailable(
                "The UMS browser worker did not respond in time.", self.diagnostics()
            ) from exc
        if ok:
            return result
        raise result

    # -------------------------------------------------------- browser startup

    def _start(self) -> dict[str, Any]:
        with self._status_lock:
            self._running = True
            self._last_error = None
        self._set_state(
            UMSState.BROWSER_STARTED,
            "Starting the dedicated CampusAI browser. Sign in to UMS manually in that window.",
        )
        self._profile.mkdir(parents=True, exist_ok=True)
        port = settings.ums_cdp_port
        endpoint = f"http://127.0.0.1:{port}"

        if not self._cdp_alive(endpoint):
            browser_path = self._find_browser()
            args = [
                browser_path,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={self._profile}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-sync",
                "--new-window",
                settings.ums_url,
            ]
            log.info("[UMS] Browser starting: %s (profile=%s, cdp=%s)", Path(browser_path).name, self._profile, port)
            self._chrome_process = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            log.info("[UMS] Browser already listening on %s; attaching", endpoint)

        self._connect_cdp(endpoint)
        log.info("[UMS] Browser started")
        self._monitor()
        return self.status()

    @staticmethod
    def _cdp_alive(endpoint: str) -> bool:
        try:
            urllib.request.urlopen(f"{endpoint}/json/version", timeout=1).read()
            return True
        except Exception:  # noqa: BLE001
            return False

    def _find_browser(self) -> str:
        candidates = [
            os.environ.get("CAMPUSAI_CHROME_PATH"),
            os.environ.get("CAMPUSAI_EDGE_PATH"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        for name in ("chrome.exe", "msedge.exe", "google-chrome", "chromium"):
            found = shutil.which(name)
            if found:
                return found
        raise RuntimeError(
            "Google Chrome or Microsoft Edge was not found. Install one, or set "
            "CAMPUSAI_CHROME_PATH / CAMPUSAI_EDGE_PATH."
        )

    def _connect_cdp(self, endpoint: str) -> None:
        deadline = time.time() + 25
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{endpoint}/json/version", timeout=1).read()
                self._browser = self._pw.chromium.connect_over_cdp(endpoint)
                contexts = self._browser.contexts
                if not contexts:
                    raise RuntimeError("The browser is open but exposes no context yet.")
                log.info("[UMS] CDP endpoint %s attached (%d context(s))", endpoint, len(contexts))
                with self._status_lock:
                    self._browser_connected = True
                self._diag(browser_started=True, cdp_endpoint=endpoint, context_count=len(contexts))
                self._set_state(
                    UMSState.AUTHENTICATION_PENDING,
                    "CampusAI browser is open. Sign in to UMS and complete verification yourself.",
                )
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(0.4)
        raise RuntimeError(
            f"Playwright could not attach to the CampusAI browser on {endpoint}: {last_error}"
        )

    # --------------------------------------------------------- page discovery

    def _all_pages(self) -> list[Page]:
        if not self._browser:
            return []
        pages: list[Page] = []
        try:
            contexts = self._browser.contexts
        except Exception:  # noqa: BLE001 - browser went away
            with self._status_lock:
                self._browser_connected = False
            return []
        self._diag(context_count=len(contexts))
        for context in contexts:
            for page in context.pages:
                if not page.is_closed():
                    pages.append(page)
        return pages

    def _ums_pages(self) -> list[Page]:
        """Every open tab whose hostname belongs to UMS - never ``pages[0]``.

        Only UMS hostnames are recorded in diagnostics; the student's other tabs
        are counted but their URLs are never captured or logged.
        """
        pages = self._all_pages()
        ums = [p for p in pages if settings.ums_host in _host(p.url)]
        self._diag(
            page_count=len(pages),
            ums_page_count=len(ums),
            ums_page_urls=[p.url for p in ums][:10],
            ums_page_found=bool(ums),
        )
        return ums

    def _pick_ums_page(self) -> Page | None:
        ums = self._ums_pages()
        if not ums:
            return None
        for page in reversed(ums):
            if ATTENDANCE_WORD.search(page.url):
                return page
        return ums[-1]

    # -------------------------------------------------- authentication checks

    def _classify(self, page: Page) -> dict[str, Any]:
        """Positive authentication detection.

        Being on a UMS URL is not evidence of a login. A session counts as
        authenticated only when a post-login marker is present *and* no password
        field / verification challenge is on screen.
        """
        info = {"authenticated": False, "verification_required": False, "login_page": False,
                "url": page.url, "title": None}
        try:
            info["title"] = page.title()
        except Exception:  # noqa: BLE001
            return info

        try:
            text = page.locator("body").inner_text(timeout=2500)[: settings.ums_max_page_text]
        except Exception:  # noqa: BLE001
            text = ""
        lowered = f"{info['url']} {info['title']} {text}".lower()

        verification = any(
            marker in lowered
            for marker in (
                "verify you are human",
                "checking your browser",
                "complete the verification",
                "please complete the verification",
                "just a moment",
                "cf-challenge",
            )
        )

        def count(selector: str) -> int:
            try:
                return page.locator(selector).count()
            except Exception:  # noqa: BLE001
                return 0

        password_fields = count("input[type=password]")
        logout_markers = count(
            "a[href*='ogout'], a[href*='ignout'], "
            "a:has-text('Logout'), a:has-text('Log Out'), a:has-text('Sign Out')"
        )
        menu_markers = 0
        for marker in settings.ums_dashboard_markers_list:
            if marker.lower() in lowered:
                menu_markers += 1

        info["verification_required"] = verification
        info["login_page"] = bool(password_fields) and not logout_markers
        info["authenticated"] = bool(
            not verification
            and not info["login_page"]
            and settings.ums_host in _host(info["url"])
            and (logout_markers > 0 or menu_markers >= 2)
        )
        return info

    def _monitor(self) -> None:
        """Cheap periodic poll. Never types, never clicks on a login page."""
        if not self._browser_connected:
            return
        page = self._pick_ums_page()
        now = time.time()
        if page is None:
            with self._status_lock:
                self._last_seen_at = now
                self._auth_flags = {"authenticated": False, "verification_required": False, "login_page": False}
                self._page_info = {"url": None, "title": None}
            self._diag(authenticated=False, verification_required=False, login_page=False,
                       current_url=None, current_title=None)
            self._set_state(
                UMSState.AUTHENTICATION_PENDING,
                f"No {settings.ums_host} tab is open in the CampusAI browser.",
            )
            return

        info = self._classify(page)
        if (
            not info["authenticated"]
            and not info["login_page"]
            and not info["verification_required"]
            and self._is_error_page(info)
            and time.time() - self._last_heal_at > 30
        ):
            # Stranded on a UMS error page (e.g. a 404 an old fallback URL led
            # to, or a capture cut off by a backend reload). Go back to the
            # dashboard; if the session really ended, that shows the login page.
            self._last_heal_at = time.time()
            log.info("[UMS] On an error page (%r); returning to %s", info.get("title"), settings.ums_url)
            try:
                page.goto(settings.ums_url, wait_until="domcontentloaded", timeout=20000)
            except Exception as exc:  # noqa: BLE001
                log.info("[UMS] could not leave the error page: %s", type(exc).__name__)
            return
        if (
            not info["authenticated"]
            and self._was_authenticated
            and not info["login_page"]
            and not info["verification_required"]
            and self._unauth_streak < 15
        ):
            # Probably caught a page mid-load. Only believe "signed out" after
            # a few readings in a row, unless the login page is actually showing.
            self._unauth_streak += 1
            return
        self._unauth_streak = 0
        with self._status_lock:
            self._last_seen_at = now
            self._auth_flags = {
                "authenticated": info["authenticated"],
                "verification_required": info["verification_required"],
                "login_page": info["login_page"],
            }
            self._page_info = {"url": info["url"], "title": info["title"]}
        self._diag(
            authenticated=info["authenticated"],
            verification_required=info["verification_required"],
            login_page=info["login_page"],
            current_url=info["url"],
            current_title=info["title"],
        )

        if info["verification_required"]:
            self._auto_capture_done = False
            self._auto_capture_attempts = 0
            self._set_state(
                UMSState.AUTHENTICATION_PENDING,
                "UMS is showing a human-verification page. Complete it yourself; CampusAI will wait.",
            )
            return
        if not info["authenticated"]:
            self._auto_capture_done = False
            self._auto_capture_attempts = 0
            if info["login_page"] and (self._panels or self._attendance is not None):
                # Signed out: the cached data belongs to a session that has ended.
                self._clear_cache()
                log.info("[UMS] Login page detected; cached UMS data cleared")
            self._was_authenticated = False
            self._set_state(
                UMSState.AUTHENTICATION_PENDING,
                "Waiting for manual UMS login in the CampusAI browser window.",
            )
            return

        if not self._was_authenticated:
            log.info("[UMS] Authentication detected on %s", info["url"])
            self._was_authenticated = True
        if self._attendance is None:
            self._set_state(UMSState.AUTHENTICATED, "UMS is authenticated. Locating the Attendance Summary page.")
        elif self._state is UMSState.AUTHENTICATION_PENDING:
            self._set_state(UMSState.READY, "UMS is authenticated and live data is cached.")
        # With prefetch on, attendance is simply its first item - one attempt,
        # then the other items, then a retry later. The old loop below tried
        # attendance three times in a row first, which could take many minutes
        # and held everything else (chat questions included) up behind it.
        if settings.ums_auto_navigate and not self._auto_capture_done and not settings.ums_prefetch:
            self._auto_capture_attempts += 1
            if self._auto_capture_attempts >= settings.ums_auto_capture_attempts:
                # Stop retrying, but say so instead of looping on the student's browser.
                self._auto_capture_done = True
            try:
                self._capture(page)
                self._auto_capture_done = True
            except Exception as exc:  # noqa: BLE001 - surfaced in diagnostics
                with self._status_lock:
                    self._last_error = str(exc)
                self._diag(last_error=str(exc))
                log.info(
                    "[UMS] automatic capture attempt %d/%d failed: %s",
                    self._auto_capture_attempts, settings.ums_auto_capture_attempts, exc,
                )
            return
        # Idle and signed in: read the next item that is missing or due.
        self._prefetch_step()

    # ------------------------------------------------------------- navigation

    def _capture(self, page: Page) -> dict[str, Any]:
        """AUTHENTICATED -> ... -> ATTENDANCE_STORED. Raises on any failure."""
        self._set_state(UMSState.ATTENDANCE_NAVIGATION_STARTED, "Navigating to the UMS Attendance Summary page.")
        self._diag(navigation_attempts=[], attendance_page_found=False, attendance_table_found=False,
                   attendance_url=None, table_headers=[], table_sample_rows=[], courses_parsed=0,
                   validated=False, validation_error=None, tables_scanned=0)

        attempts: list[str] = []
        target, winner = self._navigate_to_attendance(page, attempts)
        self._diag(navigation_attempts=attempts)

        log.info("[UMS] Attendance URL %s (title=%r)", target.url, self._safe_title(target))
        found = self._wait_for_attendance_table(target)
        if found is None:
            self._set_state(
                UMSState.ATTENDANCE_NAVIGATION_STARTED,
                "Authenticated, but no attendance table was found. Open Attendance Summary in the browser and press Refresh.",
            )
            raise UMSLiveAttendanceUnavailable(
                "UMS is authenticated, but Playwright found no attendance table. Open the "
                "Attendance Summary page in the CampusAI browser and press Refresh.",
                self.diagnostics(),
            )

        frame, parsed = found
        self._diag(
            attendance_page_found=True,
            attendance_url=frame.url or target.url,
            attendance_table_found=True,
            table_headers=parsed.get("headers", []),
            table_sample_rows=[c["course"] for c in parsed["courses"][:3]],
            table_raw_rows=parsed.get("raw_rows", [])[:3],
            courses_parsed=len(parsed["courses"]),
        )
        self._set_state(UMSState.ATTENDANCE_TABLE_FOUND)
        log.info("[UMS] Parsed courses %d", len(parsed["courses"]))
        log.info("[UMS] Aggregate %s", parsed["aggregate"])
        self._set_state(UMSState.ATTENDANCE_PARSED)

        ok, reason = validate_attendance(parsed)
        self._diag(validated=ok, validation_error=None if ok else reason)
        log.info("[UMS] Validation result %s (%s)", ok, reason)
        if not ok:
            self._set_state(UMSState.ATTENDANCE_PARSED, f"Attendance table failed validation: {reason}")
            raise UMSLiveAttendanceUnavailable(
                f"An attendance table was parsed but failed validation: {reason}", self.diagnostics()
            )
        self._set_state(UMSState.ATTENDANCE_VALIDATED)

        record = {
            "courses": parsed["courses"],
            "aggregate": parsed["aggregate"],
            "headers": parsed.get("headers", []),
            "extraction": parsed.get("extraction", "dom-table"),
            "source_url": frame.url or target.url,
        }
        with self._status_lock:
            self._attendance = record
            self._attendance_updated_at = time.time()
            self._last_error = None
        self._diag(attendance_updated_at=self._attendance_updated_at, last_error=None)
        self._save_target(target.url, frame.url or target.url, winner)
        if settings.ums_close_after_capture and (winner or {}).get("opener"):
            # We opened a modal on the student's screen; put it back.
            try:
                target.keyboard.press("Escape")
                time.sleep(0.6)  # let the close animation finish
            except Exception:  # noqa: BLE001
                pass
            self._clear_stray_backdrop(target)
        self._set_state(UMSState.ATTENDANCE_STORED)
        log.info("[UMS] Attendance stored")
        self._set_state(UMSState.READY, "Live UMS attendance captured by Playwright.")
        return record

    @staticmethod
    def _safe_title(page: Page) -> str:
        try:
            return page.title()
        except Exception:  # noqa: BLE001
            return ""

    # ---------------------------------------------------- learned click target

    def _target_file(self) -> Path:
        return Path(settings.ums_browser_profile).resolve().parent / "attendance_target.json"

    def _load_target(self) -> dict[str, Any] | None:
        if not settings.ums_remember_target:
            return None
        try:
            return json.loads(self._target_file().read_text("utf-8"))
        except Exception:  # noqa: BLE001 - a missing/corrupt hint is not an error
            return None

    def _save_target(self, page_url: str, frame_url: str, candidate: dict[str, Any] | None) -> None:
        """Remember what worked so the next capture goes straight there.

        Only URLs and a CSS path are stored - never cookies, tokens, or any
        page content.
        """
        if not settings.ums_remember_target:
            return
        payload = {
            "page_url": page_url,
            "frame_url": frame_url,
            "selector": (candidate or {}).get("selector"),
            "text": (candidate or {}).get("text"),
            "opener": bool((candidate or {}).get("opener")),
            "saved_at": time.time(),
        }
        try:
            path = self._target_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2), "utf-8")
            log.info("[UMS] Remembered attendance target %s", payload["selector"] or payload["page_url"])
        except Exception as exc:  # noqa: BLE001
            log.debug("[UMS] could not save attendance target: %s", exc)

    # ------------------------------------------------------------- navigation

    def _navigate_to_attendance(self, page: Page, attempts: list[str]) -> tuple[Page, dict[str, Any] | None]:
        """Reach the attendance table without the student having to open it.

        Order: table already visible -> the control that worked last time ->
        ranked in-portal controls (with rollback when one goes somewhere wrong)
        -> menu openers, then ranked controls again -> configured direct URLs.
        """
        origin = page.url
        log.info("[UMS] Navigating to attendance from %s", origin)

        # Load the summary the way UMS's own tile does, without opening the
        # modal: works even when a UMS pop-up (e.g. the Campus Drive
        # notification shown after every reload) covers the tile, and nothing
        # moves on the student's screen. It empties the old table first, so
        # this always reads fresh numbers - unlike re-reading a table that is
        # still sitting in the hidden modal from an earlier load.
        if self._call_page_function(page, settings.ums_attendance_summary_loader, attempts):
            if self._wait_for_attendance_table(page) is not None:
                log.info("[UMS] Attendance summary loaded via %s()", settings.ums_attendance_summary_loader)
                return page, None

        if self._scan_frames(page) is not None:
            attempts.append("already-on-attendance-page")
            log.info("[UMS] Attendance table is already present")
            return page, None

        remembered = self._load_target()
        if remembered:
            result = self._try_remembered(page, remembered, attempts)
            if result is not None:
                return result

        opened = self._click_openers(page, attempts)
        if opened is not None:
            return opened

        candidates = self._explore(page)
        self._diag(attendance_candidates=[
            {k: c[1][k] for k in ("text", "href", "selector", "score", "visible")} for c in candidates[:10]
        ])
        log.info(
            "[UMS] Attendance control candidates: %s",
            [(c[1]["text"][:40] or c[1]["href"][:40], c[1]["score"]) for c in candidates[:8]],
        )

        result = self._try_candidates(page, candidates, attempts, origin)
        if result is not None:
            return result

        if settings.ums_expand_menus:
            for opener in self._menu_openers(page)[: settings.ums_max_menu_clicks]:
                attempts.append(f"menu:{opener[1]['text'][:40]}")
                log.info("[UMS] Opening menu %r to reveal attendance controls", opener[1]["text"][:40])
                try:
                    opener[0].locator(opener[1]["selector"]).first.click(timeout=5000)
                    time.sleep(1.2)
                except Exception as exc:  # noqa: BLE001
                    log.info("[UMS] menu click failed: %s", type(exc).__name__)
                    continue
                if self._scan_frames(page) is not None:
                    attempts.append("table-appeared-after-menu")
                    return page, None
                fresh = [c for c in self._explore(page) if c[1]["selector"] not in
                         {seen[1]["selector"] for seen in candidates}]
                if not fresh:
                    continue
                candidates.extend(fresh)
                result = self._try_candidates(page, fresh, attempts, origin)
                if result is not None:
                    return result

        for path in settings.ums_attendance_paths_list:
            url = path if path.startswith("http") else settings.ums_url.rstrip("/") + "/" + path.lstrip("/")
            if url.rstrip("/") == page.url.rstrip("/"):
                continue
            attempts.append(f"goto:{url}")
            try:
                log.info("[UMS] Trying direct attendance URL %s", url)
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except Exception as exc:  # noqa: BLE001
                log.info("[UMS] direct URL failed: %s", type(exc).__name__)
                continue
            if settings.ums_host not in _host(page.url):
                continue
            if self._wait_for_attendance_table(page, quick=True) is not None:
                return page, None

        # Nothing worked: leave the browser where the student left it.
        self._restore(page, origin, attempts)
        return page, None

    def _restore(self, page: Page, origin: str, attempts: list[str]) -> None:
        if page.is_closed() or page.url.rstrip("/") == origin.rstrip("/"):
            return
        attempts.append("restore-original-page")
        log.info("[UMS] Returning the browser to %s", origin)
        try:
            page.goto(origin, wait_until="domcontentloaded", timeout=20000)
        except Exception as exc:  # noqa: BLE001
            log.info("[UMS] could not restore original page: %s", type(exc).__name__)

    def _call_page_function(self, page: Page, name: str, attempts: list[str]) -> bool:
        """Call one of UMS's own (read-only) loader functions if the page has it.

        These are what the dashboard tiles call on click. Calling them directly
        fetches the same data without opening a modal or needing a click.
        """
        if not name:
            return False
        if "dashboard" in (page.url or "").lower():
            self._wait_for_opener(page, 10)  # page scripts ready after a reload
        try:
            called = bool(page.evaluate(
                "(name) => { if (typeof window[name] !== 'function') return false;"
                " window[name](); return true; }",
                name,
            ))
        except Exception as exc:  # noqa: BLE001 - page navigating
            log.info("[UMS] calling %s() failed: %s", name, type(exc).__name__)
            return False
        if called:
            attempts.append(f"called:{name}()")
            log.info("[UMS] Called UMS page function %s()", name)
        return called

    @staticmethod
    def _is_error_page(info: dict[str, Any]) -> bool:
        title = (info.get("title") or "").lower()
        return any(text in title for text in (
            "resource cannot be found", "server error", "runtime error", "404", "not found",
        ))

    @staticmethod
    def _clear_stray_backdrop(page: Page) -> None:
        """Remove a Bootstrap backdrop left behind with no modal open.

        It covers the whole page and swallows clicks - the student's as well as
        ours. Only acts when no modal is actually showing.
        """
        try:
            removed = page.evaluate(
                """() => {
                    if (document.querySelector('.modal.show, .modal.in')) return 0;
                    const stray = document.querySelectorAll('.modal-backdrop');
                    stray.forEach(e => e.remove());
                    document.body.classList.remove('modal-open');
                    document.body.style.removeProperty('padding-right');
                    document.body.style.removeProperty('overflow');
                    return stray.length;
                }"""
            )
            if removed:
                log.info("[UMS] Removed %d leftover modal backdrop(s)", removed)
        except Exception:  # noqa: BLE001 - page navigating
            pass

    def _wait_for_opener(self, page: Page, seconds: float) -> bool:
        """Wait until an attendance opener (the dashboard tile) is visible."""
        deadline = time.time() + seconds
        while True:
            for selector in settings.ums_attendance_openers_list:
                for frame in page.frames:
                    try:
                        locator = frame.locator(selector).first
                        if locator.count() and locator.is_visible():
                            return True
                    except Exception:  # noqa: BLE001 - frame navigating or detached
                        continue
            if time.time() >= deadline:
                return False
            time.sleep(0.5)

    def _click_openers(self, page: Page, attempts: list[str]) -> tuple[Page, dict[str, Any] | None] | None:
        """Click the configured controls that *load* the attendance panel.

        Some portals never put attendance on a URL at all. LPU UMS renders the
        table into a modal only after its dashboard tile calls ``getAtt()``, so
        until that click there is no table in the DOM to find - no amount of
        navigating or frame searching would ever have located it.
        """
        if "dashboard" in (page.url or "").lower():
            # Just after a reload (e.g. coming back from the leave page) the
            # dashboard tiles take a few seconds to appear; checking once at
            # that moment finds nothing and gives up.
            self._wait_for_opener(page, 10)
        self._clear_stray_backdrop(page)
        clicked: set[str] = set()
        for selector in settings.ums_attendance_openers_list:
            for frame in page.frames:
                try:
                    locator = frame.locator(selector).first
                    if not locator.count() or not locator.is_visible():
                        continue
                    # "#AttPercent" and "[onclick*='getAtt']" are the same tile.
                    # Clicking it twice toggles the modal shut mid-animation and
                    # leaves a backdrop over the page that blocks every click.
                    element_key = frame.url + "|" + locator.evaluate(
                        "e => e.id || e.outerHTML.slice(0, 200)"
                    )
                    if element_key in clicked:
                        continue
                    clicked.add(element_key)
                except Exception:  # noqa: BLE001
                    continue
                attempts.append(f"opener:{selector}")
                log.info("[UMS] Clicking attendance opener %s", selector)
                try:
                    locator.scroll_into_view_if_needed(timeout=3000)
                    locator.click(timeout=6000)
                except Exception as exc:  # noqa: BLE001
                    log.info("[UMS] opener %s failed: %s", selector, type(exc).__name__)
                    continue
                if self._wait_for_attendance_table(page) is not None:
                    log.info("[UMS] Attendance panel opened by %s", selector)
                    return page, {"selector": selector, "text": f"opener {selector}", "opener": True}
                log.info("[UMS] opener %s did not produce a table", selector)
        return None

    def _explore(self, page: Page) -> list[tuple[Frame, dict[str, Any]]]:
        """Ranked attendance controls across every frame. No clicking."""
        found: list[tuple[Frame, dict[str, Any]]] = []
        for frame in page.frames:
            try:
                items = frame.evaluate(EXPLORE_JS)
            except Exception:  # noqa: BLE001 - detached or cross-origin frame
                continue
            for item in rank_candidates(list(items or [])):
                item["frame_url"] = frame.url
                found.append((frame, item))
        # Visible controls first, then by score - see navigation.rank_candidates.
        found.sort(key=lambda c: (bool(c[1].get("visible")), c[1]["score"]), reverse=True)
        return found

    def attendance_detail(self, force: bool = False) -> dict[str, Any]:
        """Class-by-class attendance, per course."""
        return self._get("attendance_detail", force)

    def leave(self, force: bool = False) -> dict[str, Any]:
        """Hostel leave balances and authorities. READ ONLY - nothing is filled or submitted."""
        return self._get("leave", force)

    def student_profile(self, force: bool = False) -> dict[str, Any]:
        """Who the student is, read from UMS. READ ONLY."""
        return self._get("profile", force)

    def prefill_leave(self, draft: dict[str, Any]) -> dict[str, Any]:
        """Type a validated draft into the UMS leave form and STOP.

        Fills only the five configured fields, each located by its own label
        through a locator that refuses to return a checkbox or a button. The
        acknowledgement is never ticked, Submit is never clicked, and the form
        is read back afterwards so the student can see exactly what was entered.
        """
        if not settings.ums_allow_prefill:
            raise UMSLiveAttendanceUnavailable(
                "Filling the UMS leave form is switched off. Set UMS_ALLOW_PREFILL=true in "
                ".env to enable it. CampusAI still never ticks the acknowledgement or submits.",
                self.diagnostics(),
            )
        status = self.status()
        if not status["browser_connected"] or not status["authenticated"]:
            raise UMSLiveAttendanceUnavailable(self._unavailable_reason(status), status["diagnostics"])
        return self._call(
            lambda: self._prefill_leave(draft), timeout=settings.ums_capture_timeout_seconds
        )

    def timetable(self, force: bool = False) -> dict[str, Any]:
        """Live timetable from the authenticated UMS session."""
        return self._get("timetable", force)

    def announcements(self, force: bool = False) -> dict[str, Any]:
        """Live announcements from the authenticated UMS session."""
        return self._get("announcements", force)

    def messages(self, force: bool = False) -> dict[str, Any]:
        """The latest messages (newest first) from the student's UMS message store."""
        return self._get("messages", force)

    def search_messages(self, query: str = "", days: int | None = None, max_rows: int = 100) -> dict[str, Any]:
        """Search the student's WHOLE message history (not just the recent panel).

        ``query`` is matched by UMS itself against subjects and message text;
        ``days`` keeps only messages from the last N days. Cached briefly.
        """
        key = f"{query.strip().lower()}|{days}|{max_rows}"
        cached = self._message_searches.get(key)
        if cached and time.time() - cached["updated_at"] <= settings.ums_message_search_ttl_seconds:
            return cached
        status = self.status()
        if not status["browser_connected"] or not status["authenticated"]:
            raise UMSLiveAttendanceUnavailable(self._unavailable_reason(status), status["diagnostics"])
        result = self._call(
            lambda: self._search_messages(query.strip(), days, max_rows),
            timeout=settings.ums_capture_timeout_seconds,
        )
        self._message_searches[key] = result
        return result

    # ------------------------------------------------------- message store
    def _store_page(self, page: Page, page_index: int, subject: str, description: str) -> list[dict[str, Any]]:
        url = settings.ums_url.rstrip("/") + "/" + settings.ums_message_store_method.lstrip("/")
        args = {"url": url, "pageIndex": page_index, "subject": subject, "description": description}
        try:
            out = page.evaluate(MESSAGE_STORE_JS, args)
        except Exception:  # noqa: BLE001 - page mid-navigation (another read moved it)
            time.sleep(1.5)
            page = self._pick_ums_page() or page
            out = page.evaluate(MESSAGE_STORE_JS, args)
        if not isinstance(out, dict) or out.get("status") != 200 or "rows" not in out:
            raise UMSLiveAttendanceUnavailable(
                f"The UMS message store did not answer (HTTP {out.get('status') if isinstance(out, dict) else '?'}).",
                self.diagnostics(),
            )
        rows = out.get("rows")
        return rows if isinstance(rows, list) else []

    def _read_store(
        self, subject: str, description: str, max_rows: int, since_iso: str | None
    ) -> tuple[list[dict[str, Any]], int]:
        """Page through the store (newest first) until enough rows or too old."""
        from app.services.schedule import parse_datetime

        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable(
                f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
            )
        records: list[dict[str, Any]] = []
        total, pages = 0, 1
        page_index = 1
        while page_index <= settings.ums_message_max_pages:
            rows = self._store_page(page, page_index, subject, description)
            if page_index == 1:
                total, pages = message_totals(rows)
            batch = parse_message_rows(rows)
            records.extend(batch)
            if not batch or len(records) >= max_rows or page_index >= pages:
                break
            if since_iso:
                oldest = parse_datetime(batch[-1]["date"])
                if oldest and oldest["iso"] < since_iso:
                    break
            page_index += 1
        return records, total

    def _add_senders(self, records: list[dict[str, Any]]) -> None:
        """The store has no sender; the dashboard panel does for recent messages."""
        panel = self._panels.get("messages") or {}
        senders = {
            re.sub(r"\s+", " ", (item.get("title") or "")).strip().lower(): item.get("sender")
            for item in panel.get("panel_items") or []
            if item.get("sender")
        }
        for record in records:
            if not record.get("sender"):
                record["sender"] = senders.get(re.sub(r"\s+", " ", record["title"]).strip().lower(), "")

    def _fetch_messages(self) -> dict[str, Any]:
        """Prefetch: the latest messages from the store, senders from the panel."""
        page = self._pick_ums_page()
        panel_items: list[dict[str, Any]] = []
        if page is not None:
            try:  # the dashboard panel is already on screen: no clicks needed
                panel_items = dedupe(self._read_containers(page, ["#MyMessage"], []))
            except Exception:  # noqa: BLE001 - senders are a nice-to-have
                panel_items = []
        try:
            records, total = self._read_store("", "", settings.ums_message_prefetch_rows, None)
            records = dedupe_messages(records)
        except Exception as exc:  # noqa: BLE001 - fall back to the old panel reading
            log.info("[UMS] message store unavailable (%s); reading the dashboard panel", exc)
            return self._capture_panel(
                "messages",
                settings.ums_message_containers_list,
                settings.ums_message_openers_list,
                settings.ums_message_page,
            )
        result = {
            "available": True,
            "kind": "messages",
            "source": "UMS message store",
            "count": len(records),
            "items": records,
            "total_in_store": total,
            "panel_items": panel_items,
            "updated_at": time.time(),
        }
        self._panels["messages"] = result
        self._add_senders(records)
        return result

    def _search_messages(self, query: str, days: int | None, max_rows: int) -> dict[str, Any]:
        from datetime import date, timedelta

        from app.services.schedule import parse_datetime

        since_iso = (date.today() - timedelta(days=days)).isoformat() if days else None
        if query:
            # UMS searches subject and text separately; ask both, merge.
            by_subject, _ = self._read_store(query, "", max_rows, since_iso)
            by_text, _ = self._read_store("", query, max_rows, since_iso)
            records = dedupe_messages(by_subject + by_text)
        else:
            records, _ = self._read_store("", "", max_rows if not days else settings.ums_message_max_pages * 20, since_iso)
            records = dedupe_messages(records)

        def iso(record: dict[str, Any]) -> str:
            stamp = parse_datetime(record.get("date"))
            return stamp["iso"] if stamp else ""

        if since_iso:
            records = [r for r in records if iso(r) and iso(r) >= since_iso]
        records.sort(key=iso, reverse=True)
        self._add_senders(records)
        cached = self._panels.get("messages") or {}
        return {
            "available": True,
            "source": "UMS message store",
            "items": records[:max_rows],
            "total_matching": len(records),
            "total_in_store": cached.get("total_in_store"),
            "query": query,
            "days": days,
            "updated_at": time.time(),
        }

    # ------------------------------------------------------- cache & prefetch
    #
    # Everything read from UMS is kept in memory (never on disk) so a chat
    # answer can use it at once. Right after sign-in the idle monitor reads
    # each item in turn; later it re-reads items older than
    # UMS_REFRESH_AFTER_SECONDS. A question that arrives meanwhile is queued
    # between items, so it never waits for the whole prefetch.

    def _age(self, kind: str) -> float | None:
        """Seconds since this item was read, or None if it has not been."""
        if kind == "attendance":
            stamp = self._attendance_updated_at if self._attendance is not None else None
        else:
            entry = self._panels.get(kind)
            stamp = entry.get("updated_at") if entry else None
        return None if stamp is None else time.time() - stamp

    def _cached(self, kind: str) -> dict[str, Any] | None:
        age = self._age(kind)
        if age is None or age > settings.ums_cache_max_age_seconds:
            return None
        return self._panels.get(kind)

    def _get(self, kind: str, force: bool = False) -> dict[str, Any]:
        """Cached data when recent enough, otherwise read it from UMS now."""
        if not force:
            cached = self._cached(kind)
            if cached is not None:
                return cached
        status = self.status()
        if not status["browser_connected"] or not status["authenticated"]:
            raise UMSLiveAttendanceUnavailable(self._unavailable_reason(status), status["diagnostics"])

        def run() -> dict[str, Any]:
            # The prefetch may have read it while this request was queued.
            if not force:
                cached = self._cached(kind)
                if cached is not None:
                    return cached
            return self._fetch_now(kind)

        return self._call(run, timeout=settings.ums_capture_timeout_seconds)

    def _fetch_now(self, kind: str) -> dict[str, Any]:
        """Read one item from UMS and cache it. Runs on the worker thread."""
        if kind == "attendance":
            page = self._pick_ums_page()
            if page is None:
                raise UMSLiveAttendanceUnavailable(
                    f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
                )
            self._capture(page)
            self._item_generation[kind] = self._generation
            return self._attendance or {}
        if kind == "attendance_detail":
            result = self._capture_detail()
        elif kind == "leave":
            result = self._capture_leave()
        elif kind == "profile":
            result = self._capture_profile()
        elif kind == "timetable":
            result = self._capture_timetable()
        elif kind == "announcements":
            result = self._capture_panel(
                "announcements",
                settings.ums_announcement_containers_list,
                settings.ums_announcement_openers_list,
                settings.ums_announcement_page,
            )
        elif kind == "messages":
            result = self._fetch_messages()
        else:
            raise ValueError(f"Unknown UMS item {kind!r}")
        self._panels[kind] = result
        self._item_generation[kind] = self._generation
        return result

    def _prefetch_due(self, kind: str) -> bool:
        failed = self._prefetch_errors.get(kind)
        if failed:
            # Back off: 2, 4, 8 ... minutes, at most 30, so a page that keeps
            # failing does not keep tying up the browser.
            wait = min(settings.ums_prefetch_retry_seconds * 2 ** (failed[2] - 1), 1800)
            if time.time() - failed[0] < wait:
                return False
        age = self._age(kind)
        if age is None or self._item_generation.get(kind, 0) < self._generation:
            return True
        refresh = settings.ums_refresh_after_seconds
        return refresh > 0 and age > refresh

    def _prefetch_step(self) -> None:
        """Read the first missing or stale item. One per idle tick."""
        if not settings.ums_prefetch:
            return
        kind = next((k for k in settings.ums_prefetch_items_list if self._prefetch_due(k)), None)
        if kind is None:
            return
        self._prefetch_current = kind
        started = time.time()
        try:
            self._fetch_now(kind)
            self._prefetch_errors.pop(kind, None)
            log.info("[UMS] prefetched %s in %.1fs", kind, time.time() - started)
        except Exception as exc:  # noqa: BLE001 - retried later, reported in status
            count = self._prefetch_errors.get(kind, (0, "", 0))[2] + 1
            self._prefetch_errors[kind] = (time.time(), str(exc), count)
            log.info("[UMS] prefetch of %s failed: %s", kind, exc)
        finally:
            self._prefetch_current = None

    def _prefetch_status(self) -> dict[str, Any]:
        items = {}
        for kind in settings.ums_prefetch_items_list:
            age = self._age(kind)
            failed = self._prefetch_errors.get(kind)
            items[kind] = {
                "ready": age is not None,
                "age_seconds": None if age is None else round(age),
                "error": failed[1] if failed else None,
            }
        return {
            "enabled": settings.ums_prefetch,
            "current": self._prefetch_current,
            "ready_count": sum(1 for item in items.values() if item["ready"]),
            "total": len(items),
            "items": items,
        }

    def _clear_cache(self) -> None:
        with self._status_lock:
            self._attendance = None
            self._attendance_updated_at = None
            self._panels = {}
            self._prefetch_errors = {}
            self._item_generation = {}
            self._message_searches = {}

    def inspect(
        self,
        selectors: list[str],
        depth: int,
        html: bool,
        openers: list[str],
        url: str = "",
        wait: float = 2.0,
    ) -> dict[str, Any]:
        """Structural probe of specific containers, for designing a parser.

        With ``url`` it first opens that UMS page (a plain GET, refused for
        anything that looks like an action), and returns the browser to where it
        started afterwards.
        """
        return self._call(
            lambda: self._inspect(selectors, depth, html, openers, url, wait), timeout=120
        )

    def site_map(self) -> dict[str, Any]:
        """Read-only inventory of the current UMS page. Navigates nothing."""
        return self._call(lambda: self._site_map(None, 0), timeout=60)

    def crawl(self, topics: list[str], max_visits: int) -> dict[str, Any]:
        """Inventory the dashboard, then open a few safe report pages by URL.

        Only same-host ``.aspx`` links that are not flagged as actions are
        visited, each by direct navigation - nothing is clicked and no form is
        ever submitted. The browser is returned to where it started.
        """
        return self._call(
            lambda: self._site_map(topics, max_visits),
            timeout=30 + max_visits * 25,
        )

    def explore(self) -> dict[str, Any]:
        """Diagnostic: what CampusAI can see and how it ranks it. Clicks nothing."""
        return self._call(self._explore_report, timeout=30)

    def _explore_report(self) -> dict[str, Any]:
        page = self._pick_ums_page()
        if page is None:
            return {"error": f"No {settings.ums_host} tab is open.", "candidates": []}
        candidates = self._explore(page)
        return {
            "page_url": page.url,
            "title": self._safe_title(page),
            "frame_urls": [f.url for f in page.frames][:15],
            "remembered_target": self._load_target(),
            "candidates": [
                {
                    "score": item["score"], "tag": item["tag"], "text": item["text"],
                    "href": item["href"], "onclick": item["onclick"],
                    "selector": item["selector"], "visible": item["visible"],
                    "frame_url": item["frame_url"],
                    "would_click": item["score"] >= settings.ums_min_candidate_score,
                }
                for _, item in candidates[:30]
            ],
        }

    #: What a profile is allowed to carry out of the leave page. The leave page
    #: also exposes a mobile number and the student's pending application; none
    #: of that belongs in an identity record, so it is not copied across.
    PROFILE_KEYS = ("name", "student_id", "program", "department", "section",
                    "term", "hostel", "room")

    def _capture_profile(self) -> dict[str, Any]:
        """Read the student's identity: dashboard first, leave page as fallback.

        The dashboard hides the name from the site map entirely - it is in no
        link, panel or table - so this reads it the way a person would.

        When that yields nothing it opens the hostel leave page and reads the
        identity block there directly. It deliberately does NOT go through the
        leave-balance capture: the balances are a separate parse that can fail
        on its own, and the student's name should not disappear because a
        balance table changed shape.
        """
        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable(
                f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
            )
        origin = page.url
        attempts: list[str] = []
        profile: dict[str, Any] = {}
        seen_labels: list[str] = []

        for frame in page.frames:
            try:
                # A pure query: no click, no fill, nothing written.
                payload = frame.evaluate(PROFILE_JS)
            except Exception:  # noqa: BLE001 - detached or cross-origin frame
                continue
            seen_labels.extend(
                (field.get("label") or "") for field in (payload.get("fields") or [])[:20]
            )
            parsed = parse_profile(payload)
            if parsed.get("name"):
                profile = merge_profile(parsed, profile)
                attempts.append(f"dashboard:{parsed.get('name_source') or 'found'}")
                if is_strong(parsed):
                    break
            elif parsed and not profile:
                profile = parsed  # keep any registration number even without a name

        ok, _ = validate_profile(profile)
        # A name that came only from a "Welcome, X" match is not trusted on its
        # own - the leave page prints it against an actual label, so go and
        # check. This is what stopped a line of marketing copy becoming a name.
        if not ok or not is_strong(profile):
            attempts.append("dashboard:no-name")
            target = settings.ums_url.rstrip("/") + "/" + settings.ums_leave_page.lstrip("/")
            try:
                attempts.append(f"goto:{settings.ums_leave_page}")
                page.goto(target, wait_until="domcontentloaded", timeout=25000)
                time.sleep(settings.ums_leave_wait_seconds)

                for frame in page.frames:
                    fallback: dict[str, Any] = {}
                    # Two readings of the same page, because the identity block
                    # is laid out differently from the balance tables.
                    try:
                        fallback = parse_profile(frame.evaluate(PROFILE_JS))
                    except Exception:  # noqa: BLE001
                        fallback = {}
                    if not fallback.get("name"):
                        try:
                            # The leave page's own field parser - this is the
                            # reading proven to yield the name in practice.
                            leave = parse_leave(frame.evaluate(LEAVE_JS)) or {}
                        except Exception:  # noqa: BLE001
                            leave = {}
                        fields = leave.get("profile") or {}
                        seen_labels.extend(sorted(fields))
                        fallback = {
                            key: value for key, value in fields.items()
                            if key in self.PROFILE_KEYS and value
                        }
                        if fallback.get("name"):
                            fallback["name_source"] = "leave-page-fields"
                    if fallback.get("name"):
                        attempts.append(f"leave:{','.join(sorted(k for k in fallback if k != 'name_source'))}")
                        # The leave page is labelled, so its name wins over a
                        # greeting - but never over a labelled dashboard field.
                        if is_strong(fallback) and not is_strong(profile):
                            profile = merge_profile(fallback, profile)
                            profile["name"] = fallback["name"]
                            profile["name_source"] = fallback.get("name_source") or "leave-page"
                        else:
                            profile = merge_profile(profile, fallback)
                        break
                else:
                    attempts.append("leave:no-name")
            finally:
                self._restore(page, origin, attempts)

        ok, reason = validate_profile(profile)
        log.info("[UMS] Student profile: valid=%s (%s) via %s", ok, reason, attempts)
        if not ok:
            raise UMSLiveAttendanceUnavailable(
                "UMS is authenticated, but your name could not be read from the dashboard or "
                f"the hostel leave page. Result: {reason}.",
                {
                    **self.diagnostics(),
                    "profile_attempts": attempts,
                    # The labels that were on the pages, so the next fix is a
                    # one-line config change rather than another guess.
                    "profile_labels_seen": sorted({label for label in seen_labels if label})[:40],
                },
            )
        return {
            "available": True,
            "kind": "profile",
            "source": "UMS Playwright session",
            "read_only": True,
            "profile": profile,
            "attempts": attempts,
            "labels_seen": sorted({label for label in seen_labels if label})[:40],
            "updated_at": time.time(),
        }

    def _capture_leave(self) -> dict[str, Any]:
        """Open the hostel leave page, read it, come back. No interaction."""
        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable(
                f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
            )
        origin = page.url
        attempts: list[str] = []
        target = settings.ums_url.rstrip("/") + "/" + settings.ums_leave_page.lstrip("/")

        try:
            attempts.append(f"goto:{target}")
            log.info("[UMS] Opening hostel leave page (read only)")
            page.goto(target, wait_until="domcontentloaded", timeout=25000)
            time.sleep(settings.ums_leave_wait_seconds)

            record = None
            for frame in page.frames:
                try:
                    # A pure query. No click, no fill, no submit anywhere in this path.
                    payload = frame.evaluate(LEAVE_JS)
                except Exception:  # noqa: BLE001 - detached or cross-origin frame
                    continue
                parsed = parse_leave(payload)
                if parsed and parsed.get("balances"):
                    record = parsed
                    attempts.append(f"balances:{len(parsed['balances'])}")
                    break

            ok, reason = validate_leave(record)
            log.info("[UMS] Hostel leave: valid=%s (%s)", ok, reason)
            if not ok:
                raise UMSLiveAttendanceUnavailable(
                    "UMS is authenticated, but the hostel leave balances could not be read from "
                    f"{settings.ums_leave_page}. Result: {reason}.",
                    {**self.diagnostics(), "leave_attempts": attempts},
                )
            return {
                "available": True,
                "kind": "leave",
                "source": "UMS Playwright session",
                "read_only": True,
                **record,
                "attempts": attempts,
                "updated_at": time.time(),
            }
        finally:
            self._restore(page, origin, attempts)

    def _prefill_leave(self, draft: dict[str, Any]) -> dict[str, Any]:
        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable(
                f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
            )
        target = settings.ums_url.rstrip("/") + "/" + settings.ums_leave_page.lstrip("/")
        if settings.ums_leave_page.lower() not in page.url.lower():
            page.goto(target, wait_until="domcontentloaded", timeout=25000)
            time.sleep(settings.ums_leave_wait_seconds)

        labels = settings.ums_leave_field_labels
        values = {
            "leave_type": draft.get("leave_type", ""),
            "start": format_for_ums(draft.get("start", ""), settings.ums_leave_datetime_format),
            "end": format_for_ums(draft.get("end", ""), settings.ums_leave_datetime_format),
            "visit_place": draft.get("visit_place", ""),
            "reason": draft.get("reason", ""),
        }

        filled: list[dict[str, Any]] = []
        refused: list[dict[str, Any]] = []
        # Two passes: an ASP.NET dropdown often posts back and clears the rest.
        for attempt in range(2):
            located = {
                item["label"]: item
                for item in page.evaluate(LOCATE_JS, {"labels": list(labels.values())}) or []
            }
            pending = False
            for key, label in labels.items():
                field = located.get(label) or {"label": label, "missing": True}
                if field.get("missing") or field.get("refused"):
                    if attempt == 0:
                        refused.append({
                            "field": key, "label": label,
                            "reason": field.get("refused") or "not found on the page",
                        })
                    continue
                wanted = values[key]
                if not wanted or (field.get("value") or "").strip() == wanted.strip():
                    continue
                pending = True
                try:
                    locator = page.locator(field["selector"]).first
                    if field["kind"] == "select-one":
                        locator.select_option(label=wanted)
                    else:
                        locator.fill(wanted)
                    if attempt == 0:
                        filled.append({"field": key, "label": label, "value": wanted})
                except Exception as exc:  # noqa: BLE001
                    refused.append({"field": key, "label": label, "reason": type(exc).__name__})
                time.sleep(0.4)
            if not pending:
                break
            time.sleep(1.2)  # let any postback settle before verifying

        # Read the form back rather than trusting what we typed.
        time.sleep(0.8)
        verified = {
            item["label"]: item.get("value", "")
            for item in page.evaluate(LOCATE_JS, {"labels": list(labels.values())}) or []
        }
        acknowledged = page.evaluate(
            "() => Array.from(document.querySelectorAll('input[type=checkbox]'))"
            ".some(c => c.checked)"
        )
        log.info(
            "[UMS] Leave form prefilled: %d field(s), %d refused, acknowledgement ticked=%s",
            len(filled), len(refused), acknowledged,
        )
        if acknowledged:
            # Never our doing - but say so loudly rather than quietly proceeding.
            log.warning("[UMS] A checkbox on the leave page is ticked; CampusAI did not tick it.")

        return {
            "available": True,
            "kind": "leave_prefill",
            "source": "UMS Playwright session",
            "submitted": False,
            "acknowledgement_ticked": acknowledged,
            "filled": filled,
            "refused": refused,
            "form_now": {label: verified.get(label, "") for label in labels.values()},
            "next_step": (
                "The form is filled in the CampusAI browser window. Check every field, tick the "
                "acknowledgement yourself, and press Submit there. CampusAI has not submitted "
                "anything and cannot."
            ),
            "updated_at": time.time(),
        }

    def _capture_timetable(self) -> dict[str, Any]:
        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable(
                f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
            )
        origin = page.url
        attempts: list[str] = []
        target = settings.ums_url.rstrip("/") + "/" + settings.ums_timetable_page.lstrip("/")

        try:
            if settings.ums_timetable_page.lower() not in page.url.lower():
                attempts.append(f"goto:{target}")
                log.info("[UMS] Opening timetable page %s", target)
                page.goto(target, wait_until="domcontentloaded", timeout=25000)
                time.sleep(1.0)

            # The page ships empty; the grid only exists after the AJAX loader runs.
            self._open_panels(page, settings.ums_timetable_openers_list, attempts)
            time.sleep(settings.ums_timetable_wait_seconds)

            classes: list[dict[str, Any]] = []
            for frame in page.frames:
                try:
                    payload = frame.evaluate(
                        TIMETABLE_JS, {"selector": settings.ums_timetable_container}
                    )
                except Exception:  # noqa: BLE001 - detached or cross-origin frame
                    continue
                found = parse_timetable(payload)
                if found:
                    attempts.append(f"{settings.ums_timetable_container}:{len(found)}")
                    classes = found
                    break

            ok, reason = validate_timetable(classes)
            log.info("[UMS] Timetable: %d slot(s), valid=%s (%s)", len(classes), ok, reason)
            if not ok:
                raise UMSLiveAttendanceUnavailable(
                    "UMS is authenticated, but the timetable could not be read from "
                    f"{settings.ums_timetable_container} on {settings.ums_timetable_page}. "
                    f"Result: {reason}.",
                    {**self.diagnostics(), "timetable_attempts": attempts},
                )
            return {
                "available": True,
                "kind": "timetable",
                "source": "UMS Playwright session",
                "count": len(classes),
                "classes": classes,
                "attempts": attempts,
                "updated_at": time.time(),
            }
        finally:
            self._restore(page, origin, attempts)

    def _capture_detail(self) -> dict[str, Any]:
        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable(
                f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
            )
        attempts: list[str] = []
        selector = settings.ums_attendance_detail_selector

        def read() -> dict[str, Any]:
            found_all: dict[str, Any] = {}
            for frame in page.frames:
                try:
                    payload = frame.evaluate(DETAIL_JS, {"selector": selector})
                except Exception:  # noqa: BLE001 - detached or cross-origin frame
                    continue
                found = parse_detail_tables(payload)
                if found:
                    attempts.append(f"{selector}:{len(found)} in {frame.url[:60]}")
                    found_all.update({k: v for k, v in found.items() if k not in found_all})
            return found_all

        def wait_for_logs(seconds: float) -> dict[str, Any]:
            deadline = time.time() + seconds
            while True:
                found = read()
                if found or time.time() >= deadline:
                    return found
                time.sleep(0.75)

        # The Attendance tile (getAtt) makes TWO requests: the summary and,
        # separately, the class-by-class log, which empties its area first and
        # fills it when the server replies - usually after the summary. So the
        # log may still be on its way from a recent click: wait briefly first,
        # and after clicking, keep checking rather than looking once.
        courses = wait_for_logs(3)
        if not courses:
            # Ask UMS for the log the way its own tile does, but without opening
            # the modal: nothing moves on the student's screen and there is no
            # click to be blocked. Falls back to clicking the tile.
            if self._call_page_function(page, settings.ums_attendance_detail_loader, attempts):
                courses = wait_for_logs(settings.ums_table_wait_seconds)
            if not courses:
                log.info("[UMS] No class logs yet; opening the attendance panel")
                if self._click_openers(page, attempts) is not None:
                    courses = wait_for_logs(settings.ums_table_wait_seconds)

        ok, reason = validate_detail(courses)
        log.info("[UMS] Attendance detail: %d course(s), valid=%s (%s)", len(courses), ok, reason)
        if not ok:
            raise UMSLiveAttendanceUnavailable(
                "UMS is authenticated, but the class-by-class attendance log could not be read. "
                f"Selector: {selector}. Result: {reason}.",
                {**self.diagnostics(), "detail_attempts": attempts},
            )
        return {
            "available": True,
            "kind": "attendance_detail",
            "source": "UMS Playwright session",
            "count": len(courses),
            "courses": courses,
            "attempts": attempts,
            "updated_at": time.time(),
        }

    def _open_panels(self, page: Page, openers: list[str], attempts: list[str]) -> None:
        """Click the controls that render a panel. Same idea as #AttPercent."""
        for selector in openers:
            for frame in page.frames:
                try:
                    locator = frame.locator(selector).first
                    if not locator.count() or not locator.is_visible():
                        continue
                    locator.scroll_into_view_if_needed(timeout=3000)
                    locator.click(timeout=5000)
                    attempts.append(f"opener:{selector}")
                    log.info("[UMS] Opened panel with %s", selector)
                    time.sleep(1.2)
                except Exception as exc:  # noqa: BLE001
                    log.info("[UMS] panel opener %s failed: %s", selector, type(exc).__name__)
                break

    def _read_containers(
        self, page: Page, containers: list[str], attempts: list[str]
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        config = {
            "max": settings.ums_panel_max_items,
            "maxLines": settings.ums_panel_max_lines,
            "titleSelectors": settings.ums_card_title_selectors_list,
            "dateSelectors": settings.ums_card_date_selectors_list,
            "bodySelectors": settings.ums_card_body_selectors_list,
        }
        for selector in containers:
            for frame in page.frames:
                try:
                    payload = frame.evaluate(CARDS_JS, {**config, "selector": selector})
                except Exception:  # noqa: BLE001 - detached or cross-origin frame
                    continue
                if not payload:
                    continue
                found = parse_cards(payload, frame.url or page.url, channel=selector,
                                    max_titles=settings.ums_card_max_title_elements)
                attempts.append(f"{selector}:{len(found)}")
                log.info(
                    "[UMS] Container %s -> %d child node(s), %d parsed",
                    selector, payload.get("children", 0), len(found),
                )
                records.extend(found)
        return records

    def _capture_panel(
        self, kind: str, containers: list[str], openers: list[str], page_path: str
    ) -> dict[str, Any]:
        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable(
                f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
            )
        origin = page.url
        attempts: list[str] = []
        log.info("[UMS] Capturing %s from %s", kind, origin)

        self._open_panels(page, openers, attempts)
        records = dedupe(self._read_containers(page, containers, attempts))
        ok, reason = validate_cards(records, kind)

        # The dashboard panel can be empty (nothing recent). Fall back to the
        # dedicated page, which is a plain GET, then come back.
        if not ok and page_path:
            url = page_path if page_path.startswith("http") else settings.ums_url.rstrip("/") + "/" + page_path.lstrip("/")
            attempts.append(f"goto:{url}")
            log.info("[UMS] %s panel empty (%s); opening %s", kind, reason, url)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                time.sleep(1.5)
                page_records = dedupe(self._read_containers(page, containers + ["body"], attempts))
                if page_records:
                    records = dedupe(records + page_records)
                    ok, reason = validate_cards(records, kind)
            except Exception as exc:  # noqa: BLE001
                attempts.append(f"goto-failed:{type(exc).__name__}")
            finally:
                self._restore(page, origin, attempts)

        log.info("[UMS] %s: %d item(s), valid=%s (%s)", kind, len(records), ok, reason)
        if not ok:
            raise UMSLiveAttendanceUnavailable(
                f"UMS is authenticated, but no {kind} could be extracted. "
                f"Containers tried: {containers}. Result: {reason}.",
                {**self.diagnostics(), "panel_attempts": attempts, "panel_kind": kind},
            )
        return {
            "available": True,
            "kind": kind,
            "source": "UMS Playwright session",
            "count": len(records),
            "items": records,
            "attempts": attempts,
            "updated_at": time.time(),
        }

    def _inspect(
        self,
        selectors: list[str],
        depth: int,
        html: bool,
        openers: list[str],
        url: str = "",
        wait: float = 2.0,
    ) -> dict[str, Any]:
        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable(
                f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
            )
        attempts: list[str] = []
        origin = page.url

        if url:
            target = url if url.startswith("http") else settings.ums_url.rstrip("/") + "/" + url.lstrip("/")
            if settings.ums_host not in _host(target):
                raise UMSLiveAttendanceUnavailable(
                    f"Refusing to open {target}: not on {settings.ums_host}.", self.diagnostics()
                )
            if is_action({"text": "", "href": target}):
                raise UMSLiveAttendanceUnavailable(
                    f"Refusing to open {target}: it looks like an action, not a report page.",
                    self.diagnostics(),
                )
            attempts.append(f"goto:{target}")
            log.info("[UMS] Inspect opening %s", target)
            page.goto(target, wait_until="domcontentloaded", timeout=25000)
            time.sleep(max(0.5, min(wait, 15)))

        if openers:
            self._open_panels(page, openers, attempts)
            time.sleep(max(0.5, min(wait, 15)))
        config = {
            "depth": max(1, min(depth, 6)), "breadth": 8, "html": bool(html),
            "samples": 2, "htmlChars": 3000,
        }
        results = []
        for selector in selectors:
            for frame in page.frames:
                try:
                    payload = frame.evaluate(INSPECT_JS, {**config, "selector": selector})
                except Exception:  # noqa: BLE001
                    continue
                if payload and payload.get("exists"):
                    payload["frame_url"] = frame.url
                    results.append(payload)
                    break
            else:
                results.append({"selector": selector, "exists": False})
        report = {"page_url": page.url, "title": self._safe_title(page),
                  "openers": attempts, "results": results}
        if url:
            self._restore(page, origin, attempts)
        return report

    def _map_page(self, page: Page) -> list[dict[str, Any]]:
        frames: list[dict[str, Any]] = []
        for frame in page.frames:
            try:
                dump = frame.evaluate(MAP_JS)
            except Exception:  # noqa: BLE001 - detached or cross-origin frame
                continue
            if dump:
                frames.append(dump)
        return frames

    def _visit_targets(self, mapped: dict[str, Any], topics: list[str], limit: int) -> list[dict[str, str]]:
        """Pick safe, same-host report pages to open. Read-only pages only."""
        base = settings.ums_url.rstrip("/") + "/"
        chosen: dict[str, dict[str, str]] = {}
        for topic in topics:
            for link in (mapped["by_topic"].get(topic) or {}).get("links", []):
                href = (link.get("href") or "").strip()
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                if is_action(link):
                    continue
                lowered = href.lower()
                if lowered.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip")):
                    continue
                if "openapp.aspx" in lowered:  # cross-application launcher
                    continue
                url = href if href.startswith("http") else base + href.lstrip("/")
                if settings.ums_host not in _host(url):
                    continue
                if url in chosen:
                    continue
                chosen[url] = {"url": url, "text": link.get("text", ""), "topic": topic}
                if len(chosen) >= limit:
                    return list(chosen.values())
        return list(chosen.values())

    def _site_map(self, topics: list[str] | None, max_visits: int) -> dict[str, Any]:
        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable(
                f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
            )
        origin = page.url
        log.info("[UMS] Mapping %s", origin)
        mapped = build_site_map(self._map_page(page))
        mapped["origin"] = origin
        mapped["visited"] = []
        mapped["skipped"] = []

        if not topics or max_visits <= 0:
            return mapped

        targets = self._visit_targets(mapped, topics, max_visits)
        log.info("[UMS] Crawl plan: %s", [t["url"] for t in targets])
        for target in targets:
            try:
                log.info("[UMS] Opening %s (%s)", target["url"], target["topic"])
                page.goto(target["url"], wait_until="domcontentloaded", timeout=25000)
                time.sleep(1.2)
            except Exception as exc:  # noqa: BLE001
                mapped["skipped"].append({**target, "error": type(exc).__name__})
                continue
            if settings.ums_host not in _host(page.url):
                mapped["skipped"].append({**target, "error": "left the UMS host"})
                continue
            visited = build_site_map(self._map_page(page))
            mapped["visited"].append({
                "requested": target["url"],
                "landed": page.url,
                "topic": target["topic"],
                "link_text": target["text"],
                "title": (visited["pages"][0]["title"] if visited["pages"] else None),
                "tables": visited["tables"],
                "panels": visited["panels"][:25],
                "handlers": [h for h in visited["handlers"] if h["topics"]][:25],
                "counts": visited["counts"],
            })

        self._restore(page, origin, [])
        try:
            self._monitor()
        except Exception:  # noqa: BLE001
            pass
        return mapped

    def _menu_openers(self, page: Page) -> list[tuple[Frame, dict[str, Any]]]:
        keywords = settings.ums_menu_keywords_list
        openers: list[tuple[Frame, dict[str, Any]]] = []
        for frame in page.frames:
            try:
                for item in frame.evaluate(MENU_JS, keywords) or []:
                    openers.append((frame, item))
            except Exception:  # noqa: BLE001
                continue
        return openers

    def _try_remembered(
        self, page: Page, remembered: dict[str, Any], attempts: list[str]
    ) -> tuple[Page, dict[str, Any] | None] | None:
        page_url = remembered.get("page_url") or ""
        selector = remembered.get("selector")
        if page_url and settings.ums_host in _host(page_url) and page.url.rstrip("/") != page_url.rstrip("/"):
            attempts.append(f"remembered-goto:{page_url}")
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=20000)
            except Exception:  # noqa: BLE001
                return None
            if self._wait_for_attendance_table(page, quick=True) is not None:
                return page, None
        if not selector:
            return None
        if remembered.get("opener"):
            opened = self._click_openers(page, attempts)
            if opened is not None:
                return opened
        attempts.append(f"remembered-click:{remembered.get('text') or selector}")
        log.info("[UMS] Trying remembered attendance control %s", selector)
        for frame in page.frames:
            try:
                locator = frame.locator(selector).first
                if not locator.count():
                    continue
                locator.click(timeout=6000)
            except Exception:  # noqa: BLE001
                continue
            time.sleep(1.0)
            if self._wait_for_attendance_table(page) is not None:
                return page, {"selector": selector, "text": remembered.get("text")}
        log.info("[UMS] Remembered control no longer works; rediscovering")
        return None

    def _try_candidates(
        self,
        page: Page,
        candidates: list[tuple[Frame, dict[str, Any]]],
        attempts: list[str],
        origin: str,
    ) -> tuple[Page, dict[str, Any] | None] | None:
        tried = 0
        for frame, item in candidates:
            if not item.get("visible"):
                # Hidden: inside a closed modal or a collapsed menu. Playwright
                # cannot click it; opening the menu is what makes it real.
                attempts.append(f"hidden:{(item['text'] or item['href'])[:40]}")
                continue
            if item["score"] < settings.ums_min_candidate_score:
                attempts.append(f"skip:{(item['text'] or item['href'])[:40]}(score={item['score']})")
                continue
            if tried >= settings.ums_max_candidate_clicks:
                break
            tried += 1
            result = self._try_candidate(page, frame, item, attempts, origin)
            if result is not None:
                return result
        return None

    def _try_candidate(
        self,
        page: Page,
        frame: Frame,
        item: dict[str, Any],
        attempts: list[str],
        origin: str,
    ) -> tuple[Page, dict[str, Any] | None] | None:
        """Click one candidate, verify it produced a table, undo it if not."""
        label = (item["text"] or item["href"] or item["selector"])[:60]
        attempts.append(f"click:{label}(score={item['score']})")
        start_url = page.url
        known_pages = {id(p) for p in self._all_pages()}
        try:
            locator = frame.locator(item["selector"]).first
            locator.scroll_into_view_if_needed(timeout=3000)
            locator.click(timeout=6000)
        except Exception as exc:  # noqa: BLE001
            log.info("[UMS] click %r failed: %s", label[:40], type(exc).__name__)
            return None

        try:
            page.wait_for_load_state("domcontentloaded", timeout=12000)
        except Exception:  # noqa: BLE001 - in-page/AJAX updates never fire this
            pass
        time.sleep(0.8)
        log.info("[UMS] After click %r: %s", label[:40], page.url)

        # A popup/new tab on the UMS host.
        for opened in self._all_pages():
            if id(opened) in known_pages:
                continue
            if settings.ums_host in _host(opened.url):
                if self._wait_for_attendance_table(opened) is not None:
                    log.info("[UMS] Attendance opened in a new tab: %s", opened.url)
                    return opened, item
            attempts.append(f"closing-wrong-tab:{_host(opened.url)}")
            try:
                opened.close()
            except Exception:  # noqa: BLE001
                pass

        # Navigated off the UMS host - this was the wrong control (for example an
        # event/QR attendance page on another subdomain). Undo it.
        if not page.is_closed() and settings.ums_host not in _host(page.url):
            wrong = page.url
            attempts.append(f"wrong-host:{_host(wrong)}")
            log.info("[UMS] Candidate navigated off-host to %s - going back", _host(wrong))
            try:
                page.go_back(wait_until="domcontentloaded", timeout=15000)
            except Exception:  # noqa: BLE001
                pass
            if settings.ums_host not in _host(page.url):
                self._restore(page, origin, attempts)
            return None

        if self._wait_for_attendance_table(page) is not None:
            return page, item

        # Right host, wrong page: step back so the next candidate starts clean.
        if page.url.rstrip("/") != start_url.rstrip("/"):
            attempts.append("go-back")
            try:
                page.go_back(wait_until="domcontentloaded", timeout=15000)
                time.sleep(0.5)
            except Exception:  # noqa: BLE001
                self._restore(page, start_url, attempts)
        return None

    # ------------------------------------------------------------- extraction

    def _wait_for_attendance_table(self, page: Page, quick: bool = False) -> tuple[Frame, dict[str, Any]] | None:
        """Poll on an explicit DOM condition, never on networkidle."""
        deadline = time.time() + (4 if quick else settings.ums_table_wait_seconds)
        while True:
            result = self._scan_frames(page)
            if result is not None:
                return result
            if time.time() >= deadline:
                return None
            time.sleep(0.75)

    def _scan_frames(self, page: Page) -> tuple[Frame, dict[str, Any]] | None:
        try:
            frames = list(page.frames)
        except Exception:  # noqa: BLE001
            return None
        self._diag(frame_count=len(frames), frame_urls=[f.url for f in frames][:15])
        log.debug("[UMS] Frame count %d", len(frames))

        scanned = 0
        rejected: tuple[str, dict[str, Any]] | None = None
        for frame in frames:
            for js, kind in ((TABLES_JS, "dom-table"), (GRID_JS, "aria-grid")):
                try:
                    matrices = frame.evaluate(js)
                except Exception:  # noqa: BLE001 - detached/cross-origin frame
                    continue
                for rows in matrices or []:
                    scanned += 1
                    parsed = parse_attendance_rows(rows)
                    if not parsed:
                        continue
                    ok, reason = validate_attendance(parsed)
                    if not ok:
                        # Never discard this silently: a table that parsed but
                        # failed validation is the most useful diagnostic there is.
                        if rejected is None:
                            rejected = (reason, parsed)
                        log.info(
                            "[UMS] Table parsed but rejected by validation: %s (headers=%s)",
                            reason, parsed.get("headers"),
                        )
                        continue
                    parsed["extraction"] = kind
                    self._diag(tables_scanned=scanned)
                    log.info("[UMS] Attendance table candidate found in frame %s (%s)", frame.url, kind)
                    return frame, parsed
        if rejected is not None:
            reason, parsed = rejected
            self._diag(
                tables_scanned=scanned,
                attendance_table_found=True,
                table_headers=parsed.get("headers", []),
                table_sample_rows=[c["course"] for c in parsed["courses"][:3]],
                table_raw_rows=parsed.get("raw_rows", [])[:3],
                courses_parsed=len(parsed["courses"]),
                validated=False,
                validation_error=reason,
            )
        else:
            self._diag(tables_scanned=scanned)
        return None

    # -------------------------------------------------------- other commands

    def _refresh(self) -> dict[str, Any]:
        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable(
                f"No {settings.ums_host} tab is open in the CampusAI browser.", self.diagnostics()
            )
        info = self._classify(page)
        with self._status_lock:
            self._auth_flags = {
                "authenticated": info["authenticated"],
                "verification_required": info["verification_required"],
                "login_page": info["login_page"],
            }
            self._page_info = {"url": info["url"], "title": info["title"]}
        self._diag(authenticated=info["authenticated"], verification_required=info["verification_required"],
                   login_page=info["login_page"], current_url=info["url"], current_title=info["title"])
        if not info["authenticated"]:
            raise UMSLiveAttendanceUnavailable(
                "UMS is not authenticated yet. Finish signing in manually, then press Refresh.",
                self.diagnostics(),
            )
        self._set_state(UMSState.AUTHENTICATED)
        self._auto_capture_attempts = 0
        # Re-read everything else in the background too; the old data keeps
        # answering questions until each item has been read again.
        self._generation += 1
        self._prefetch_errors = {}
        self._capture(page)
        self._item_generation["attendance"] = self._generation
        self._auto_capture_done = True
        return self.status()

    def _navigate(self, target: str) -> dict[str, Any]:
        page = self._pick_ums_page()
        if page is None:
            raise UMSLiveAttendanceUnavailable("The UMS browser has no UMS tab open.", self.diagnostics())
        key = (target or "").strip().lower()
        if key == "attendance":
            self._capture(page)
            return self.status()
        url = target if target.startswith("https://") and settings.ums_host in _host(target) else settings.ums_url
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        self._monitor()
        return self.status()

    def _stop(self) -> dict[str, Any]:
        try:
            if self._browser:
                self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        self._browser = None
        if self._chrome_process and self._chrome_process.poll() is None:
            try:
                self._chrome_process.terminate()
            except Exception:  # noqa: BLE001
                pass
        self._chrome_process = None
        with self._status_lock:
            self._running = False
            self._browser_connected = False
            self._attendance = None
            self._attendance_updated_at = None
            self._panels = {}
            self._prefetch_errors = {}
            self._item_generation = {}
            self._message_searches = {}
            self._prefetch_current = None
            self._was_authenticated = False
            self._auto_capture_done = False
            self._auto_capture_attempts = 0
            self._auth_flags = {"authenticated": False, "verification_required": False, "login_page": False}
            self._page_info = {"url": None, "title": None}
            self._diagnostics = self._blank_diagnostics()
            self._message = "UMS Playwright session stopped."
        self._set_state(UMSState.IDLE)
        return self.status()


ums_playwright = UMSPlaywrightService()

__all__ = ["UMSPlaywrightService", "ums_playwright"]
