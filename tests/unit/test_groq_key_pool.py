"""Unit tests for Groq API Key Pool, multi-key parsing, rotation, and failover mechanics."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel

from vasukisquare.config import Settings
from vasukisquare.llm.client import LLMClient, LLMGenerationError
from vasukisquare.llm.pool import GroqKeyPool, GroqKeyState, is_retryable_groq_error


class SampleSchema(BaseModel):
    title: str
    summary: str


def test_groq_key_parsing_single_and_multiple():
    """Test parsing single key and multiple comma-separated keys with whitespace and empty entries."""
    # Single key backward compatibility
    s1 = Settings(groq_api_key="gsk_single_key_123")
    assert s1.get_groq_api_keys() == ["gsk_single_key_123"]

    # Multiple keys
    s2 = Settings(groq_api_key="gsk_key1, gsk_key2 ,  gsk_key3  ")
    assert s2.get_groq_api_keys() == ["gsk_key1", "gsk_key2", "gsk_key3"]

    # Multiple keys with duplicates and empty entries
    s3 = Settings(groq_api_key="gsk_key1, , gsk_key2, gsk_key1, gsk_key3, ")
    assert s3.get_groq_api_keys() == ["gsk_key1", "gsk_key2", "gsk_key3"]

    # Empty key
    s4 = Settings(groq_api_key="")
    assert s4.get_groq_api_keys() == []


def test_groq_key_state_properties():
    """Test GroqKeyState labels, cooldown calculation, and status."""
    key = GroqKeyState(index=1, api_key="gsk_secret_12345")
    assert key.label == "Groq Key #1"
    assert "gsk_secret" not in repr(key)
    assert key.is_available() is True
    assert key.is_in_cooldown() is False
    assert key.get_cooldown_remaining() == 0.0

    # Put in cooldown
    key.cooldown_until = time.time() + 10.0
    assert key.is_in_cooldown() is True
    assert key.is_available() is False
    assert key.get_cooldown_remaining() > 0.0

    # Invalidate
    key.is_invalid = True
    assert key.is_available() is False
    assert "invalid" in repr(key)


def test_groq_key_pool_preferred_strategy_ordering():
    """Test candidate key ordering with preferred strategy (always prefer Key #1 if available)."""
    pool = GroqKeyPool(
        api_keys=["key1", "key2", "key3"],
        strategy="preferred",
        cooldown_seconds=60.0,
    )
    assert len(pool.keys) == 3

    # Initially, all are available in order 1 -> 2 -> 3
    candidates = pool.get_candidate_keys()
    assert [k.index for k in candidates] == [1, 2, 3]

    # Key 1 gets rate-limited
    pool.mark_rate_limited(pool.keys[0], retry_after=30.0)
    candidates = pool.get_candidate_keys()
    # Key 2 and Key 3 are available, Key 1 is at the end in cooldown
    assert [k.index for k in candidates] == [2, 3, 1]

    # Key 2 gets rate-limited with longer retry_after
    pool.mark_rate_limited(pool.keys[1], retry_after=50.0)
    candidates = pool.get_candidate_keys()
    # Key 3 is available, Key 1 (expires in 30s) comes before Key 2 (expires in 50s)
    assert [k.index for k in candidates] == [3, 1, 2]

    # Key 1 cooldown expires
    pool.keys[0].cooldown_until = time.time() - 1.0
    candidates = pool.get_candidate_keys()
    # Key 1 and Key 3 are available -> Key 1 comes first again!
    assert [k.index for k in candidates] == [1, 3, 2]


def test_groq_key_pool_round_robin_strategy():
    """Test candidate key ordering with round_robin strategy."""
    pool = GroqKeyPool(
        api_keys=["key1", "key2", "key3"],
        strategy="round_robin",
    )
    # Start at 0
    k1 = pool.advance_for_new_request()
    assert k1.index == 2
    candidates = pool.get_candidate_keys()
    assert [k.index for k in candidates] == [2, 3, 1]


def test_groq_key_pool_401_invalidation():
    """Test that 401 permanently excludes key from candidate list."""
    pool = GroqKeyPool(api_keys=["key1", "key2"])
    assert pool.active_key_count() == 2

    # Mark Key 1 invalid
    pool.mark_invalid(pool.keys[0])
    assert pool.keys[0].is_invalid is True
    assert pool.active_key_count() == 1

    candidates = pool.get_candidate_keys()
    assert len(candidates) == 1
    assert candidates[0].index == 2

    # Mark Key 2 invalid
    pool.mark_invalid(pool.keys[1])
    assert pool.active_key_count() == 0
    assert pool.get_candidate_keys() == []


def test_groq_key_pool_summary_sanitization():
    """Verify get_summary contains safe labels and NO actual API keys."""
    raw_keys = ["gsk_very_secret_key_111", "gsk_very_secret_key_222"]
    pool = GroqKeyPool(api_keys=raw_keys)
    pool.mark_success(pool.keys[0])
    pool.mark_rate_limited(pool.keys[1])

    summary = pool.get_summary()
    assert "Groq Key #1" in summary
    assert "Groq Key #2" in summary
    for secret in raw_keys:
        assert secret not in summary


@pytest.mark.asyncio
async def test_llm_client_key_rotation_on_429():
    """Test LLMClient rotates to Key #2 when Key #1 receives HTTP 429."""
    settings = Settings(
        groq_api_key="gsk_key1,gsk_key2",
        llm_provider="groq",
        groq_model="openai/gpt-oss-120b",
        vasukisquare_mock_mode=False,
    )
    client = LLMClient(settings=settings)

    mock_chat1 = MagicMock()
    mock_chat1.ainvoke = AsyncMock(side_effect=Exception("Error code: 429 - rate limit exceeded"))

    mock_chat2 = MagicMock()
    mock_chat2.ainvoke = AsyncMock(return_value=SampleSchema(title="Habits", summary="Daily routines"))

    # Return mock_chat1 when api_key='gsk_key1' and mock_chat2 when api_key='gsk_key2'
    def mock_get_chat_model(*args, **kwargs):
        api_key = kwargs.get("api_key")
        mock_chat = MagicMock()
        if api_key == "gsk_key1":
            mock_chat.with_structured_output = MagicMock(return_value=mock_chat1)
        else:
            mock_chat.with_structured_output = MagicMock(return_value=mock_chat2)
        return mock_chat

    with patch.object(client, "get_chat_model", side_effect=mock_get_chat_model):
        res = await client.invoke_structured(
            schema=SampleSchema,
            system_prompt="Test sys",
            user_prompt="Test user",
            stage="test",
        )

        assert res.title == "Habits"
        # Key 1 was rate limited, Key 2 succeeded
        assert client.groq_key_pool.keys[0].rate_limits == 1
        assert client.groq_key_pool.keys[1].successes == 1


@pytest.mark.asyncio
async def test_llm_client_key_rotation_on_401():
    """Test LLMClient permanently invalidates Key #1 on 401 and succeeds on Key #2."""
    settings = Settings(
        groq_api_key="gsk_bad_key,gsk_good_key",
        llm_provider="groq",
        groq_model="openai/gpt-oss-120b",
        vasukisquare_mock_mode=False,
    )
    client = LLMClient(settings=settings)

    mock_chat_bad = MagicMock()
    mock_chat_bad.ainvoke = AsyncMock(side_effect=Exception("Error code: 401 - Invalid API Key"))

    mock_chat_good = MagicMock()
    mock_chat_good.ainvoke = AsyncMock(return_value=SampleSchema(title="Success", summary="Valid Key"))

    def mock_get_chat_model(*args, **kwargs):
        api_key = kwargs.get("api_key")
        mock_chat = MagicMock()
        if api_key == "gsk_bad_key":
            mock_chat.with_structured_output = MagicMock(return_value=mock_chat_bad)
        else:
            mock_chat.with_structured_output = MagicMock(return_value=mock_chat_good)
        return mock_chat

    with patch.object(client, "get_chat_model", side_effect=mock_get_chat_model):
        res = await client.invoke_structured(
            schema=SampleSchema,
            system_prompt="Test sys",
            user_prompt="Test user",
            stage="test",
        )

        assert res.title == "Success"
        # Key 1 is marked invalid
        assert client.groq_key_pool.keys[0].is_invalid is True
        assert client.groq_key_pool.keys[1].successes == 1


@pytest.mark.asyncio
async def test_llm_client_structured_error_does_not_rotate_key():
    """Verify that JSON schema parse error does NOT mark key in cooldown or rotate key."""
    settings = Settings(
        groq_api_key="gsk_key1,gsk_key2",
        llm_provider="groq",
        groq_model="openai/gpt-oss-120b",
        vasukisquare_mock_mode=False,
    )
    client = LLMClient(settings=settings)

    # First invocation fails with JSON decode error, second invocation on retry succeeds
    mock_chat_attempt = MagicMock()
    mock_chat_attempt.ainvoke = AsyncMock(side_effect=[
        ValueError("jsondecodeerror: Invalid JSON"),
        SampleSchema(title="Recovered", summary="Valid schema"),
    ])

    def mock_get_chat_model(*args, **kwargs):
        mock_chat = MagicMock()
        mock_chat.with_structured_output = MagicMock(return_value=mock_chat_attempt)
        return mock_chat

    with patch.object(client, "get_chat_model", side_effect=mock_get_chat_model):
        res = await client.invoke_structured(
            schema=SampleSchema,
            system_prompt="Test sys",
            user_prompt="Test user",
            stage="test",
        )

        assert res.title == "Recovered"
        # Key 1 was NOT marked in cooldown or rate limited
        assert client.groq_key_pool.keys[0].is_in_cooldown() is False
        assert client.groq_key_pool.keys[0].rate_limits == 0
        assert client.groq_key_pool.keys[0].successes == 1

