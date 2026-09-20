"""Webpage fetching and clean text extraction tool."""

import re
import logging
from typing import Optional
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from vasukisquare.research.models import SourceDocument, SourceType
from vasukisquare.tools.base import BaseTool

logger = logging.getLogger(__name__)


class FetchParams(BaseModel):
    """Parameters for fetching a single webpage."""

    url: str
    source_type: SourceType = SourceType.WEBPAGE


from vasukisquare.research.sanitization import clean_source_title, sanitize_source_text


def clean_html_content(raw_html: str) -> tuple[str, str]:
    """Strip scripts, styles, boilerplate, and tags, returning (title, clean_text)."""
    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    raw_title = title_match.group(1).strip() if title_match else "Untitled Webpage"
    title = clean_source_title(raw_title)

    # Remove script and style tags
    clean = re.sub(r"<(script|style|nav|header|footer|aside|form|noscript)[^>]*>.*?</\1>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    # Sanitize general web content
    clean = sanitize_source_text(clean)
    return title, clean


class WebpageFetcherTool(BaseTool[FetchParams, Optional[SourceDocument]]):
    """Fetches full webpage HTML and extracts structured content."""

    def __init__(self, timeout_seconds: float = 15.0):
        super().__init__(
            name="webpage_fetcher",
            description="Fetches full webpage contents and extracts cleaned readable text.",
            timeout_seconds=timeout_seconds,
        )

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def _run(self, params: FetchParams) -> Optional[SourceDocument]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
                resp = await client.get(params.url)
                resp.raise_for_status()
                raw_html = resp.text

            title, text = clean_html_content(raw_html)
            if not text:
                logger.info(f"[FETCH] url={params.url} status={resp.status_code} extracted_chars=0 (empty)")
                return None

            logger.info(f"[FETCH] url={params.url} status={resp.status_code} extracted_chars={len(text)}")
            return SourceDocument(
                url=params.url,
                title=title,
                source_type=params.source_type,
                extracted_text=text[:10000],  # Limit to 10k chars per document
                summary=text[:300] + "..." if len(text) > 300 else text,
            )
        except Exception as e:
            logger.warning(f"[FETCH:FAILED] url={params.url} error={e}")
            return None

