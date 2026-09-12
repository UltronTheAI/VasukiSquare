"""Web search tool supporting multiple swappable search providers: SearXNG, Tavily, Serper, Brave, and Mock."""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from vasukisquare.research.models import SourceDocument, SourceType, normalize_url
from vasukisquare.tools.base import BaseTool, SearchProvider

logger = logging.getLogger(__name__)


# Health check cache: url -> (is_healthy, timestamp)
_SEARXNG_HEALTH_CACHE: Dict[str, Tuple[bool, float]] = {}


def check_searxng_health(url: str, timeout: float = 3.0, ttl_seconds: float = 60.0) -> bool:
    """Lightweight check to determine if a SearXNG instance is reachable and healthy."""
    clean_url = (url or "").rstrip("/")
    if not clean_url:
        return False

    now = time.time()
    if clean_url in _SEARXNG_HEALTH_CACHE:
        is_healthy, ts = _SEARXNG_HEALTH_CACHE[clean_url]
        if now - ts < ttl_seconds:
            return is_healthy

    try:
        resp = httpx.get(f"{clean_url}/", timeout=timeout, follow_redirects=True)
        is_healthy = resp.status_code < 500
    except Exception as e:
        logger.debug(f"SearXNG health check probe failed for {clean_url}: {e}")
        is_healthy = False

    _SEARXNG_HEALTH_CACHE[clean_url] = (is_healthy, now)
    return is_healthy


class SearchResult(BaseModel):
    """Normalized search result from any search engine provider."""

    title: str
    url: str
    snippet: str
    source: str
    engine: Optional[str] = None


class SearchParams(BaseModel):
    """Parameters for web search query."""

    query: str
    max_results: int = Field(default=5, ge=1, le=50)


class MockSearchProvider(SearchProvider):
    """Mock search provider for testing and deterministic offline execution."""

    def __init__(self, predefined_results: Optional[List[SourceDocument]] = None):
        self.predefined_results = predefined_results or []

    async def search(self, query: str, max_results: int = 5) -> List[SourceDocument]:
        if self.predefined_results:
            return self.predefined_results[:max_results]

        q_lower = query.lower()
        if "python" in q_lower:
            docs = [
                SourceDocument(
                    url="https://docs.python.org/3/tutorial/index.html",
                    title="The Python Tutorial — Python 3 Documentation",
                    source_type=SourceType.DOCUMENTATION,
                    extracted_text="Python is an easy to learn, powerful programming language. It has efficient high-level data structures and a simple but effective approach to object-oriented programming.",
                    summary="Official Python 3 tutorial introducing basic syntax, data structures, functions, and modules.",
                    reliability_score=0.98,
                ),
                SourceDocument(
                    url="https://peps.python.org/pep-0008/",
                    title="PEP 8 – Style Guide for Python Code",
                    source_type=SourceType.DOCUMENTATION,
                    extracted_text="This document gives coding conventions for the Python code comprising the standard library in the main Python distribution.",
                    summary="The canonical PEP 8 style guide for readable and idiomatic Python programming.",
                    reliability_score=0.95,
                ),
                SourceDocument(
                    url="https://realpython.com/python-basics/",
                    title="Python Basics: A Practical Introduction to Python 3",
                    source_type=SourceType.WEB,
                    extracted_text="Learn Python fundamentals step-by-step: variables, loops, functions, lists, dictionaries, and file input/output.",
                    summary="Hands-on beginner tutorial covering core Python language mechanics and real-world scripting.",
                    reliability_score=0.88,
                ),
            ]
            return docs[:max_results]

        # Derive clean slug and clean title from query
        clean_words = [
            w for w in query.replace(":", " ").replace(",", " ").split()
            if w.lower() not in ("overview", "definition", "fundamentals", "guide", "in-depth")
        ]
        slug = "-".join(clean_words[:6]).lower() if clean_words else "technical-specification"
        title_text = " ".join(clean_words[:6]).title() if clean_words else "System Architecture & Engineering Specification"

        return [
            SourceDocument(
                url=f"https://acm.org/publications/proceedings/{slug}",
                title=f"{title_text} - Primary Specification",
                source_type=SourceType.DOCUMENTATION,
                extracted_text=f"Formal architectural specification and empirical evaluation of {query}.",
                summary=f"Technical specification and performance analysis of {query}.",
                reliability_score=0.90,
            )
        ][:max_results]


