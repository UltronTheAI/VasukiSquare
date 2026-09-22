"""Unit tests for DevToPublisher external API communication and tag sanitization."""

from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import pytest

from vasukisquare.promotion.models import PromotionPost
from vasukisquare.promotion.publishers.devto import (
    DevToPublisher,
    sanitize_devto_tag,
    sanitize_devto_tags,
)


@pytest.fixture
def sample_post():
    return PromotionPost(
        campaign_run_id="camp_test",
        book_id="book-123",
        book_slug="rust-memory-safety",
        platform="devto",
        title="Understanding Rust Memory Safety: Borrowing, Lifetimes, and RAII",
        body_markdown="# Rust Memory Safety\n\nRust eliminates data races...",
        tags=["#Rust", "WebAssembly", "Programming 101", "systems-engineering", "extra-tag"],
        canonical_url="https://vasukisquare.cc/book/rust-memory-safety",
    )


# ==============================================================================
# Tag Sanitization Unit Tests
# ==============================================================================

def test_sanitize_devto_tag_valid_unchanged():
    assert sanitize_devto_tag("python") == "python"
    assert sanitize_devto_tag("webdev") == "webdev"
    assert sanitize_devto_tag("vue3") == "vue3"


def test_sanitize_devto_tag_hyphenated():
    assert sanitize_devto_tag("urban-gardening") == "urbangardening"
    assert sanitize_devto_tag("design-patterns") == "designpatterns"
    assert sanitize_devto_tag("no-code-tools") == "nocodetools"


def test_sanitize_devto_tag_spaces():
    assert sanitize_devto_tag("Web Development") == "webdevelopment"
    assert sanitize_devto_tag(" machine learning ") == "machinelearning"


def test_sanitize_devto_tag_hashtags_and_underscores():
    assert sanitize_devto_tag("#Python") == "python"
    assert sanitize_devto_tag("###Rust") == "rust"
    assert sanitize_devto_tag("system_design") == "systemdesign"
    assert sanitize_devto_tag("_private_api_") == "privateapi"


def test_sanitize_devto_tag_uppercase_and_punctuation():
    assert sanitize_devto_tag("TypeScript") == "typescript"
    assert sanitize_devto_tag("node.js") == "nodejs"
    assert sanitize_devto_tag("c++") == "c"
    assert sanitize_devto_tag("a.b!c?d*") == "abcd"


def test_sanitize_devto_tag_unicode():
    assert sanitize_devto_tag("gärten") == "grten"
    assert sanitize_devto_tag("café") == "caf"
    assert sanitize_devto_tag("🦀rust") == "rust"


def test_sanitize_devto_tag_empty_or_all_symbols():
    assert sanitize_devto_tag("") is None
    assert sanitize_devto_tag("   ") is None
    assert sanitize_devto_tag("###---___!!!") is None
    assert sanitize_devto_tag(None) is None


def test_sanitize_devto_tag_max_length():
    long_tag = "a" * 50
    sanitized = sanitize_devto_tag(long_tag, max_length=30)
    assert len(sanitized) == 30
    assert sanitized == "a" * 30


def test_sanitize_devto_tags_list():
    raw_tags = [
        "urban-gardening",
        "#Python",
        "design-patterns",
        "web_dev",
        "Extra-Fifth-Tag",
    ]
    clean = sanitize_devto_tags(raw_tags)
    assert clean == ["urbangardening", "python", "designpatterns", "webdev"]
    assert len(clean) == 4


def test_sanitize_devto_tags_deduplication():
    raw_tags = ["Python", "#python", "python", "PYTHON", "rust"]
    clean = sanitize_devto_tags(raw_tags)
    assert clean == ["python", "rust"]


def test_sanitize_devto_tags_fallback_when_empty():
    clean = sanitize_devto_tags([], fallback_category="distributed-systems")
    assert clean == ["distributedsystems"]

    clean_all_invalid = sanitize_devto_tags(["---", "###"], fallback_category="Database-Internals")
    assert clean_all_invalid == ["databaseinternals"]

    clean_no_category = sanitize_devto_tags(["---", "###"], fallback_category=None)
    assert clean_no_category == ["programming", "tech"]


