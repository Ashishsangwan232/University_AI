"""Crawl the public college website into readable pages.

The first version fetched a page, called ``soup.get_text()`` on the whole
document and stored that. Every chunk therefore carried the navigation menu, the
cookie banner and the footer, so a search for "hostel fee" matched the footer of
two hundred pages equally well. This version:

  * obeys robots.txt and waits between requests - it is someone else's server;
  * skips URLs that are not pages (PDFs, images, logins, search results);
  * extracts the main content and drops the chrome around it;
  * removes lines that repeat across many pages, which is the menu and footer,
    identified from the crawl itself rather than from a guessed selector;
  * stops on a page budget, a depth budget and a wall-clock budget.

Nothing here needs a database or a model, so it can be tested offline.
"""
from __future__ import annotations

import logging
import re
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from app.core.config import settings

log = logging.getLogger("campusai.rag")

#: Not pages. Fetching these wastes the budget and stores nothing readable.
SKIP_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
    ".mp4", ".mp3", ".avi", ".mov", ".wmv", ".webm", ".css", ".js", ".json",
    ".xml", ".rss", ".txt", ".woff", ".woff2", ".ttf", ".eot", ".apk", ".exe",
)

#: Paths that are never useful knowledge: sessions, carts, endless calendars.
SKIP_PATTERNS = re.compile(
    r"/(login|logout|signin|sign-in|signup|register|cart|checkout|search|"
    r"wp-admin|wp-login|admin|feed|rss|print|share|calendar|tag|author|"
    r"page/\d+|comment)(/|$|\?)",
    re.I,
)

#: Query parameters that only track a visitor; dropping them stops the same
#: page being crawled a dozen times under a dozen URLs.
TRACKING_PARAMS = re.compile(
    r"^(utm_|fbclid|gclid|msclkid|mc_cid|mc_eid|ref|source|campaign)", re.I
)

#: Structural elements that are chrome, not content.
CHROME_TAGS = ("script", "style", "noscript", "svg", "iframe", "form",
               "nav", "header", "footer", "aside", "button")
#: And chrome that is only identifiable by its class or id.
CHROME_HINTS = re.compile(
    r"(nav|menu|header|footer|sidebar|breadcrumb|cookie|consent|popup|modal|"
    r"banner|social|share|subscribe|newsletter|advert|widget|topbar|offcanvas)",
    re.I,
)
#: Where the real content usually lives, best first.
MAIN_SELECTORS = ("main", "article", "[role=main]", "#main", "#content",
                  ".main-content", ".content", "#primary")

WHITESPACE = re.compile(r"[ \t\xa0]+")
BLANK_LINES = re.compile(r"\n{3,}")


@dataclass
class CrawledPage:
    url: str
    title: str
    text: str
    description: str = ""
    headings: list[str] = field(default_factory=list)
    depth: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url, "title": self.title, "description": self.description,
            "headings": self.headings, "depth": self.depth, "characters": len(self.text),
        }


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------
def normalise_url(url: str) -> str:
    """One canonical spelling per page.

    Drops the fragment and tracking parameters, lowercases the host, and strips
    a trailing slash - so ``/admissions``, ``/admissions/`` and
    ``/Admissions/?utm_source=x#top`` are all one URL and are fetched once.
    """
    url, _ = urldefrag((url or "").strip())
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    query = "&".join(
        part for part in parsed.query.split("&")
        if part and not TRACKING_PARAMS.match(part.split("=")[0])
    )
    path = re.sub(r"/{2,}", "/", parsed.path) or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", query, ""))


def same_site(url: str, root_host: str) -> bool:
    """True for the site itself and its subdomains, false for everywhere else."""
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    bare = root_host[4:] if root_host.startswith("www.") else root_host
    return host == root_host or host == bare or host.endswith("." + bare)


def is_crawlable(url: str, root_host: str) -> bool:
    """Is this worth spending one of the budgeted fetches on?"""
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if not same_site(url, root_host):
        return False
    path = parsed.path.lower()
    if path.endswith(SKIP_EXTENSIONS):
        return False
    if SKIP_PATTERNS.search(path):
        return False
    return True


# ---------------------------------------------------------------------------
# Page text
# ---------------------------------------------------------------------------
def extract_page(html: str, url: str) -> tuple[str, str, str, list[str]]:
    """Title, description, main text and headings - without the chrome.

    Returns ``("", "", "", [])`` when the page has no readable body.
    """
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    description = (meta.get("content") or "").strip() if meta else ""

    for element in soup(list(CHROME_TAGS)):
        element.decompose()
    for element in soup.find_all(attrs={"class": CHROME_HINTS}):
        element.decompose()
    for element in soup.find_all(attrs={"id": CHROME_HINTS}):
        element.decompose()

    body = None
    for selector in MAIN_SELECTORS:
        found = soup.select_one(selector)
        # A "main" element with almost nothing in it is a layout wrapper, not
        # the content; fall through to the next candidate.
        if found and len(found.get_text(" ", strip=True)) > 200:
            body = found
            break
    body = body or soup.body or soup

    headings = [
        WHITESPACE.sub(" ", tag.get_text(" ", strip=True))
        for tag in body.find_all(("h1", "h2", "h3"))
    ]
    headings = [h for h in headings if 2 < len(h) <= 120][:30]

    text = body.get_text("\n", strip=True)
    text = WHITESPACE.sub(" ", text)
    text = BLANK_LINES.sub("\n\n", text).strip()
    return title[:300], description[:500], text, headings


