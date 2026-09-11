"""Regression and unit tests for PdfRenderer API contract, error handling, and page count budgeting."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from vasukisquare.config import Settings
from vasukisquare.renderer.pdf import PdfRenderer, PDFExportError
from vasukisquare.agents.editorial import EditorialPlannerAgent, BookIntent


@pytest.mark.asyncio
async def test_pdf_renderer_render_pdf_from_html_api_contract(tmp_path: Path):
    """Verify that PdfRenderer exposes render_pdf_from_html and creates a valid non-empty PDF file."""
    output_pdf = tmp_path / "test_book.pdf"
    simple_html = """<!doctype html>
<html>
<head><title>Test</title></head>
<body>
<h1>VasukiSquare PDF Test</h1>
<p>Hello world from deterministic A4 renderer.</p>
</body>
</html>"""

    renderer = PdfRenderer()

    # Verify method exists and is callable without AttributeError
    assert hasattr(renderer, "render_pdf_from_html")
    assert callable(renderer.render_pdf_from_html)

    # Mock Playwright for fast unit test
    with patch("playwright.async_api.async_playwright") as mock_playwright:
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        # Simulate creating the PDF file
        async def fake_pdf(path, **kwargs):
            Path(path).write_bytes(b"%PDF-1.4 mock pdf content bytes")

        mock_page.pdf = AsyncMock(side_effect=fake_pdf)
        mock_page.set_content = AsyncMock()
        mock_page.evaluate = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        # Context manager mock
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_p)
        cm.__aexit__ = AsyncMock(return_value=None)
        mock_playwright.return_value = cm

        res = await renderer.render_pdf_from_html(simple_html, output_pdf)
        assert res == output_pdf
        assert output_pdf.exists()
        assert output_pdf.stat().st_size > 0


@pytest.mark.asyncio
async def test_pdf_renderer_error_handling(tmp_path: Path):
    """Verify that PdfRenderer raises PDFExportError on failure."""
    renderer = PdfRenderer()
    output_pdf = tmp_path / "failed.pdf"

    with patch("playwright.async_api.async_playwright", side_effect=Exception("Chromium crashed")):
        with pytest.raises(PDFExportError) as exc:
            await renderer.render_pdf_from_html("<html></html>", output_pdf)
        assert "Failed to export assembled HTML" in str(exc.value)


@pytest.mark.asyncio
async def test_editorial_planner_page_budgeting_for_10_pages():
    """Verify that a 10-page book request plans exactly ~10 physical pages instead of 27."""
    settings = Settings(app_env="test", vasukisquare_mock_mode=True)
    agent = EditorialPlannerAgent(settings)

    intent = BookIntent(
        topic="LioranDB for Noobs",
        target_audience="Beginners",
        technical_depth="introductory",
        book_type="beginner_guide",
        tone="educational",
        chapter_count=2,
    )

    plan = await agent.generate_book_plan(
        prompt="LioranDB for Noobs: From Zero Knowledge to Building Real Apps",
        intent=intent,
        target_pages=10,
    )

    assert plan.total_pages == 10
    assert len(plan.all_planned_pages) == 10
    # 2 chapters planned for 10-page book
    assert len(plan.chapters) == 2


@pytest.mark.asyncio
async def test_editorial_planner_page_budgeting_for_20_and_80_pages():
    """Verify adaptive chapter and page budgeting for 20 and 80 page targets."""
    settings = Settings(app_env="test", vasukisquare_mock_mode=True)
    agent = EditorialPlannerAgent(settings)

    # 20 Pages
    plan_20 = await agent.generate_book_plan(
        prompt="Modern Key-Value Stores",
        target_pages=20,
    )
    assert abs(plan_20.total_pages - 20) <= 1
    assert len(plan_20.chapters) == 3

    # 80 Pages
    plan_80 = await agent.generate_book_plan(
        prompt="Modern Key-Value Stores",
        target_pages=80,
    )
    assert abs(plan_80.total_pages - 80) <= 2
    assert len(plan_80.chapters) == 8

