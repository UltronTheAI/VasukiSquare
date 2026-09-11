"""Web search tool supporting multiple swappable search providers."""

import logging
from typing import List, Optional
import httpx
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from vasukisquare.research.models import SourceDocument, SourceType
from vasukisquare.tools.base import BaseTool, SearchProvider

logger = logging.getLogger(__name__)


class SearchParams(BaseModel):
    """Parameters for web search query."""

    query: str
    max_results: int = Field(default=5, ge=1, le=20)


class MockSearchProvider(SearchProvider):
    """Mock search provider for testing and deterministic offline execution."""

    def __init__(self, predefined_results: Optional[List[SourceDocument]] = None):
        self.predefined_results = predefined_results or []

    async def search(self, query: str, max_results: int = 5) -> List[SourceDocument]:
        if self.predefined_results:
            return self.predefined_results[:max_results]
        
        # Derive clean slug and clean title from query
        clean_words = [w for w in query.replace(":", " ").replace(",", " ").split() if w.lower() not in ("overview", "definition", "fundamentals", "guide", "in-depth")]
        slug = "-".join(clean_words[:6]).lower() if clean_words else "technical-specification"
        title_text = " ".join(clean_words[:6]).title() if clean_words else "System Architecture & Engineering Specification"

        return [
            SourceDocument(
                url=f"https://acm.org/publications/proceedings/{slug}",
                title=f"{title_text} - Primary Specification",
                source_type=SourceType.DOCUMENTATION,
                extracted_text=f"Formal architectural specification and empirical evaluation of {query}.",
                summary=f"Technical specification and performance analysis of {query}.",
            )
        ]


class TavilySearchProvider(SearchProvider):
    """Tavily search provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = "https://api.tavily.com/search"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def search(self, query: str, max_results: int = 5) -> List[SourceDocument]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                self.endpoint,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_raw_content": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        documents = []
        for item in data.get("results", []):
            documents.append(
                SourceDocument(
                    url=item.get("url", ""),
                    title=item.get("title", "Untitled"),
                    source_type=SourceType.WEB,
                    extracted_text=item.get("content", ""),
                    summary=item.get("snippet", ""),
                    reliability_score=0.7,
                )
            )
        return documents


class SerperSearchProvider(SearchProvider):
    """Serper Google search provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = "https://google.serper.dev/search"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def search(self, query: str, max_results: int = 5) -> List[SourceDocument]:
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                self.endpoint,
                headers=headers,
                json={"q": query, "num": max_results},
            )
            resp.raise_for_status()
            data = resp.json()

        documents = []
        for item in data.get("organic", []):
            documents.append(
                SourceDocument(
                    url=item.get("link", ""),
                    title=item.get("title", "Untitled"),
                    source_type=SourceType.WEB,
                    extracted_text=item.get("snippet", ""),
                    summary=item.get("snippet", ""),
                    reliability_score=0.65,
                )
            )
        return documents


class WebSearchTool(BaseTool[SearchParams, List[SourceDocument]]):
    """High-level search tool dispatching queries to the configured SearchProvider."""

    def __init__(self, provider: SearchProvider, timeout_seconds: float = 15.0):
        super().__init__(
            name="web_search",
            description="Searches the web for recent and relevant domain information.",
            timeout_seconds=timeout_seconds,
        )
        self.provider = provider

    async def _run(self, params: SearchParams) -> List[SourceDocument]:
        return await self.provider.search(params.query, params.max_results)

