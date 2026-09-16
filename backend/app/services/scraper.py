"""Public-page crawler with robots.txt compliance and per-domain rate limiting.

Scope is deliberately narrow: fetch the submitted page plus a few likely
contact/about pages on the same site, then hand the HTML to the extractor.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.services.extractor import extract_from_page, merge_page_results
from app.services.urls import same_site

# Paths that most often carry the contact details we are after.
_PRIORITY_HINTS = (
    "kontak", "contact", "hubungi", "tentang", "about", "profil", "profile",
    "alamat", "lokasi", "location", "cabang",
)

_SKIP_EXT = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".rar",
    ".mp4", ".mp3", ".doc", ".docx", ".xls", ".xlsx", ".css", ".js", ".ico",
)

MAX_HTML_BYTES = 3_000_000


class ScrapeError(Exception):
    """Raised when a target site cannot be crawled."""


@dataclass
class CrawlResult:
    root_html: str = ""
    pages: List[Dict] = field(default_factory=list)
    fetched_urls: List[str] = field(default_factory=list)
    blocked_by_robots: bool = False


class DomainRateLimiter:
    """Serialises requests per host and enforces a minimum delay between them."""

    def __init__(self, delay_seconds: float) -> None:
        self.delay = delay_seconds
        self._locks: Dict[str, asyncio.Lock] = {}
        self._last: Dict[str, float] = {}
        self._guard = asyncio.Lock()

    async def acquire(self, host: str) -> None:
        async with self._guard:
            lock = self._locks.setdefault(host, asyncio.Lock())
        await lock.acquire()
        elapsed = time.monotonic() - self._last.get(host, 0.0)
        if elapsed < self.delay:
            await asyncio.sleep(self.delay - elapsed)

    def release(self, host: str) -> None:
        self._last[host] = time.monotonic()
        lock = self._locks.get(host)
        if lock and lock.locked():
            lock.release()


rate_limiter = DomainRateLimiter(settings.scraper_delay_seconds)
_robots_cache: Dict[str, Optional[RobotFileParser]] = {}


async def _robots_allows(client: httpx.AsyncClient, url: str) -> bool:
    if not settings.scraper_respect_robots:
        return True
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _robots_cache:
        parser: Optional[RobotFileParser] = None
        try:
            response = await client.get(f"{origin}/robots.txt", timeout=10.0)
            if response.status_code == 200 and len(response.content) < 512_000:
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
        except (httpx.HTTPError, UnicodeDecodeError):
            parser = None  # Unreachable robots.txt is treated as "allowed".
        _robots_cache[origin] = parser

    parser = _robots_cache[origin]
    if parser is None:
        return True
    return parser.can_fetch(settings.scraper_user_agent, url)


async def fetch_page(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Fetch one page as HTML, honouring robots.txt and the per-domain delay."""
    host = urlparse(url).hostname or ""
    await rate_limiter.acquire(host)
    try:
        if not await _robots_allows(client, url):
            raise ScrapeError(f"Diblokir oleh robots.txt: {url}")
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return None
        if len(response.content) > MAX_HTML_BYTES:
            return response.text[:MAX_HTML_BYTES]
        return response.text
    finally:
        rate_limiter.release(host)


def pick_internal_links(html: str, base_url: str, limit: int) -> List[str]:
    """Choose same-site links most likely to hold contact information."""
    soup = BeautifulSoup(html, "lxml")
    scored: List[Tuple[int, str]] = []
    seen: Set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        absolute = parsed._replace(fragment="").geturl()
        key = absolute.rstrip("/").lower()
        if key in seen or key == base_url.rstrip("/").lower():
            continue
        if not same_site(absolute, base_url):
            continue
        if parsed.path.lower().endswith(_SKIP_EXT):
            continue

        haystack = f"{parsed.path.lower()} {anchor.get_text(' ', strip=True).lower()}"
        score = sum(3 for hint in _PRIORITY_HINTS if hint in haystack)
        if score == 0:
            continue
        seen.add(key)
        scored.append((score, absolute))

    scored.sort(key=lambda item: (-item[0], len(item[1])))
    return [url for _, url in scored[:limit]]


async def crawl_site(url: str, max_pages: Optional[int] = None) -> CrawlResult:
    """Crawl the submitted URL plus prioritised contact/about pages."""
    max_pages = max_pages or settings.scraper_max_pages_per_site
    result = CrawlResult()
    headers = {
        "User-Agent": settings.scraper_user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    }

    async with httpx.AsyncClient(
        headers=headers,
        timeout=settings.scraper_timeout_seconds,
        follow_redirects=True,
        max_redirects=5,
    ) as client:
        try:
            root_html = await fetch_page(client, url)
        except ScrapeError as exc:
            result.blocked_by_robots = True
            raise ScrapeError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise ScrapeError(
                f"HTTP {exc.response.status_code} saat mengakses {url}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ScrapeError(f"Gagal mengakses {url}: {exc.__class__.__name__}") from exc

        if not root_html:
            raise ScrapeError(f"{url} tidak mengembalikan dokumen HTML")

        result.root_html = root_html
        result.fetched_urls.append(url)
        result.pages.append(extract_from_page(root_html, url))

        for link in pick_internal_links(root_html, url, max_pages - 1):
            try:
                page_html = await fetch_page(client, link)
            except (ScrapeError, httpx.HTTPError):
                continue  # A secondary page failing must not fail the whole job.
            if not page_html:
                continue
            result.fetched_urls.append(link)
            result.pages.append(extract_from_page(page_html, link))

    return result


async def scrape_url(url: str) -> Tuple[Dict, CrawlResult]:
    """Crawl a site and return the merged contact record plus the raw crawl."""
    crawl = await crawl_site(url)
    contact = merge_page_results(crawl.pages)
    data = contact.to_dict()
    data["website_url"] = url
    return data, crawl
