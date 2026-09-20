"""Comprehensive unit tests for Groq rate-limit smart wait/retry, structured output recovery,
token color normalization, multi-factor density validation, and pipeline checkpoint/resume.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel

from vasukisquare.config import Settings
from vasukisquare.design.tokens import ColorToken, normalize_design_color
from vasukisquare.design.icons import LucideIcon, render_lucide_icon
from vasukisquare.llm.client import LLMClient
from vasukisquare.llm.pool import (
    GroqModelPool,
    is_retryable_groq_error,
)
from vasukisquare.book.models import (
    BookIntent,
    BookPlan,
    PageContent,
    PlannedPage,
)
from vasukisquare.book.components import (
    CalloutBlock,
    CodeBlock,
    ComparisonBlock,
    StepBlock,
    TableBlock,
    TerminalBlock,
    TerminalLine,
    TextBlock,
)
from vasukisquare.agents.content_validator import count_page_words, validate_page_content
from vasukisquare.pipeline.orchestrator import EbookGenerationPipeline


class SampleSchema(BaseModel):
    title: str = "Test"
    description: str = "Reliability Test"


# =========================================================================
# 1. Groq Rate Limit Smart Wait & Retry
# =========================================================================

@pytest.mark.asyncio
async def test_groq_rate_limit_smart_wait_and_retry_succeeds():
    """All Groq models in cooldown, earliest available_at is 2.0s away (<= max_wait),
    LLMClient waits and retries on Groq successfully without falling back to Ollama."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_valid_key",
        groq_models="model-a, model-b",
        groq_wait_for_rate_limit=True,
        groq_max_rate_limit_wait_seconds=10.0,
        groq_rate_limit_buffer_seconds=0.1,
        llm_fallback_on_rate_limit=True,
        vasukisquare_mock_mode=True,
    )
    client = LLMClient(settings=settings)

    call_count = 0

    def fake_get_chat_model(temperature=None, provider=None, model_name=None):
        nonlocal call_count
        call_count += 1
        mock_llm = MagicMock()
        mock_structured = MagicMock()

        if call_count == 1:
            # model-a 429
            mock_structured.ainvoke = AsyncMock(side_effect=Exception("429 Rate limit. Try again in 0.2s"))
        elif call_count == 2:
            # model-b 429
            mock_structured.ainvoke = AsyncMock(side_effect=Exception("429 Rate limit. Try again in 0.5s"))
        else:
            # retry on earliest model succeeds!
            mock_structured.ainvoke = AsyncMock(return_value=SampleSchema(title="Retry Success"))

        mock_llm.with_structured_output.return_value = mock_structured
        return mock_llm

    with patch.object(client, "get_chat_model", side_effect=fake_get_chat_model):
        res = await client.invoke_structured(
            schema=SampleSchema,
            system_prompt="sys",
            user_prompt="usr",
            stage="test_stage",
        )

    assert res.title == "Retry Success"
    assert call_count == 3
    assert client.metrics.fallback_occurred is False


