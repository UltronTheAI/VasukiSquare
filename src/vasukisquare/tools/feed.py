"""RSS and news feed retrieval tool."""

import xml.etree.ElementTree as ET
import logging
from typing import List
import httpx
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from vasukisquare.research.models import SourceDocument, SourceType
from vasukisquare.tools.base import BaseTool

logger = logging.getLogger(__name__)


class FeedParams(BaseModel):
    """Parameters for fetching an RSS feed."""

    feed_url: str
    max_entries: int = Field(default=5, ge=1, le=20)


class RssNewsTool(BaseTool[FeedParams, List[SourceDocument]]):
    """Fetches and parses RSS/Atom feeds for industry news and announcements."""

    def __init__(self, timeout_seconds: float = 12.0):
        super().__init__(
            name="rss_news_fetcher",
            description="Parses RSS and news feeds for domain developments.",
            timeout_seconds=timeout_seconds,
        )

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def _run(self, params: FeedParams) -> List[SourceDocument]:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(params.feed_url)
            resp.raise_for_status()
            xml_data = resp.text

        documents: List[SourceDocument] = []
        try:
            root = ET.fromstring(xml_data)
            # Support RSS 2.0 channel -> item
            items = root.findall(".//item")
            if not items:
                # Support Atom feed -> entry
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for item in items[:params.max_entries]:
                title_elem = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
                link_elem = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
                desc_elem = (
                    item.find("description")
                    or item.find("{http://www.w3.org/2005/Atom}summary")
                    or item.find("{http://www.w3.org/2005/Atom}content")
                )

                title = title_elem.text.strip() if title_elem is not None and title_elem.text else "News Entry"
                link = ""
                if link_elem is not None:
                    link = link_elem.text.strip() if link_elem.text else link_elem.attrib.get("href", "")
                
                desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

                if link:
                    documents.append(
                        SourceDocument(
                            url=link,
                            title=title,
                            source_type=SourceType.NEWS,
                            extracted_text=desc,
                            summary=desc[:200],
                            reliability_score=0.70,
                        )
                    )
        except Exception as e:
            logger.warning(f"Error parsing feed {params.feed_url}: {e}")

        return documents

