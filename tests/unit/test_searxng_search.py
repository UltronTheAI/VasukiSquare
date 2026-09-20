"""Comprehensive unit tests for SearXNG search provider, normalization, health checks, error handling, and provider resolution."""

from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from vasukisquare.config import Settings
from vasukisquare.research.models import SourceType
from vasukisquare.tools.search import (
    SearchParams,
    SearxngSearchProvider,
    WebSearchTool,
    check_searxng_health,
    create_search_provider,
)


@pytest.fixture(autouse=True)
def clear_health_cache():
    from vasukisquare.tools.search import _SEARXNG_HEALTH_CACHE
    _SEARXNG_HEALTH_CACHE.clear()
    yield
    _SEARXNG_HEALTH_CACHE.clear()


@pytest.mark.asyncio
async def test_searxng_successful_search_and_normalization():
    """1 & 2. Verify SearXNG searches endpoint and returns normalized SourceDocuments."""
    mock_payload = {
        "query": "habit formation behavioral science",
        "number_of_results": 2,
        "results": [
            {
                "url": "https://example.com/habits-guide?utm_source=twitter",
                "title": "The Science of Habit Formation",
                "content": "Habit loops consist of a cue, a routine, and a reward.",
                "engine": "duckduckgo",
            },
            {
                "url": "https://academic.edu/papers/habit-neurobiology",
                "title": "Neural Basis of Habit Learning",
                "content": "Basal ganglia and dopamine pathways regulate automatic behaviors.",
                "engine": "google",
            },
        ],
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        provider = SearxngSearchProvider(url="http://localhost:8080", timeout=10.0)
        docs = await provider.search("habit formation behavioral science", max_results=5)

        assert len(docs) == 2
        # Normalization check: tracking parameter stripped
        assert docs[0].url == "https://example.com/habits-guide"
        assert docs[0].title == "The Science of Habit Formation"
        assert "cue, a routine, and a reward" in docs[0].extracted_text
        assert docs[0].source_type == SourceType.WEB
        assert docs[0].metadata.get("engine") == "duckduckgo"
        assert docs[0].metadata.get("source") == "searxng"

        assert docs[1].url == "https://academic.edu/papers/habit-neurobiology"
        assert docs[1].metadata.get("engine") == "google"


@pytest.mark.asyncio
async def test_searxng_duplicate_url_deduplication():
    """3. Verify SearXNG deduplicates results with identical or variation URLs across engines."""
    mock_payload = {
        "results": [
            {
                "url": "https://example.com/article/?utm_medium=social",
                "title": "Article Title 1",
                "content": "Snippet from DuckDuckGo",
                "engine": "duckduckgo",
            },
            {
                "url": "https://example.com/article",
                "title": "Article Title 2",
                "content": "Snippet from Google",
                "engine": "google",
            },
            {
                "url": "https://example.com/different-article",
                "title": "Different Article",
                "content": "Snippet from Brave",
                "engine": "brave",
            },
        ]
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        provider = SearxngSearchProvider(url="http://localhost:8080")
        docs = await provider.search("test query", max_results=10)

        # 3 items in response, but 2 share the same normalized URL
        assert len(docs) == 2
        assert docs[0].url == "https://example.com/article"
        assert docs[1].url == "https://example.com/different-article"


@pytest.mark.asyncio
async def test_searxng_empty_results():
    """4. Verify empty search results are handled cleanly without exceptions."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"results": []}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        provider = SearxngSearchProvider(url="http://localhost:8080")
        docs = await provider.search("nonexistent query xyz999", max_results=10)
        assert docs == []


@pytest.mark.asyncio
async def test_searxng_html_returned_json_disabled_error():
    """8 & 9. Verify HTML returned instead of JSON raises descriptive error."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    mock_response.text = "<!DOCTYPE html><html><body>SearXNG search page</body></html>"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        provider = SearxngSearchProvider(url="http://localhost:8080")
        with pytest.raises(ValueError) as exc_info:
            await provider.search("test query")

        assert "JSON search output is not enabled" in str(exc_info.value)
        assert "Enable the json search format in SearXNG settings" in str(exc_info.value)


@pytest.mark.asyncio
async def test_searxng_forbidden_format_error():
    """Verify 403 Forbidden with format error raises descriptive error."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 403
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = '{"error": "format json is not allowed"}'

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        provider = SearxngSearchProvider(url="http://localhost:8080")
        with pytest.raises(ValueError) as exc_info:
            await provider.search("test query")

        assert "JSON search output is not enabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_searxng_malformed_json_error():
    """7. Verify malformed JSON payload raises descriptive configuration error."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.side_effect = Exception("JSON decode failed")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        provider = SearxngSearchProvider(url="http://localhost:8080")
        with pytest.raises(ValueError) as exc_info:
            await provider.search("test query")

        assert "JSON search output is not enabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_searxng_max_results_limit_respected():
    """14. Verify max_results bounds the returned documents."""
    results = [
        {"url": f"https://example.com/page{i}", "title": f"Page {i}", "content": f"Content {i}"}
        for i in range(20)
    ]
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"results": results}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        provider = SearxngSearchProvider(url="http://localhost:8080")
        docs = await provider.search("many results", max_results=4)
        assert len(docs) == 4


@pytest.mark.asyncio
async def test_search_cache_prevents_duplicate_http_calls():
    """15. Verify WebSearchTool caches results for identical queries."""
    mock_provider = MagicMock(spec=SearxngSearchProvider)
    mock_provider.search = AsyncMock(return_value=[])

    tool = WebSearchTool(provider=mock_provider, provider_name="searxng")

    params = SearchParams(query="habit formation", max_results=5)
    await tool.execute(params)
    await tool.execute(params)
    await tool.execute(params)

    # Underlying search should have been called only once due to cache
    assert mock_provider.search.call_count == 1


def test_searxng_health_check():
    """Verify check_searxng_health returns True on 200 and False on network error with caching."""
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        assert check_searxng_health("http://localhost:8080") is True

    # Test failure probe
    with patch("httpx.get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        assert check_searxng_health("http://invalid-host:8080") is False


def test_explicit_searxng_provider_selection():
    """10. Verify SEARCH_PROVIDER=searxng resolves to SearXNG provider."""
    settings = Settings(
        app_env="production",
        vasukisquare_mock_mode=False,
        search_provider="searxng",
        searxng_url="http://localhost:8080",
        searxng_enabled=True,
    )
    provider_name, reason = settings.resolve_search_provider()
    assert provider_name == "searxng"
    assert "http://localhost:8080" in reason

    provider = create_search_provider(settings)
    assert isinstance(provider, SearxngSearchProvider)
    assert provider.url == "http://localhost:8080"


def test_auto_mode_selects_healthy_searxng():
    """11. Verify SEARCH_PROVIDER=auto selects SearXNG when healthy."""
    settings = Settings(
        app_env="production",
        vasukisquare_mock_mode=False,
        search_provider="auto",
        searxng_url="http://localhost:8080",
        searxng_enabled=True,
        tavily_api_key="tvly-mock-key",
    )
    with patch("vasukisquare.tools.search.check_searxng_health", return_value=True):
        provider_name, _ = settings.resolve_search_provider()
        assert provider_name == "searxng"


def test_auto_mode_falls_back_when_searxng_unavailable():
    """12. Verify SEARCH_PROVIDER=auto falls back to Tavily/Serper when SearXNG is down."""
    settings = Settings(
        app_env="production",
        vasukisquare_mock_mode=False,
        search_provider="auto",
        searxng_url="http://localhost:8080",
        searxng_enabled=True,
        tavily_api_key="tvly-mock-key",
    )
    with patch("vasukisquare.tools.search.check_searxng_health", return_value=False):
        provider_name, _ = settings.resolve_search_provider()
        assert provider_name == "tavily"


def test_missing_paid_keys_valid_with_searxng():
    """13. Verify production validation passes with SearXNG without requiring Tavily/Serper API keys."""
    settings = Settings(
        app_env="production",
        vasukisquare_mock_mode=False,
        llm_provider="groq",
        groq_api_key="gsk_real_valid_key_12345",
        search_provider="searxng",
        searxng_url="http://localhost:8080",
        searxng_enabled=True,
        tavily_api_key=None,
        serper_api_key=None,
        brave_search_api_key=None,
    )
    assert settings.has_web_search_provider is True

    with patch("vasukisquare.tools.search.check_searxng_health", return_value=True):
        # Should not raise EnvironmentConfigurationError for search
        settings.validate_production_environment()

