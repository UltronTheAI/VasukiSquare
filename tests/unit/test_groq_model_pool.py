"""Unit tests for Groq Model Group / Model Pool, failover logic, strategies,
cooldown tracking, error classification, and provider fallback independence."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel, Field
from typing import List, Optional

from vasukisquare.config import Settings, get_groq_models
from vasukisquare.llm.client import LLMClient, LLMGenerationError, GroqGenerationError
from vasukisquare.llm.metrics import BookGenerationMetrics
from vasukisquare.llm.pool import (
    GroqModelPool,
    parse_model_list,
    parse_retry_after,
    is_retryable_groq_error,
)


class DummyOutputSchema(BaseModel):
    title: str = "Test"
    summary: str = "Success"


# =========================================================================
# 1. Parsing & Configuration Tests
# =========================================================================

def test_single_model_configuration():
    """Single model configured via GROQ_MODELS or GROQ_MODEL."""
    models = parse_model_list("openai/gpt-oss-120b")
    assert models == ["openai/gpt-oss-120b"]

    settings = Settings(
        _env_file=None,
        groq_model="openai/gpt-oss-120b",
        groq_models="",
        vasukisquare_mock_mode=True,
    )
    assert settings.get_groq_models() == ["openai/gpt-oss-120b"]


def test_three_model_group_parsing():
    """Three-model group parsed correctly into ordered list."""
    raw = "openai/gpt-oss-120b, llama-3.3-70b-versatile, llama-3.1-8b-instant"
    models = parse_model_list(raw)
    assert models == [
        "openai/gpt-oss-120b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]


def test_duplicate_model_entries_parsing():
    """Duplicate model entries are deduplicated while preserving first occurrence order."""
    raw = "model-a, model-b, model-a, model-c, model-b"
    models = parse_model_list(raw)
    assert models == ["model-a", "model-b", "model-c"]


def test_empty_and_whitespace_model_entries_parsing():
    """Empty strings, commas, and excessive whitespace are safely ignored."""
    raw = "  model-1, ,  , model-2 , , model-3  "
    models = parse_model_list(raw)
    assert models == ["model-1", "model-2", "model-3"]


def test_empty_input_defaults_to_default_model():
    """Empty or None input returns default model."""
    assert parse_model_list("") == ["openai/gpt-oss-120b"]
    assert parse_model_list(None) == ["openai/gpt-oss-120b"]
    assert parse_model_list("   ") == ["openai/gpt-oss-120b"]


def test_backward_compatible_groq_model_env():
    """Existing single-model GROQ_MODEL in .env works transparently."""
    settings = Settings(
        _env_file=None,
        groq_model="llama-3.3-70b-versatile",
        groq_models="",
        vasukisquare_mock_mode=True,
    )
    assert settings.get_groq_models() == ["llama-3.3-70b-versatile"]


def test_task_specific_model_groups():
    """Task-specific model pools override global pool for writing/research/planning."""
    settings = Settings(
        _env_file=None,
        groq_models="global-1, global-2",
        groq_models_writing="write-1, write-2",
        groq_models_research="research-1",
        vasukisquare_mock_mode=True,
    )
    assert settings.get_groq_models() == ["global-1", "global-2"]
    assert settings.get_groq_models("writing") == ["write-1", "write-2"]
    assert settings.get_groq_models("research") == ["research-1"]
    assert settings.get_groq_models("planning") == ["global-1", "global-2"]


# =========================================================================
# 2. Pool Selection Strategies & Cooldowns
# =========================================================================

def test_ordered_strategy():
    """Ordered strategy starts with first model and advances only on failover."""
    pool = GroqModelPool(["model-1", "model-2", "model-3"], strategy="ordered")
    assert pool.current_model == "model-1"
    assert pool.get_candidate_models() == ["model-1", "model-2", "model-3"]


def test_rotate_strategy():
    """Rotate strategy round-robins the starting model per request."""
    pool = GroqModelPool(["model-1", "model-2", "model-3"], strategy="rotate")
    assert pool.current_model == "model-1"
    
    m2 = pool.advance_for_new_request()
    assert m2 == "model-2"
    assert pool.current_model == "model-2"

    m3 = pool.advance_for_new_request()
    assert m3 == "model-3"

    m1 = pool.advance_for_new_request()
    assert m1 == "model-1"


def test_random_strategy():
    """Random strategy shuffles configured models on pool initialization."""
    models = [f"model-{i}" for i in range(10)]
    pool = GroqModelPool(models, strategy="random")
    assert set(pool.models) == set(models)
    assert len(pool.models) == 10


def test_cooldown_prioritization():
    """Models in cooldown are placed after available models in candidate ordering."""
    pool = GroqModelPool(["model-1", "model-2", "model-3"], cooldown_seconds=60.0)
    assert not pool.is_in_cooldown("model-1")

    # Mark model-1 in cooldown
    pool.record_failure("model-1", Exception("429 Rate limit"), is_rate_limit=True)
    assert pool.is_in_cooldown("model-1")
    assert pool.get_cooldown_remaining("model-1") > 0

    candidates = pool.get_candidate_models()
    # Available models (model-2, model-3) must precede model-1
    assert candidates[0] == "model-2"
    assert candidates[1] == "model-3"
    assert candidates[2] == "model-1"


def test_retry_after_header_and_regex_parsing():
    """parse_retry_after extracts delay from header or string message."""
    # From message
    err1 = Exception("Rate limit exceeded. Try again in 14.5s")
    assert parse_retry_after(err1) == 14.5

    err2 = Exception("Resource exhausted. retry_after: 30")
    assert parse_retry_after(err2) == 30.0

    # From mock response headers
    class MockResp:
        headers = {"retry-after": "45"}
    err3 = Exception("429 Too Many Requests")
    err3.response = MockResp()
    assert parse_retry_after(err3) == 45.0


def test_error_classification():
    """is_retryable_groq_error correctly identifies retryable vs non-retryable errors."""
    # 401 Unauthorized / Invalid API Key -> Non-retryable
    info1 = is_retryable_groq_error(Exception("401 Unauthorized: Invalid API key"))
    assert not info1.is_retryable

    # 429 Rate limit -> Retryable
    info2 = is_retryable_groq_error(Exception("429 Rate limit reached for TPM. Try again in 5.2s"))
    assert info2.is_retryable
    assert info2.is_rate_limit
    assert info2.retry_after == 5.2

    # 503 Service Unavailable -> Retryable
    info3 = is_retryable_groq_error(Exception("503 Service Unavailable: Server overloaded"))
    assert info3.is_retryable
    assert not info3.is_rate_limit

    # Model decommissioned / not found -> Retryable across models
    info4 = is_retryable_groq_error(Exception("Model 'old-model' is decommissioned and no longer exists"))
    assert info4.is_retryable
    assert info4.is_model_unavailable


# =========================================================================
# 3. LLMClient Failover & Execution Tests
# =========================================================================

@pytest.mark.asyncio
async def test_first_model_succeeds():
    """First model succeeds on first attempt: 0 failovers, 0 switches."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_real_key",
        groq_models="model-1, model-2, model-3",
        groq_model_fallback=True,
        vasukisquare_mock_mode=True,
    )
    client = LLMClient(settings=settings)

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    expected_result = DummyOutputSchema(title="Success Title", summary="Success Summary")
    mock_structured.ainvoke = AsyncMock(return_value=expected_result)
    mock_llm.with_structured_output.return_value = mock_structured

    with patch.object(client, "get_chat_model", return_value=mock_llm):
        result = await client.invoke_structured(
            schema=DummyOutputSchema,
            system_prompt="sys",
            user_prompt="usr",
            stage="test_stage",
        )

    assert result.title == "Success Title"
    assert client.groq_pool.current_model == "model-1"
    assert client.groq_pool.model_switches == 0
    assert client.groq_pool.model_stats["model-1"]["successes"] == 1


