"""Integration tests for the end-to-end research subsystem and tool providers."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from vasukisquare.config import Settings
from vasukisquare.research.models import SourceDocument, SourceType, ResearchCorpus
from vasukisquare.research.service import ResearchService
from vasukisquare.research.planner import ResearchPlanner
from vasukisquare.tools.search import WebSearchTool, MockSearchProvider, SearchParams
from vasukisquare.tools.wikipedia import WikipediaTool, WikipediaParams
from vasukisquare.tools.fetcher import WebpageFetcherTool, clean_html_content


def test_mock_search_provider_execution():
    async def _test():
        provider = MockSearchProvider([
            SourceDocument(
                url="https://github.com/fastapi/fastapi",
                title="FastAPI Repository",
                source_type=SourceType.DOCUMENTATION,
                extracted_text="FastAPI framework, high performance, easy to learn, fast to code, ready for production.",
            )
        ])
        tool = WebSearchTool(provider=provider)
        results = await tool.execute(SearchParams(query="fastapi framework", max_results=1))

        assert len(results) == 1
        assert results[0].domain == "github.com"
        assert results[0].source_type == SourceType.DOCUMENTATION

    asyncio.run(_test())


def test_research_service_end_to_end():
    async def _test():
        # Setup mock search provider returning custom technical sources
        mock_docs = [
            SourceDocument(
                url="https://docs.python.org/3/library/asyncio.html",
                title="Python AsyncIO",
                source_type=SourceType.DOCUMENTATION,
                extracted_text="AsyncIO detailed technical specifications and event loop mechanics." * 10,
            ),
            SourceDocument(
                url="https://en.wikipedia.org/wiki/Asynchronous_I/O",
                title="Asynchronous I/O - Wikipedia",
                source_type=SourceType.WIKIPEDIA,
                extracted_text="Asynchronous I/O is a form of input/output processing." * 10,
            ),
            SourceDocument(
                url="https://docs.python.org/3/library/asyncio.html?utm_medium=blog",
                title="Python AsyncIO Duplicate",
                source_type=SourceType.DOCUMENTATION,
                extracted_text="AsyncIO duplicate text.",
            ),
        ]
        search_tool = WebSearchTool(provider=MockSearchProvider(mock_docs))
        wikipedia_tool = WikipediaTool()
        wikipedia_tool.execute = AsyncMock(return_value=[  # type: ignore
            SourceDocument(
                url="https://en.wikipedia.org/wiki/Asynchronous_I/O",
                title="Asynchronous I/O - Wikipedia",
                source_type=SourceType.WIKIPEDIA,
                extracted_text="General encyclopedia overview.",
            )
        ])

        settings = Settings(vasukisquare_mock_mode=True)
        service = ResearchService(
            settings=settings,
            search_tool=search_tool,
            wikipedia_tool=wikipedia_tool,
        )

        corpus: ResearchCorpus = await service.research_topic("Asynchronous Programming in Python")

        assert corpus.topic == "Asynchronous Programming in Python"
        assert len(corpus.documents) > 0
        # Verified deduplication
        urls = [d.url for d in corpus.documents]
        assert len(urls) == len(set(urls))
        # Verified highest authority document ranks top
        assert corpus.documents[0].source_type == SourceType.DOCUMENTATION
        assert corpus.documents[0].domain == "docs.python.org"

    asyncio.run(_test())


def test_html_cleaner():
    raw_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>MongoDB Architecture Guide</title>
        <style>.hide { display: none; }</style>
        <script>console.log('tracker');</script>
      </head>
      <body>
        <nav><a href="/">Home</a></nav>
        <main>
          <h1>WiredTiger Storage Engine</h1>
          <p>WiredTiger provides document-level concurrency and checkpointing.</p>
        </main>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """
    title, text = clean_html_content(raw_html)
    assert title == "MongoDB Architecture Guide"
    assert "WiredTiger provides document-level concurrency" in text
    assert "console.log" not in text
    assert "Copyright" not in text

