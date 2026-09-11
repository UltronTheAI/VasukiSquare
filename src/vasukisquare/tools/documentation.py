"""Developer documentation and technical blog extraction tool."""

import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from vasukisquare.research.models import SourceDocument, SourceType
from vasukisquare.tools.base import BaseTool
from vasukisquare.tools.fetcher import WebpageFetcherTool, FetchParams

logger = logging.getLogger(__name__)


class DocScraperParams(BaseModel):
    """Parameters for scraping documentation or technical blog URLs."""

    urls: List[str]
    is_official_doc: bool = True


class DocScraperTool(BaseTool[DocScraperParams, List[SourceDocument]]):
    """Scrapes official developer documentation and technical blogs with high reliability scoring."""

    def __init__(self, timeout_seconds: float = 20.0):
        super().__init__(
            name="doc_scraper",
            description="Fetches developer documentation and technical blog articles.",
            timeout_seconds=timeout_seconds,
        )
        self.fetcher = WebpageFetcherTool(timeout_seconds=10.0)

    async def _run(self, params: DocScraperParams) -> List[SourceDocument]:
        documents: List[SourceDocument] = []
        source_type = SourceType.DOCUMENTATION if params.is_official_doc else SourceType.BLOG
        default_score = 0.95 if params.is_official_doc else 0.80

        for url in params.urls:
            try:
                doc = await self.fetcher.execute(FetchParams(url=url, source_type=source_type))
                if doc:
                    doc.reliability_score = default_score
                    documents.append(doc)
            except Exception as e:
                logger.warning(f"Failed to scrape documentation url {url}: {e}")

        return documents