class SearxngSearchProvider(SearchProvider):
    """Self-hosted or local SearXNG metasearch engine provider."""

    def __init__(
        self,
        url: str = "http://localhost:8080",
        timeout: float = 20.0,
        default_language: str = "en",
    ):
        self.url = (url or "http://localhost:8080").rstrip("/")
        self.timeout = timeout
        self.default_language = default_language
        self.endpoint = f"{self.url}/search"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)),
        reraise=True,
    )
    async def _fetch_searxng_raw(self, query: str, max_results: int) -> dict:
        params = {
            "q": query,
            "format": "json",
            "language": self.default_language,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(self.endpoint, params=params)

            # Detect JSON format disabled error or HTML returned
            content_type = resp.headers.get("content-type", "").lower()
            if "text/html" in content_type:
                raise ValueError(
                    "SearXNG is reachable but JSON search output is not enabled. "
                    "Enable the json search format in SearXNG settings (search.formats: [html, json])."
                )

            if resp.status_code in (400, 403):
                text_lower = resp.text.lower()
                if "format" in text_lower or "json" in text_lower:
                    raise ValueError(
                        "SearXNG is reachable but JSON search output is not enabled. "
                        "Enable the json search format in SearXNG settings (search.formats: [html, json])."
                    )

            resp.raise_for_status()

            try:
                data = resp.json()
            except Exception as e:
                raise ValueError(
                    "SearXNG is reachable but JSON search output is not enabled. "
                    "Enable the json search format in SearXNG settings."
                ) from e

            if not isinstance(data, dict):
                raise ValueError("SearXNG is reachable but returned invalid non-dictionary JSON.")

            return data

    async def search(self, query: str, max_results: int = 10) -> List[SourceDocument]:
        data = await self._fetch_searxng_raw(query, max_results)

        raw_results = data.get("results", [])
        documents: List[SourceDocument] = []
        seen_urls: set[str] = set()

        for item in raw_results:
            raw_url = item.get("url", "")
            if not raw_url:
                continue

            try:
                norm_url = normalize_url(raw_url)
            except Exception:
                norm_url = raw_url

            if not norm_url or norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)

            title = item.get("title", "Untitled")
            content = item.get("content", "") or item.get("snippet", "")
            engine = item.get("engine") or (item.get("engines", [None])[0] if isinstance(item.get("engines"), list) else None)

            metadata: Dict[str, Any] = {"source": "searxng"}
            if engine:
                metadata["engine"] = engine

            documents.append(
                SourceDocument(
                    url=norm_url,
                    title=title,
                    source_type=SourceType.WEB,
                    extracted_text=content,
                    summary=content,
                    reliability_score=0.75,
                    metadata=metadata,
                )
            )

            if len(documents) >= max_results:
                break

        logger.info(
            f"[Research] Search provider: SearXNG | Query: '{query}' | "
            f"Results: {len(raw_results)} | Unique URLs: {len(documents)}"
        )
        return documents


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
        seen_urls: set[str] = set()
        for item in data.get("results", []):
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            documents.append(
                SourceDocument(
                    url=url,
                    title=item.get("title", "Untitled"),
                    source_type=SourceType.WEB,
                    extracted_text=item.get("content", ""),
                    summary=item.get("snippet", ""),
                    reliability_score=0.7,
                )
            )
            if len(documents) >= max_results:
                break
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
        seen_urls: set[str] = set()
        for item in data.get("organic", []):
            url = item.get("link", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            documents.append(
                SourceDocument(
                    url=url,
                    title=item.get("title", "Untitled"),
                    source_type=SourceType.WEB,
                    extracted_text=item.get("snippet", ""),
                    summary=item.get("snippet", ""),
                    reliability_score=0.65,
                )
            )
            if len(documents) >= max_results:
                break
        return documents


class BraveSearchProvider(SearchProvider):
    """Brave Search provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = "https://api.search.brave.com/res/v1/web/search"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def search(self, query: str, max_results: int = 5) -> List[SourceDocument]:
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                self.endpoint,
                headers=headers,
                params={"q": query, "count": max_results},
            )
            resp.raise_for_status()
            data = resp.json()

        documents = []
        seen_urls: set[str] = set()
        for item in data.get("web", {}).get("results", []):
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            documents.append(
                SourceDocument(
                    url=url,
                    title=item.get("title", "Untitled"),
                    source_type=SourceType.WEB,
                    extracted_text=item.get("description", ""),
                    summary=item.get("description", ""),
                    reliability_score=0.7,
                )
            )
            if len(documents) >= max_results:
                break
        return documents


class WebSearchTool(BaseTool[SearchParams, List[SourceDocument]]):
    """High-level search tool dispatching queries to the configured SearchProvider with query caching."""

    def __init__(
        self,
        provider: SearchProvider,
        timeout_seconds: float = 25.0,
        provider_name: Optional[str] = None,
    ):
        super().__init__(
            name="web_search",
            description="Searches the web for recent and relevant domain information.",
            timeout_seconds=timeout_seconds,
        )
        self.provider = provider
        self.provider_name = provider_name or provider.__class__.__name__.replace("SearchProvider", "").lower()
        self._cache: Dict[Tuple[str, str, int], List[SourceDocument]] = {}

    async def _run(self, params: SearchParams) -> List[SourceDocument]:
        cache_key = (self.provider_name, params.query.strip().lower(), params.max_results)
        if cache_key in self._cache:
            logger.debug(f"[SEARCH CACHE HIT] provider={self.provider_name} query='{params.query}'")
            return self._cache[cache_key]

        results = await self.provider.search(params.query, params.max_results)
        self._cache[cache_key] = results
        logger.info(f"[SEARCH] provider={self.provider_name} query=\"{params.query}\" results={len(results)}")
        return results


def create_search_provider(settings: Any) -> SearchProvider:
    """Factory creating the appropriate SearchProvider based on application settings."""
    if getattr(settings, "vasukisquare_mock_mode", False):
        return MockSearchProvider()

    provider_name, _ = settings.resolve_search_provider()

    if provider_name == "searxng":
        return SearxngSearchProvider(
            url=settings.searxng_url,
            timeout=settings.searxng_timeout,
            default_language=settings.default_language,
        )
    elif provider_name == "tavily":
        return TavilySearchProvider(api_key=settings.tavily_api_key)
    elif provider_name == "serper":
        return SerperSearchProvider(api_key=settings.serper_api_key)
    elif provider_name == "brave":
        return BraveSearchProvider(api_key=settings.brave_search_api_key)
    else:
        return MockSearchProvider()


def create_search_tool(settings: Any) -> WebSearchTool:
    """Factory creating the configured WebSearchTool."""
    provider = create_search_provider(settings)
    provider_name = getattr(settings, "active_search_provider_name", None)
    timeout = getattr(settings, "searxng_timeout", 20.0) + 5.0
    return WebSearchTool(provider=provider, timeout_seconds=timeout, provider_name=provider_name)