@pytest.mark.asyncio
async def test_groq_rate_limit_wait_exceeds_max_falls_back_to_ollama():
    """Earliest available_at is 120s away (> max_wait), LLMClient does NOT wait and falls back to Ollama."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_valid_key",
        groq_models="model-a",
        groq_wait_for_rate_limit=True,
        groq_max_rate_limit_wait_seconds=10.0,
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
            mock_structured.ainvoke = AsyncMock(side_effect=Exception("429 Rate limit. Try again in 120.0s"))
        else:
            mock_structured.ainvoke = AsyncMock(return_value=SampleSchema(title="Ollama Handled"))

        mock_llm.with_structured_output.return_value = mock_structured
        return mock_llm

    with patch.object(client, "get_chat_model", side_effect=fake_get_chat_model):
        res = await client.invoke_structured(
            schema=SampleSchema,
            system_prompt="sys",
            user_prompt="usr",
            stage="test_stage",
        )

    assert res.title == "Ollama Handled"
    assert ("groq", "model-a") in providers_called
    assert ("ollama", "qwen2.5:7b-instruct") in providers_called
    assert client.metrics.fallback_occurred is True


# =========================================================================
# 2. OTPM & Context Length Limits
# =========================================================================

def test_otpm_context_limit_error_skips_model_immediately():
    """Request too large / OTPM Limit error is classified as is_impossible_limit=True."""
    err1 = Exception("Request too large for model ... on limit tokens per minute (TPM): Limit 30000, Requested 45000")
    info1 = is_retryable_groq_error(err1)
    assert info1.is_retryable is True
    assert info1.is_impossible_limit is True
    assert info1.is_rate_limit is False

    err2 = Exception("maximum context length exceeded for model")
    info2 = is_retryable_groq_error(err2)
    assert info2.is_impossible_limit is True


# =========================================================================
# 3. Structured Output Recovery
# =========================================================================

@pytest.mark.asyncio
async def test_structured_output_error_same_model_recovery_first():
    """First structured output error triggers same-model retry with stricter instructions."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_valid_key",
        groq_models="model-1, model-2",
        groq_model_fallback=True,
        vasukisquare_mock_mode=True,
    )
    client = LLMClient(settings=settings)

    call_history = []

    def fake_get_chat_model(temperature=None, provider=None, model_name=None):
        mock_llm = MagicMock()
        mock_structured = MagicMock()

        async def fake_ainvoke(msgs):
            call_history.append((model_name, [m.content for m in msgs]))
            if len(call_history) == 1:
                raise ValueError("tool_use_failed: Failed to parse tool call arguments as JSON")
            return SampleSchema(title="Recovered On Same Model")

        mock_structured.ainvoke = AsyncMock(side_effect=fake_ainvoke)
        mock_llm.with_structured_output.return_value = mock_structured
        return mock_llm

    with patch.object(client, "get_chat_model", side_effect=fake_get_chat_model):
        res = await client.invoke_structured(
            schema=SampleSchema,
            system_prompt="Base System",
            user_prompt="Write page",
            stage="test_stage",
        )

    assert res.title == "Recovered On Same Model"
    assert len(call_history) == 2
    assert call_history[0][0] == "model-1"
    assert call_history[1][0] == "model-1"
    assert "CRITICAL: Output strictly valid JSON" in call_history[1][1][0]
    # Verify model-1 is NOT in cooldown
    assert not client.groq_pool.is_in_cooldown("model-1")


@pytest.mark.asyncio
async def test_structured_output_error_two_failures_failover_next_model():
    """Model fails structured retry twice, client fails over to next candidate model without cooldown."""
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        groq_api_key="gsk_valid_key",
        groq_models="model-1, model-2",
        groq_model_fallback=True,
        vasukisquare_mock_mode=True,
    )
    client = LLMClient(settings=settings)

    models_called = []

    def fake_get_chat_model(temperature=None, provider=None, model_name=None):
        mock_llm = MagicMock()
        mock_structured = MagicMock()

        async def fake_ainvoke(msgs):
            models_called.append(model_name)
            if model_name == "model-1":
                raise ValueError("ValidationError: invalid json formatting")
            return SampleSchema(title="Model 2 Succeeded")

        mock_structured.ainvoke = AsyncMock(side_effect=fake_ainvoke)
        mock_llm.with_structured_output.return_value = mock_structured
        return mock_llm

    with patch.object(client, "get_chat_model", side_effect=fake_get_chat_model):
        res = await client.invoke_structured(
            schema=SampleSchema,
            system_prompt="Base System",
            user_prompt="Write page",
            stage="test_stage",
        )

    assert res.title == "Model 2 Succeeded"
    # model-1 called twice (initial + recovery retry), then failover to model-2
    assert models_called == ["model-1", "model-1", "model-2"]
    assert not client.groq_pool.is_in_cooldown("model-1")


# =========================================================================
# 4. Color Token Normalization & Lucide Icons
# =========================================================================

def test_normalize_design_color_valid_tokens_and_hex():
    """normalize_design_color safely maps ColorToken, member names, and hex strings without raising ValueError."""
    # Enum member
    assert normalize_design_color(ColorToken.BRAND_GREEN) == ColorToken.BRAND_GREEN

    # Direct hex
    assert normalize_design_color("#00ed64") == ColorToken.BRAND_GREEN
    assert normalize_design_color("#00a35c") == ColorToken.BRAND_GREEN_MID
    assert normalize_design_color("#fa6e39") == ColorToken.ACCENT_ORANGE

    # Member name strings
    assert normalize_design_color("BRAND_GREEN") == ColorToken.BRAND_GREEN
    assert normalize_design_color("accent-purple") == ColorToken.ACCENT_PURPLE

    # Unknown string falls back cleanly
    assert normalize_design_color("unknown-color", fallback_token=ColorToken.BRAND_GREEN) == ColorToken.BRAND_GREEN


