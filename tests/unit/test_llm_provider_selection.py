"""Unit tests for automatic Groq -> Ollama fallback, LLM provider selection,
preflight checks, rate limit handling, and structured output parsing."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel, Field
from typing import List

from vasukisquare.config import Settings, EnvironmentConfigurationError
from vasukisquare.llm.client import LLMClient, LLMGenerationError
from vasukisquare.llm.metrics import BookGenerationMetrics


class SampleSchema(BaseModel):
    title: str
    points: List[str] = Field(default_factory=list)


def test_provider_selection_auto_with_groq_key():
    """LLM_PROVIDER=auto with valid GROQ_API_KEY selects Groq."""
    settings = Settings(
        _env_file=None,
        llm_provider="auto",
        groq_api_key="gsk_real_key_123",
        groq_model="openai/gpt-oss-120b",
        vasukisquare_mock_mode=True,
    )
    provider, model, reason = settings.resolve_llm_provider()
    assert provider == "groq"
    assert model == "openai/gpt-oss-120b"
    assert "GROQ_API_KEY configured" in reason


def test_provider_selection_auto_with_empty_groq_key():
    """LLM_PROVIDER=auto with empty GROQ_API_KEY selects Ollama."""
    settings = Settings(
        _env_file=None,
        llm_provider="auto",
        groq_api_key="",
        ollama_model="qwen2.5:7b-instruct",
        vasukisquare_mock_mode=True,
    )
    provider, model, reason = settings.resolve_llm_provider()
    assert provider == "ollama"
    assert model == "qwen2.5:7b-instruct"
    assert "missing or empty" in reason


def test_provider_selection_auto_with_whitespace_groq_key():
    """LLM_PROVIDER=auto with whitespace GROQ_API_KEY selects Ollama."""
    settings = Settings(
        _env_file=None,
        llm_provider="auto",
        groq_api_key="   ",
        ollama_model="qwen2.5:7b-instruct",
        vasukisquare_mock_mode=True,
    )
    provider, model, reason = settings.resolve_llm_provider()
    assert provider == "ollama"
    assert model == "qwen2.5:7b-instruct"


def test_provider_selection_auto_with_missing_groq_key():
    """LLM_PROVIDER=auto with None GROQ_API_KEY selects Ollama."""
    settings = Settings(
        _env_file=None,
        llm_provider="auto",
        groq_api_key=None,
        ollama_model="qwen2.5:3b",
        vasukisquare_mock_mode=True,
    )
    provider, model, reason = settings.resolve_llm_provider()
    assert provider == "ollama"
    assert model == "qwen2.5:3b"


def test_provider_selection_explicit_groq_missing_key_fails():
    """LLM_PROVIDER=groq with missing key raises EnvironmentConfigurationError."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="",
        vasukisquare_mock_mode=True,
    )
    with pytest.raises(EnvironmentConfigurationError) as exc:
        settings.resolve_llm_provider()
    assert "LLM_PROVIDER is set to 'groq' but GROQ_API_KEY is missing or empty" in str(exc.value)


def test_provider_selection_explicit_ollama_overrides_groq_key():
    """LLM_PROVIDER=ollama selects Ollama even if GROQ_API_KEY is present."""
    settings = Settings(
        _env_file=None,
        llm_provider="ollama",
        groq_api_key="gsk_dummy_present_key",
        ollama_model="llama3.2:3b",
        ollama_base_url="http://custom-ollama:11434",
        vasukisquare_mock_mode=True,
    )
    provider, model, reason = settings.resolve_llm_provider()
    assert provider == "ollama"
    assert model == "llama3.2:3b"
    assert settings.ollama_base_url == "http://custom-ollama:11434"


def test_ollama_availability_check_server_down():
    """Production validation fails if Ollama server is unreachable."""
    settings = Settings(
        _env_file=None,
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5:7b-instruct",
        tavily_api_key="tvly_test",
        vasukisquare_mock_mode=False,
    )

    with patch("httpx.get", side_effect=Exception("Connection refused")):
        with pytest.raises(EnvironmentConfigurationError) as exc:
            settings.validate_production_environment()
        assert "Ollama server is unavailable" in str(exc.value)
        assert "ollama pull qwen2.5:7b-instruct" in str(exc.value)