# ==============================================================================
# DEV.to Publisher API & Payload Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_devto_missing_api_key(sample_post):
    publisher = DevToPublisher(api_key="")
    result = await publisher.publish(sample_post)
    assert result.success is False
    assert "DEVTO_API_KEY is missing" in result.error_message


@pytest.mark.asyncio
async def test_devto_publish_payload_strictly_sanitizes_tags():
    """Verify that invalid tags (hyphens, spaces, hashtags) NEVER reach DEV API request."""
    publisher = DevToPublisher(api_key="test_devto_key", max_retries=1)

    post_with_bad_tags = PromotionPost(
        campaign_run_id="camp_test_bad_tags",
        book_id="book-999",
        book_slug="urban-farming-guide",
        platform="devto",
        title="Sustainable Urban Farming Patterns",
        body_markdown="# Urban Farming\n\nContent...",
        tags=[
            "urban-gardening",
            "design-patterns",
            "#Sustainable Living",
            "system_design_101",
            "overflow_5th_tag",
        ],
        canonical_url="https://vasukisquare.cc/book/urban-farming-guide",
    )

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": 123456,
        "url": "https://dev.to/vasukisquare/sustainable-urban-farming-patterns-123456",
        "path": "/vasukisquare/sustainable-urban-farming-patterns-123456",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await publisher.publish(post_with_bad_tags)

        assert result.success is True
        mock_post.assert_called_once()
        called_kwargs = mock_post.call_args[1]
        submitted_tags = called_kwargs["json"]["article"]["tags"]

        # Verification: all submitted tags must be strictly [a-z0-9] and max 4
        assert len(submitted_tags) == 4
        assert submitted_tags == [
            "urbangardening",
            "designpatterns",
            "sustainableliving",
            "systemdesign101",
        ]
        for tag in submitted_tags:
            assert tag.isalnum()
            assert tag.islower()
            assert "-" not in tag
            assert "_" not in tag
            assert " " not in tag
            assert "#" not in tag


@pytest.mark.asyncio
async def test_devto_publish_success(sample_post):
    publisher = DevToPublisher(api_key="test_devto_key", max_retries=1)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": 998877,
        "url": "https://dev.to/vasukisquare/understanding-rust-memory-safety-998877",
        "path": "/vasukisquare/understanding-rust-memory-safety-998877",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await publisher.publish(sample_post)

        assert result.success is True
        assert result.external_post_id == "998877"
        assert result.external_url == "https://dev.to/vasukisquare/understanding-rust-memory-safety-998877"

        # Verify request payload
        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        assert called_args[0] == "https://dev.to/api/articles"
        assert called_kwargs["headers"]["api-key"] == "test_devto_key"
        payload = called_kwargs["json"]["article"]
        assert payload["title"] == sample_post.title
        assert payload["canonical_url"] == sample_post.canonical_url
        assert payload["published"] is True
        assert payload["tags"] == ["rust", "webassembly", "programming101", "systemsengineering"]


@pytest.mark.asyncio
async def test_devto_publish_401_unauthorized(sample_post):
    publisher = DevToPublisher(api_key="invalid_key", max_retries=2)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": "unauthorized"}
    mock_response.text = '{"error": "unauthorized"}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await publisher.publish(sample_post)

        assert result.success is False
        assert "401 Unauthorized" in result.error_message
        assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_devto_publish_422_validation_error(sample_post):
    publisher = DevToPublisher(api_key="valid_key", max_retries=2)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 422
    mock_response.json.return_value = {"error": "Title has already been taken"}
    mock_response.text = '{"error": "Title has already been taken"}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await publisher.publish(sample_post)

        assert result.success is False
        assert "422 Unprocessable Entity" in result.error_message
        assert mock_post.call_count == 1
