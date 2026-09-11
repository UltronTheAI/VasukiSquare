"""Wikipedia orientation and background information retrieval tool."""

import logging
from typing import List, Optional
import httpx
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from vasukisquare.research.models import SourceDocument, SourceType
from vasukisquare.tools.base import BaseTool

logger = logging.getLogger(__name__)


class WikipediaParams(BaseModel):
    """Parameters for Wikipedia search."""

    query: str
    max_results: int = Field(default=3, ge=1, le=5)


class WikipediaTool(BaseTool[WikipediaParams, List[SourceDocument]]):
    """Retrieves high-level orientation articles from Wikipedia."""

    def __init__(self, timeout_seconds: float = 12.0):
        super().__init__(
            name="wikipedia_search",
            description="Searches Wikipedia for conceptual orientation and taxonomy.",
            timeout_seconds=timeout_seconds,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def _run(self, params: WikipediaParams) -> List[SourceDocument]:
        search_url = "https://en.wikipedia.org/w/api.php"
        headers = {"User-Agent": "VasukiSquare/0.1.0 (https://vasukisquare.org; contact@vasukisquare.org)"}
        
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            resp = await client.get(
                search_url,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": params.query,
                    "format": "json",
                    "srlimit": params.max_results,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("query", {}).get("search", [])
        documents: List[SourceDocument] = []

        for item in results:
            title = item.get("title", "")
            page_id = item.get("pageid", "")
            snippet = item.get("snippet", "").replace('<span class="searchmatch">', "").replace("</span>", "")
            clean_title = title.replace(" ", "_")
            article_url = f"https://en.wikipedia.org/wiki/{clean_title}"

            documents.append(
                SourceDocument(
                    url=article_url,
                    title=f"{title} - Wikipedia",
                    publisher="Wikipedia",
                    domain="en.wikipedia.org",
                    source_type=SourceType.WIKIPEDIA,
                    extracted_text=snippet,
                    summary=snippet,
                    reliability_score=0.50,
                    metadata={"page_id": page_id},
                )
            )

        return documents