def test_lucide_icon_accepts_raw_hex_and_tokens():
    """LucideIcon and render_lucide_icon instantiate and render cleanly with raw hex strings."""
    icon1 = LucideIcon(name="database", color="#00ed64")
    svg1 = icon1.to_svg()
    assert "data-token-color=" in svg1
    assert "#00ed64" in svg1

    svg2 = render_lucide_icon(name="cpu", color="#00a35c")
    assert "<svg" in svg2
    assert "#00a35c" in svg2


# =========================================================================
# 5. Multi-Factor Content Density Validation & Enrichment
# =========================================================================

def test_multi_factor_content_density_scoring():
    """count_page_words accurately counts words across text, callouts, code, tables, steps, and comparisons."""
    page_content = PageContent(
        headline="Understanding Architecture Components",
        body="Introductory prose describing the architectural patterns and distributed systems.",
        blocks=[
            TextBlock(text="Detailed paragraph explaining runtime behaviors and execution metrics."),
            CodeBlock(language="python", code="def compute(val: int) -> int:\n    return val * 2\n"),
            CalloutBlock(title="Important Rule", content="Ensure strict thread isolation."),
            TableBlock(caption="Performance Table", columns=["Feature", "Cost"], rows=[["Compute", "$10"], ["Storage", "$5"]]),
            ComparisonBlock(title="Do vs Dont", left_title="Do", left_items=["Use pooling"], right_title="Dont", right_items=["Leak connections"]),
            TerminalBlock(title="Terminal", lines=[TerminalLine(kind="command", text="python main.py --run")]),
            StepBlock(title="Installation Procedure", steps=[{"step_number": 1, "title": "Setup", "description": "Install dependencies."}]),
        ],
    )
    word_count = count_page_words(page_content)
    assert word_count > 40


def test_page_content_validation_and_enrichment():
    """validate_page_content flags sparse content (< 220 words) for expansion."""
    sparse_content = PageContent(
        headline="Brief Topic",
        body="Short paragraph of only a few words.",
    )
    res = validate_page_content(sparse_content, page_type="content", min_words=220)
    assert res.is_valid is False
    assert res.needs_expansion is True
    assert "below minimum density threshold" in res.issues[0]


# =========================================================================
# 6. Checkpoints and Resumability
# =========================================================================

@pytest.mark.asyncio
async def test_checkpoint_creation_after_stages_and_pages(tmp_path: Path):
    """Pipeline writes checkpoints for intent, research, book_plan, cover_plan, and pages."""
    settings = Settings(
        _env_file=None,
        vasukisquare_mock_mode=True,
    )
    pipeline = EbookGenerationPipeline(settings=settings)

    state = await pipeline.run(
        topic="Modern Data Architecture",
        target_pages=10,
        output_dir=tmp_path,
        generate_pdf=False,
        persist_db=False,
        resume=False,
    )

    checkpoints_dir = tmp_path / "checkpoints"
    assert (checkpoints_dir / "intent.json").exists()
    assert (checkpoints_dir / "research.json").exists()
    assert (checkpoints_dir / "book_plan.json").exists()
    assert (checkpoints_dir / "cover_plan.json").exists()

    pages_dir = checkpoints_dir / "pages"
    assert (pages_dir / "page_001.json").exists()
    assert (pages_dir / "page_002.json").exists()
    assert len(list(pages_dir.glob("page_*.json"))) == len(state.pages)