def test_ollama_availability_check_model_missing():
    """Production validation fails if configured model is not installed on Ollama server."""
    settings = Settings(
        _env_file=None,
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5:7b-instruct",
        tavily_api_key="tvly_test",
        vasukisquare_mock_mode=False,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [
            {"name": "llama3:latest"},
            {"name": "mistral:latest"},
        ]
    }

    with patch("httpx.get", return_value=mock_resp):
        with pytest.raises(EnvironmentConfigurationError) as exc:
            settings.validate_production_environment()
        assert "Configured Ollama model 'qwen2.5:7b-instruct' is not installed" in str(exc.value)
        assert "ollama pull qwen2.5:7b-instruct" in str(exc.value)


def test_startup_banner_never_exposes_groq_key(capsys):
    """Startup banner prints provider and model without exposing secrets."""
    secret_key = "gsk_super_secret_production_key_xyz987"
    settings = Settings(
        _env_file=None,
        llm_provider="auto",
        groq_api_key=secret_key,
        groq_model="openai/gpt-oss-120b",
        vasukisquare_mock_mode=True,
    )
    client = LLMClient(settings)
    client.log_startup_banner()
    captured = capsys.readouterr()
    assert "LLM Provider: GROQ" in captured.out
    assert "openai/gpt-oss-120b" in captured.out
    assert secret_key not in captured.out


@pytest.mark.asyncio
async def test_groq_rate_limit_fallback_disabled_by_default():
    """When LLM_FALLBACK_ON_RATE_LIMIT=false, 429 does not switch to Ollama."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_key",
        llm_fallback_on_rate_limit=False,
        groq_wait_for_rate_limit=False,
        vasukisquare_mock_mode=True,
    )
    metrics = BookGenerationMetrics()
    client = LLMClient(settings, metrics)

    mock_chat = MagicMock()
    mock_s_llm = MagicMock()
    mock_s_llm.ainvoke = AsyncMock(side_effect=Exception("Error code: 429 - Rate limit exceeded"))
    mock_chat.with_structured_output.return_value = mock_s_llm

    client.get_chat_model = MagicMock(return_value=mock_chat)

    with pytest.raises(LLMGenerationError):
        await client.invoke_structured(
            schema=SampleSchema,
            system_prompt="system",
            user_prompt="user",
            stage="test_rate_limit",
            max_retries=1,
        )

    assert not metrics.fallback_occurred


@pytest.mark.asyncio
async def test_groq_rate_limit_fallback_enabled_switches_to_ollama():
    """When LLM_FALLBACK_ON_RATE_LIMIT=true, genuine 429 switches to Ollama."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_key",
        ollama_model="qwen2.5:7b-instruct",
        llm_fallback_on_rate_limit=True,
        groq_wait_for_rate_limit=False,
        vasukisquare_mock_mode=True,
    )
    metrics = BookGenerationMetrics()
    client = LLMClient(settings, metrics)

    expected = SampleSchema(title="Fallback Result", points=["p1", "p2"])

    def mock_get_chat(temperature=None, provider=None, **kwargs):
        m = MagicMock()
        s_m = MagicMock()
        if provider == "groq":
            s_m.ainvoke = AsyncMock(side_effect=Exception("Error code: 429 - Rate limit exceeded"))
        else:
            s_m.ainvoke = AsyncMock(return_value=expected)
        m.with_structured_output.return_value = s_m
        return m

    client.get_chat_model = MagicMock(side_effect=mock_get_chat)

    res = await client.invoke_structured(
        schema=SampleSchema,
        system_prompt="system",
        user_prompt="user",
        stage="test_rate_limit_switch",
        max_retries=2,
    )

    assert res.title == "Fallback Result"
    assert metrics.fallback_occurred
    assert metrics.fallback_reason == "rate_limit"
