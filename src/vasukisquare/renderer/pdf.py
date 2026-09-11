"""PDF rendering engine using Playwright/Chromium for exact A4 physical page generation."""

import asyncio
from pathlib import Path
from typing import Optional, Union
from vasukisquare.config import Settings, get_settings


class PdfRenderer:
    """Renders HTML content or HTML files into deterministic A4 PDFs using Playwright."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    async def render_html_to_pdf(
        self,
        html_content: str,
        output_path: Union[str, Path],
    ) -> Path:
        """Convert HTML string to an A4 PDF document using Playwright."""
        from playwright.async_api import async_playwright

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.settings.chromium_headless)
            page = await browser.new_page()
            
            await page.set_content(html_content, wait_until="networkidle")
            
            await page.pdf(
                path=str(out_path),
                width="210mm",
                height="297mm",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            await browser.close()

        return out_path

    def render_sync(self, html_content: str, output_path: Union[str, Path]) -> Path:
        """Synchronous wrapper for rendering HTML to PDF."""
        return asyncio.run(self.render_html_to_pdf(html_content, output_path))

