"""Render HTML to PDF using the same optional Playwright browser as screenshots."""
from __future__ import annotations

import logging
from typing import Dict

from app.config import settings
from app.services.screenshots import ScreenshotUnavailable, _load_playwright

logger = logging.getLogger(__name__)


async def html_to_pdf(html: str) -> bytes:
    """Render a self-contained HTML document to A4 PDF bytes.

    Raises ScreenshotUnavailable when Playwright or its browser is missing, so
    callers can fall back to handing the user printable HTML instead.
    """
    async_playwright = _load_playwright()

    async with async_playwright() as playwright:
        launch_kwargs: Dict[str, object] = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if settings.screenshot_browser_path:
            launch_kwargs["executable_path"] = settings.screenshot_browser_path
        try:
            browser = await playwright.chromium.launch(**launch_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise ScreenshotUnavailable(f"Browser tidak bisa dijalankan: {exc}") from exc

        try:
            page = await browser.new_page()
            # The document inlines its own CSS, so nothing needs the network.
            await page.set_content(html, wait_until="load")
            return await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "14mm", "bottom": "14mm", "left": "14mm", "right": "14mm"},
            )
        finally:
            await browser.close()
