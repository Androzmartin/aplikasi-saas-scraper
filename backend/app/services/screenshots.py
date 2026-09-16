"""Capture desktop and mobile screenshots of a target website.

Playwright is an optional dependency: it needs a browser binary that not every
deployment wants to ship. When it is missing or the capture fails, callers get a
clear reason back and the surrounding job carries on — a screenshot is never
allowed to fail a scrape.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.config import settings
from app.services.storage import storage
from app.services.urls import normalize_url, InvalidUrlError

logger = logging.getLogger(__name__)

# Viewports chosen to match what a client sees when you present before/after.
VIEWPORTS: Dict[str, Dict[str, int]] = {
    "desktop": {"width": 1440, "height": 900},
    "mobile": {"width": 390, "height": 844},
}

MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


class ScreenshotUnavailable(Exception):
    """Playwright (or its browser) is not installed in this deployment."""


@dataclass
class ScreenshotResult:
    keys: Dict[str, str] = field(default_factory=dict)
    failures: Dict[str, str] = field(default_factory=dict)

    @property
    def any_captured(self) -> bool:
        return bool(self.keys)


def storage_key(lead_id: str, variant: str, version: int = 1) -> str:
    return f"screenshots/{lead_id}/v{version}/{variant}.png"


def _load_playwright():
    try:
        from playwright.async_api import async_playwright  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on deployment
        raise ScreenshotUnavailable(
            "Playwright belum terpasang. Jalankan: pip install playwright && playwright install chromium"
        ) from exc
    return async_playwright


async def capture(
    url: str,
    lead_id: str,
    version: int = 1,
    variants: Optional[List[str]] = None,
) -> ScreenshotResult:
    """Screenshot the URL at each requested viewport and store the PNGs."""
    try:
        url = normalize_url(url)
    except InvalidUrlError as exc:
        raise ValueError(str(exc)) from exc

    wanted = [v for v in (variants or list(VIEWPORTS)) if v in VIEWPORTS]
    if not wanted:
        raise ValueError("Tidak ada variant screenshot yang valid")

    async_playwright = _load_playwright()
    result = ScreenshotResult()

    async with async_playwright() as playwright:
        launch_kwargs: Dict[str, object] = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if settings.screenshot_browser_path:
            launch_kwargs["executable_path"] = settings.screenshot_browser_path
        try:
            browser = await playwright.chromium.launch(**launch_kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as unavailable
            raise ScreenshotUnavailable(f"Browser tidak bisa dijalankan: {exc}") from exc

        try:
            for variant in wanted:
                try:
                    png = await _capture_one(browser, url, variant)
                    key = storage_key(lead_id, variant, version)
                    storage.put_bytes(key, png)
                    result.keys[variant] = key
                except Exception as exc:  # noqa: BLE001 - one viewport must not sink the other
                    logger.warning("Screenshot %s for %s failed: %s", variant, url, exc)
                    result.failures[variant] = f"{exc.__class__.__name__}: {exc}"
        finally:
            await browser.close()

    return result


async def _capture_one(browser, url: str, variant: str) -> bytes:
    viewport = VIEWPORTS[variant]
    context_kwargs: Dict[str, object] = {
        "viewport": viewport,
        "user_agent": MOBILE_USER_AGENT if variant == "mobile" else settings.scraper_user_agent,
        "locale": "id-ID",
    }
    if variant == "mobile":
        context_kwargs["is_mobile"] = True
        context_kwargs["has_touch"] = True
        context_kwargs["device_scale_factor"] = 2

    context = await browser.new_context(**context_kwargs)
    try:
        page = await context.new_page()
        timeout_ms = int(settings.screenshot_timeout_seconds * 1000)
        page.set_default_timeout(timeout_ms)
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        # Give late-loading heroes and webfonts a moment, but never hang on
        # sites that keep a socket open forever.
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:  # noqa: BLE001 - best effort only
            pass
        await asyncio.sleep(0.4)
        return await page.screenshot(full_page=settings.screenshot_full_page, type="png")
    finally:
        await context.close()
