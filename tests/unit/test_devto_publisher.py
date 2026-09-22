"""Unit tests for DevToPublisher external API communication."""

import json
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import pytest

from vasukisquare.promotion.models import PromotionPost
from vasukisquare.promotion.publishers.devto import DevToPublisher


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


@pytest.mark.asyncio
async def test_devto_missing_api_key(sample_post):
    publisher = DevToPublisher(api_key="")
    result = await publisher.publish(sample_post)
    assert result.success is False
    assert "DEVTO_API_KEY is missing" in result.error_message


def test_tag_sanitization():
    publisher = DevToPublisher(api_key="test_key")
    dirty_tags = ["#RustLang", "System-Design", "C++ & Memory", "cloud_native", "extra_5th"]
    clean = publisher._sanitize_tags(dirty_tags)
    assert len(clean) == 4
    assert clean[0] == "rustlang"
    assert clean[1] == "system-design"
    assert clean[2] == "cmemory"
    assert clean[3] == "cloud_native"


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
        assert len(payload["tags"]) <= 4


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
        # Should not waste retries on 401
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