@pytest.mark.asyncio
async def test_first_model_429_second_model_succeeds():
    """First model hits 429 rate limit, client immediately fails over to second model."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_real_key",
        groq_models="model-1, model-2, model-3",
        groq_model_fallback=True,
        groq_retries_per_model=1,
        vasukisquare_mock_mode=True,
    )
    client = LLMClient(settings=settings)

    call_models = []

    def fake_get_chat_model(temperature=None, provider=None, model_name=None):
        call_models.append(model_name)
        mock_llm = MagicMock()
        mock_structured = MagicMock()

        if model_name == "model-1":
            # Simulate 429 rate limit error
            mock_structured.ainvoke = AsyncMock(side_effect=Exception("429 Too Many Requests: Rate limit exceeded"))
        else:
            # model-2 succeeds
            mock_structured.ainvoke = AsyncMock(return_value=DummyOutputSchema(title="Model 2 Output"))

        mock_llm.with_structured_output.return_value = mock_structured
        return mock_llm

    with patch.object(client, "get_chat_model", side_effect=fake_get_chat_model):
        result = await client.invoke_structured(
            schema=DummyOutputSchema,
            system_prompt="sys",
            user_prompt="usr",
            stage="test_stage",
        )

    assert result.title == "Model 2 Output"
    assert call_models == ["model-1", "model-2"]
    assert client.groq_pool.current_model == "model-2"
    assert client.groq_pool.model_switches == 1
    assert client.groq_pool.model_stats["model-1"]["rate_limits"] == 1
    assert client.groq_pool.model_stats["model-2"]["successes"] == 1


@pytest.mark.asyncio
async def test_first_two_models_fail_third_succeeds():
    """First two models encounter retryable errors (429, 503), third model succeeds."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_real_key",
        groq_models="model-1, model-2, model-3",
        groq_model_fallback=True,
        groq_retries_per_model=1,
        vasukisquare_mock_mode=True,
    )
    client = LLMClient(settings=settings)

    call_models = []

    def fake_get_chat_model(temperature=None, provider=None, model_name=None):
        call_models.append(model_name)
        mock_llm = MagicMock()
        mock_structured = MagicMock()

        if model_name == "model-1":
            mock_structured.ainvoke = AsyncMock(side_effect=Exception("429 Rate limit exceeded"))
        elif model_name == "model-2":
            mock_structured.ainvoke = AsyncMock(side_effect=Exception("503 Service Unavailable: Server overloaded"))
        else:
            mock_structured.ainvoke = AsyncMock(return_value=DummyOutputSchema(title="Model 3 Output"))

        mock_llm.with_structured_output.return_value = mock_structured
        return mock_llm

    with patch.object(client, "get_chat_model", side_effect=fake_get_chat_model):
        result = await client.invoke_structured(
            schema=DummyOutputSchema,
            system_prompt="sys",
            user_prompt="usr",
            stage="test_stage",
        )

    assert result.title == "Model 3 Output"
    assert call_models == ["model-1", "model-2", "model-3"]
    assert client.groq_pool.current_model == "model-3"
    assert client.groq_pool.model_switches == 1
    assert client.groq_pool.model_stats["model-3"]["successes"] == 1


