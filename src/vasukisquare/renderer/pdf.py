"""PDF rendering engine using Playwright/Chromium for exact A4 physical page generation."""

import asyncio
from pathlib import Path
from typing import List, Optional, Union
from vasukisquare.config import Settings, get_settings
from vasukisquare.book.models import Page
from vasukisquare.renderer.html import HtmlPageRenderer


class PDFExportError(Exception):
    """Raised when HTML to PDF export fails."""
    pass


class PdfRenderer:
    """Renders HTML content or HTML files into deterministic A4 PDFs using Playwright."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        html_renderer: Optional[HtmlPageRenderer] = None,
    ):
        self.settings = settings or get_settings()
        self.html_renderer = html_renderer or HtmlPageRenderer()

    async def render_pdf_from_html(
        self,
        html_content: str,
        output_path: Union[str, Path],
    ) -> Path:
        """Canonical public API: Convert assembled HTML document string to an A4 PDF."""
        return await self.render_html_to_pdf(html_content, output_path)

    async def render_html_to_pdf(
        self,
        html_content: str,
        output_path: Union[str, Path],
    ) -> Path:
        """Convert HTML string to an A4 PDF document using Playwright Chromium."""
        from playwright.async_api import async_playwright

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.settings.chromium_headless)
                page = await browser.new_page(viewport={"width": 794, "height": 1123})
                
                await page.set_content(html_content, wait_until="load")
                
                # 1. Wait for web fonts to load completely
                try:
                    await page.evaluate("() => document.fonts.ready")
                except Exception:
                    pass

                # 2. Wait for all raster images to load completely and verify dimensions
                try:
                    await page.evaluate("""
                    () => Promise.all(
                        Array.from(document.images).map(img => {
                            if (img.complete) {
                                return img.naturalWidth !== 0 ? Promise.resolve() : Promise.reject(new Error('Image failed to load: ' + img.src));
                            }
                            return new Promise((resolve, reject) => {
                                img.onload = () => resolve();
                                img.onerror = () => reject(new Error('Image load failed: ' + img.src));
                            });
                        })
                    )
                    """)
                except Exception:
                    pass

                await page.pdf(
                    path=str(out_path),
                    format="A4",
                    print_background=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                )
                await browser.close()
                return out_path

        except Exception as e:
            raise PDFExportError(
                f"Failed to export assembled HTML to {out_path} using Playwright: {e}"
            ) from e

    async def render_book_to_pdf(
        self,
        pages: List[Page],
        output_path: Union[str, Path],
        book_title: str = "VasukiSquare Book",
        book_topic: str = "",
    ) -> Path:
        """Render a list of Page models directly into an assembled A4 PDF document."""
        html_content = self.html_renderer.render_book(
            pages=pages,
            book_title=book_title,
            book_topic=book_topic,
        )
        return await self.render_html_to_pdf(html_content, output_path)

    def render_sync(self, html_content: str, output_path: Union[str, Path]) -> Path:
        """Synchronous wrapper for rendering HTML to PDF."""
        return asyncio.run(self.render_html_to_pdf(html_content, output_path))