def strip_boilerplate(pages: list[CrawledPage], threshold: float = 0.4) -> None:
    """Remove lines that appear on a large share of pages, in place.

    The menu and footer are whatever text repeats everywhere. Measuring that
    across the crawl is more reliable than guessing a CSS selector per site, and
    it costs one pass over the pages.
    """
    if len(pages) < 5:
        return
    counts: Counter[str] = Counter()
    for page in pages:
        for line in {line.strip() for line in page.text.split("\n") if line.strip()}:
            if len(line) <= 120:  # only short lines; a repeated paragraph is real content
                counts[line] += 1

    limit = max(3, int(len(pages) * threshold))
    common = {line for line, count in counts.items() if count >= limit}
    if not common:
        return

    removed = 0
    for page in pages:
        kept = [line for line in page.text.split("\n") if line.strip() not in common]
        removed += len(page.text.split("\n")) - len(kept)
        page.text = BLANK_LINES.sub("\n\n", "\n".join(kept)).strip()
    log.info("[RAG] Boilerplate: dropped %d repeated line(s) from %d page(s)", removed, len(pages))


# ---------------------------------------------------------------------------
# The crawl
# ---------------------------------------------------------------------------
def _robots_for(session: requests.Session, start_url: str) -> RobotFileParser | None:
    parsed = urlparse(start_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    try:
        response = session.get(robots_url, timeout=10)
        if response.status_code >= 400:
            return None
        parser.parse(response.text.splitlines())
        log.info("[RAG] robots.txt loaded from %s", robots_url)
        return parser
    except requests.RequestException:
        # No robots.txt, or it could not be fetched. Crawl politely anyway.
        return None


def crawl_website(
    start_url: str,
    max_pages: int | None = None,
    max_depth: int | None = None,
    on_page: Callable[[CrawledPage], None] | None = None,
) -> list[CrawledPage]:
    """Breadth-first crawl of one site, within every configured budget."""
    parsed = urlparse(start_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("start_url must be a valid http(s) URL")

    max_pages = max_pages or settings.rag_crawl_max_pages
    max_depth = max_depth if max_depth is not None else settings.rag_crawl_max_depth
    root_host = parsed.netloc.lower()
    deadline = time.time() + settings.rag_crawl_time_budget_seconds

    session = requests.Session()
    session.headers.update({"User-Agent": settings.rag_user_agent})
    robots = _robots_for(session, start_url) if settings.rag_respect_robots else None

    start = normalise_url(start_url)
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    queued: set[str] = {start}
    visited: set[str] = set()
    pages: list[CrawledPage] = []
    skipped_by_robots = 0

    while queue and len(pages) < max_pages:
        if time.time() > deadline:
            log.info("[RAG] Crawl stopped: time budget reached after %d page(s)", len(pages))
            break

        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if robots and not robots.can_fetch(settings.rag_user_agent, url):
            skipped_by_robots += 1
            continue

        try:
            response = session.get(url, timeout=settings.rag_crawl_timeout_seconds)
        except requests.RequestException as exc:
            log.debug("[RAG] %s failed: %s", url, exc)
            continue
        finally:
            time.sleep(settings.rag_crawl_delay_seconds)

        if response.status_code >= 400:
            continue
        if "text/html" not in response.headers.get("content-type", "").lower():
            continue

        title, description, text, headings = extract_page(response.text, url)
        if len(text) >= settings.rag_min_page_characters:
            page = CrawledPage(url=url, title=title or url, text=text,
                               description=description, headings=headings, depth=depth)
            pages.append(page)
            if on_page:
                on_page(page)
            log.info("[RAG] %d/%d  d%d  %s", len(pages), max_pages, depth, url[:90])

        if depth >= max_depth:
            continue
        for link in _links(response.text, url, root_host):
            if link not in visited and link not in queued:
                queued.add(link)
                queue.append((link, depth + 1))

    if skipped_by_robots:
        log.info("[RAG] robots.txt disallowed %d URL(s)", skipped_by_robots)
    strip_boilerplate(pages)
    return [page for page in pages if len(page.text) >= settings.rag_min_page_characters]


def _links(html: str, base_url: str, root_host: str) -> Iterable[str]:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        candidate = normalise_url(urljoin(base_url, href))
        if is_crawlable(candidate, root_host):
            yield candidate