@pytest.mark.asyncio
async def test_all_pool_models_fail_raises_clear_error():
    """When every model in the pool fails and provider fallback is disabled, a clear error is raised."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_real_key",
        groq_models="model-1, model-2",
        groq_model_fallback=True,
        llm_fallback_on_rate_limit=False,
        vasukisquare_mock_mode=True,
    )
    client = LLMClient(settings=settings)

    def fake_get_chat_model(temperature=None, provider=None, model_name=None):
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(side_effect=Exception(f"429 Quota exhausted on {model_name}"))
        mock_llm.with_structured_output.return_value = mock_structured
        return mock_llm

    with patch.object(client, "get_chat_model", side_effect=fake_get_chat_model):
        with pytest.raises(LLMGenerationError) as exc_info:
            await client.invoke_structured(
                schema=DummyOutputSchema,
                system_prompt="sys",
                user_prompt="usr",
                stage="writing_stage",
            )

    err_msg = str(exc_info.value)
    assert "Groq structured generation failed for stage 'writing_stage'" in err_msg
    assert "model-1" in err_msg
    assert "model-2" in err_msg


@pytest.mark.asyncio
async def test_invalid_api_key_does_not_rotate_endlessly():
    """Non-retryable 401 Unauthorized fails immediately on the first model without switching."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_invalid_key",
        groq_models="model-1, model-2, model-3",
        groq_model_fallback=True,
        vasukisquare_mock_mode=True,
    )
    client = LLMClient(settings=settings)

    call_models = []

    def fake_get_chat_model(temperature=None, provider=None, model_name=None):
        call_models.append(model_name)
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(side_effect=Exception("401 Unauthorized: Invalid API key"))
        mock_llm.with_structured_output.return_value = mock_structured
        return mock_llm

    with patch.object(client, "get_chat_model", side_effect=fake_get_chat_model):
        with pytest.raises(Exception) as exc_info:
            await client.invoke_structured(
                schema=DummyOutputSchema,
                system_prompt="sys",
                user_prompt="usr",
                stage="test_stage",
            )

    assert "401" in str(exc_info.value) or "invalid api key" in str(exc_info.value).lower()
    # Ensured it did NOT rotate to model-2 or model-3
    assert call_models == ["model-1"]


@pytest.mark.asyncio
async def test_provider_fallback_to_ollama_after_all_groq_models_fail():
    """When LLM_FALLBACK_ON_RATE_LIMIT=true, Ollama is invoked only after all Groq models fail."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_real_key",
        groq_models="model-1, model-2",
        groq_model_fallback=True,
        llm_fallback_on_rate_limit=True,
        ollama_model="qwen2.5:7b-instruct",
        vasukisquare_mock_mode=True,
    )
    client = LLMClient(settings=settings)

    providers_called = []

    def fake_get_chat_model(temperature=None, provider=None, model_name=None):
        providers_called.append((provider, model_name))
        mock_llm = MagicMock()
        mock_structured = MagicMock()

        if provider == "groq":
            mock_structured.ainvoke = AsyncMock(side_effect=Exception(f"429 Rate limit on {model_name}"))
        elif provider == "ollama":
            mock_structured.ainvoke = AsyncMock(return_value=DummyOutputSchema(title="Ollama Fallback Output"))

        mock_llm.with_structured_output.return_value = mock_structured
        return mock_llm

    with patch.object(client, "get_chat_model", side_effect=fake_get_chat_model):
        result = await client.invoke_structured(
            schema=DummyOutputSchema,
            system_prompt="sys",
            user_prompt="usr",
            stage="test_stage",
        )

    assert result.title == "Ollama Fallback Output"
    assert ("groq", "model-1") in providers_called
    assert ("groq", "model-2") in providers_called
    assert ("ollama", "qwen2.5:7b-instruct") in providers_called
    assert client.metrics.fallback_occurred is True

