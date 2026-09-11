"""Tools domain: search, scraping, Wikipedia, RSS, and documentation extractors."""

from vasukisquare.tools.base import BaseTool, SearchProvider
from vasukisquare.tools.search import (
    WebSearchTool,
    SearchParams,
    MockSearchProvider,
    TavilySearchProvider,
    SerperSearchProvider,
)
from vasukisquare.tools.wikipedia import WikipediaTool, WikipediaParams
from vasukisquare.tools.fetcher import WebpageFetcherTool, FetchParams
from vasukisquare.tools.feed import RssNewsTool, FeedParams
from vasukisquare.tools.documentation import DocScraperTool, DocScraperParams

__all__ = [
    "BaseTool",
    "SearchProvider",
    "WebSearchTool",
    "SearchParams",
    "MockSearchProvider",
    "TavilySearchProvider",
    "SerperSearchProvider",
    "WikipediaTool",
    "WikipediaParams",
    "WebpageFetcherTool",
    "FetchParams",
    "RssNewsTool",
    "FeedParams",
    "DocScraperTool",
    "DocScraperParams",
]