@pytest.mark.asyncio
async def test_pipeline_resumes_from_existing_checkpoints(tmp_path: Path):
    """Pipeline with resume=True loads saved stages and page checkpoints without re-generating them."""
    settings = Settings(
        _env_file=None,
        vasukisquare_mock_mode=True,
    )
    pipeline = EbookGenerationPipeline(settings=settings)

    # Initial run creates checkpoints
    await pipeline.run(
        topic="Modern Data Architecture",
        target_pages=10,
        output_dir=tmp_path,
        generate_pdf=False,
        persist_db=False,
        resume=False,
    )

    # Second run with resume=True
    with patch.object(pipeline.editorial_agent, "infer_intent", side_effect=Exception("Should not be called")):
        with patch.object(pipeline.research_service, "research_topic", side_effect=Exception("Should not be called")):
            with patch.object(pipeline.writer_agent, "write_page", side_effect=Exception("Should not be called")):
                state_resumed = await pipeline.run(
                    topic="Modern Data Architecture",
                    target_pages=10,
                    output_dir=tmp_path,
                    generate_pdf=False,
                    persist_db=False,
                    resume=True,
                )

    assert state_resumed is not None
    assert len(state_resumed.pages) > 0


@pytest.mark.asyncio
async def test_corrupted_checkpoint_recovery(tmp_path: Path):
    """Corrupted page checkpoint is gracefully handled by logging warning and regenerating page."""
    settings = Settings(
        _env_file=None,
        vasukisquare_mock_mode=True,
    )
    pipeline = EbookGenerationPipeline(settings=settings)

    # Initial run
    await pipeline.run(
        topic="Corrupted Checkpoint Test",
        target_pages=10,
        output_dir=tmp_path,
        generate_pdf=False,
        persist_db=False,
        resume=False,
    )

    # Corrupt page_002.json
    corrupted_page = tmp_path / "checkpoints" / "pages" / "page_002.json"
    corrupted_page.write_text("{corrupted invalid json...", encoding="utf-8")

    # Resumed run should recover
    state = await pipeline.run(
        topic="Corrupted Checkpoint Test",
        target_pages=10,
        output_dir=tmp_path,
        generate_pdf=False,
        persist_db=False,
        resume=True,
    )
    assert len(state.pages) > 0
    assert state.pages[1].page_number == 2


# =========================================================================
# 7. Model Pool Available_At Tracking
# =========================================================================

def test_pool_available_at_tracking_and_earliest_wait():
    """GroqModelPool correctly tracks available_at per model and calculates earliest wait time."""
    pool = GroqModelPool(["model-a", "model-b", "model-c"], cooldown_seconds=60.0)

    # Initially all available immediately
    m, wait = pool.get_earliest_available_wait()
    assert wait == 0.0

    # Put model-a on 10s cooldown, model-b on 5s cooldown
    pool.record_failure("model-a", Exception("429"), is_rate_limit=True, retry_after=10.0)
    pool.record_failure("model-b", Exception("429"), is_rate_limit=True, retry_after=5.0)

    earliest_m, earliest_wait = pool.get_earliest_available_wait(["model-a", "model-b"])
    assert earliest_m == "model-b"
    assert 0.0 < earliest_wait <= 5.0


# =========================================================================
# 8. Page Writer Retries and Metrics Persistence
# =========================================================================

@pytest.mark.asyncio
async def test_writer_retries_transient_failure_and_succeeds():
    """PageWriterAgent._generate_content_page retries when _llm_write_page fails once, avoiding fallback."""
    from vasukisquare.agents.writer import PageWriterAgent
    from vasukisquare.llm.metrics import BookGenerationMetrics

    metrics = BookGenerationMetrics()
    settings = Settings(
        _env_file=None,
        vasukisquare_mock_mode=False,
    )
    writer = PageWriterAgent(settings=settings, metrics=metrics)

    attempts = 0

    async def fake_llm_write_page(p, plan, corpus):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise Exception("Transient network blip on first attempt")
        return PageContent(
            headline="Successful LLM Page",
            blocks=[TextBlock(text="This page was generated successfully after retry.")],
        )

    with patch.object(writer, "_llm_write_page", side_effect=fake_llm_write_page):
        plan = BookPlan(
            title="Database Architecture",
            subtitle="Internal Guide",
            description="DB internals",
            intent=BookIntent(topic="Databases", target_audience="Engineers"),
        )
        p = PlannedPage(
            page_number=6,
            page_type="chapter_content",
            layout="editorial_standard",
            chapter_number=1,
            chapter_title="Storage",
            brief="Page Layout",
        )
        content = await writer._generate_content_page(p, plan, citations=[])

    assert attempts == 2
    assert metrics.fallback_pages == 0
    assert metrics.pages_generated_by_llm == 1
    assert content.headline == "Successful LLM Page"


