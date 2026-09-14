"""Unit tests for small model pipeline, validators, full bleed cover, and decomposed writer."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from vasukisquare.config import Settings
from vasukisquare.book.layout import LayoutType, TechnicalPageType, TechnicalPageSpec, PAGE_TYPE_SPECS
from vasukisquare.book.components import TerminalBlock, TerminalLine, CodeBlock, CalloutBlock, TextBlock, TableBlock
from vasukisquare.book.models import BookPlan, BookIntent, PageContent, PlannedPage, PlannedChapter, CoverDesignPlan
from vasukisquare.agents.content_validator import (
    validate_terminal_command,
    validate_code_block,
    detect_topic_drift,
    evaluate_technical_page,
    validate_page_content,
)
from vasukisquare.agents.technical_content import (
    TopicClassification,
    classify_topic,
    extract_chapter_research,
)
from vasukisquare.agents.writer import (
    PageWriterAgent,
    SmallModelHeadlineLead,
    SmallModelTroubleshooting,
)
from vasukisquare.renderer.cover import CoverRenderer


def test_small_model_mode_detection():
    """Test auto detection of small models (0.5b, 1b, 3b, etc.)."""
    s1 = Settings(GROQ_API_KEY="", LLM_PROVIDER="ollama", OLLAMA_MODEL="qwen2.5:0.5b")
    assert s1.is_small_model_active is True

    s2 = Settings(GROQ_API_KEY="", LLM_PROVIDER="ollama", OLLAMA_MODEL="llama3.2:1b")
    assert s2.is_small_model_active is True

    s3 = Settings(GROQ_API_KEY="test_key", LLM_PROVIDER="groq", GROQ_MODEL="openai/gpt-oss-120b")
    assert s3.is_small_model_active is False

    s4 = Settings(GROQ_API_KEY="test_key", SMALL_MODEL_MODE="true")
    assert s4.is_small_model_active is True

    s5 = Settings(GROQ_API_KEY="", LLM_PROVIDER="ollama", OLLAMA_MODEL="qwen2.5:0.5b", SMALL_MODEL_MODE="false")
    assert s5.is_small_model_active is False


def test_validate_terminal_command():
    """Test that actual shell commands are accepted and conversational prose is rejected."""
    # Valid shell commands
    assert validate_terminal_command("npm install @liorandb/cli") is True
    assert validate_terminal_command("pip install lioran") is True
    assert validate_terminal_command("docker run -d -p 8080:8080 --name liorandb lioran/server:latest") is True
    assert validate_terminal_command("python -m venv .venv && source .venv/bin/activate") is True
    assert validate_terminal_command("# Setup environment\ncurl -fsSL https://get.lioran.dev | sh") is True
    assert validate_terminal_command("lioran status --verbose") is True

    # Invalid conversational prose
    assert validate_terminal_command("In this example we will install LioranDB by downloading it from the official website.") is False
    assert validate_terminal_command("First install the package using the package manager.") is False
    assert validate_terminal_command("LioranDB is a high-performance database designed for fast lookups.") is False
    assert validate_terminal_command("") is False


def test_validate_code_block():
    """Test that actual source code is accepted and conversational prose is rejected."""
    # Valid Python & JS code
    py_code = "import lioran\n\nclient = lioran.Client()\nres = client.query('users')\nprint(res)"
    assert validate_code_block(py_code, "python") is True

    ts_code = "import { LioranClient } from '@lioran/sdk';\nconst client = new LioranClient({ port: 8080 });\nawait client.connect();"
    assert validate_code_block(ts_code, "typescript") is True

    json_code = '{\n  "engine": "liorandb",\n  "port": 8080,\n  "enabled": true\n}'
    assert validate_code_block(json_code, "json") is True

    # Invalid prose paragraphs
    prose = "Here is how you can use the database in your application. First you must initialize the client and then you can call methods."
    assert validate_code_block(prose, "python") is False
    assert validate_code_block("", "python") is False


def test_detect_topic_drift():
    """Test detection of hallucinated zero-knowledge cryptography when topic is beginner level."""
    # Book is about LioranDB for beginners ("From Zero Knowledge")
    text_with_zk = "LioranDB utilizes zero-knowledge proofs and zk-SNARK algorithms to verify transactional integrity across the cluster."
    drift = detect_topic_drift(text_with_zk, primary_subject="LioranDB", is_beginner=True)
    assert len(drift) > 0
    assert "zero-knowledge cryptography" in drift[0]

    # Clean text with beginner explanation
    clean_text = "LioranDB is an in-memory document database that allows rapid reads and writes through an intuitive API."
    no_drift = detect_topic_drift(clean_text, primary_subject="LioranDB", is_beginner=True)
    assert len(no_drift) == 0

    # Boilerplate detection
    boilerplate = "When implementing database caching, software engineers must balance runtime execution throughput and memory limits."
    bp_drift = detect_topic_drift(boilerplate, primary_subject="LioranDB", is_beginner=True)
    assert len(bp_drift) > 0


def test_evaluate_technical_page_spec():
    """Test evaluating page content against strict technical specs."""
    install_spec = PAGE_TYPE_SPECS[TechnicalPageType.INSTALLATION]

    # Valid installation page with adequate word count
    valid_page = PageContent(
        headline="Installing LioranDB",
        blocks=[
            TextBlock(
                text="To get started with LioranDB, install the CLI binary or Python driver using pip or npm. "
                "Ensure that prerequisites such as Python 3.10+ and a valid C compiler are installed on your host system. "
                "The LioranDB client library connects directly to the daemon socket and manages local connection pools. "
                "Following installation, verify the binary installation by querying the engine version and status."
                "Following installation, verify the binary installation by querying the engine version and status. "
                "Detailed dependency checks help avoid runtime execution errors when bootstrapping database instances. "
                "The installer handles linking shared C extensions and sets up default socket permissions securely. "
                "Make sure that your operating system user account possesses sufficient permissions to create and bind the unix socket domain."
            ),
            TerminalBlock(
                title="Installation",
                shell="bash",
                lines=[
                    TerminalLine(kind="command", text="pip install lioran"),
                    TerminalLine(kind="output", text="Successfully installed lioran-1.0.0"),
                ],
            ),
            TextBlock(
                text="Once installed, configure your environment variables to point to the desired cluster instance or local storage directory. "
                "Testing connectivity early ensures that configuration errors are caught prior to executing complex database transactions. "
                "Always run automated unit tests against the running service to guarantee environment compatibility."
                "Always run automated unit tests against the running service to guarantee environment compatibility. "
                "Make sure system ports are properly exposed in containerized deployments to allow daemon access. "
                "Monitoring network latency during initial connection handshake helps benchmark query overhead. "
                "Verify file system permissions for the embedded storage directory before starting background worker threads. "
                "Proper log rotation policies should also be initialized to prevent unbounded disk usage as database operations scale over time. "
                "You can inspect active connections by calling the telemetry ping endpoint."
            ),
            CalloutBlock(title="Note", content="Requires Python 3.10+ and 512MB RAM minimum for local development."),
            CalloutBlock(title="Note", content="Requires Python 3.10+ and 512MB RAM minimum for local development environments and containerized microservice architectures."),
        ],
    )
    res_valid = evaluate_technical_page(valid_page, install_spec, primary_subject="LioranDB")
    assert res_valid.is_valid is True

    # Invalid installation page (missing terminal command)
    invalid_page = PageContent(
        headline="Installing LioranDB",
        blocks=[
            TextBlock(text="In this chapter we discuss installation theoretically without any commands."),
            CalloutBlock(title="Tip", content="Installation is straightforward."),
        ],
    )
    res_invalid = evaluate_technical_page(invalid_page, install_spec, primary_subject="LioranDB")
    assert res_invalid.is_valid is False
    assert any("TerminalBlock" in issue for issue in res_invalid.issues)


def test_cover_renderer_full_bleed_geometry():
    """Verify that cover page HTML uses full A4 geometry without clipping or shrinking."""
    renderer = CoverRenderer()
    plan = CoverDesignPlan(
        title="LioranDB for Noobs",
        subtitle="From Zero Knowledge to Real Apps",
        composition_style="asymmetric_left",
        accent_color="#00ed64",
        background_color="#001e2b",
        category="Database Engineering",
        author="VasukiSquare AI",
    )
    page = renderer.render_a4_cover_page(plan, book_id="lioran-book")
    assert page.layout == LayoutType.COVER.value
    assert "background-color: #001e2b" in page.html
    assert "297mm" in page.html
    assert "VASUKISQUARE" in page.html
    assert "VasukiSquare AI" in page.html


@pytest.mark.asyncio
async def test_small_model_decomposed_writer():
    """Test that PageWriterAgent decomposes small model generation and injects verified components."""
    settings = Settings(
        GROQ_API_KEY="",
        LLM_PROVIDER="ollama",
        OLLAMA_MODEL="qwen2.5:0.5b",
        SMALL_MODEL_MODE="true",
        VASUKISQUARE_MOCK_MODE=False,
    )
    mock_llm = MagicMock()

    # Mock small model responses for headline and tip
    async def mock_invoke_structured(schema, **kwargs):
        if schema == SmallModelHeadlineLead:
            return SmallModelHeadlineLead(
                headline="Setting Up LioranDB Locally",
                explanation="LioranDB is a lightweight embedded database engine. Running local tests allows rapid verification of the client connection and schema configuration.",
            )
        elif schema == SmallModelTroubleshooting:
            return SmallModelTroubleshooting(
                callout_title="Connection Tip",
                callout_text="Ensure port 8080 is available before launching the engine.",
                callout_variant="tip",
            )
        return None

    mock_llm.invoke_structured = AsyncMock(side_effect=mock_invoke_structured)

    agent = PageWriterAgent(settings=settings, llm_client=mock_llm)
    planned_page = PlannedPage(
        page_number=3,
        page_type=TechnicalPageType.INSTALLATION.value,
        layout=LayoutType.EDITORIAL.value,
        chapter_number=1,
        chapter_title="Getting Started",
        brief="Installation & Quickstart",
    )
    plan = BookPlan(
        title="LioranDB for Noobs: From Zero Knowledge to Building Real Apps with LioranDB",
        subtitle="A Comprehensive Practical Guide",
        description="Learn LioranDB from scratch",
        intent=BookIntent(
            primary_programming_language="python",
            domain_topic="LioranDB",
            technical_depth="introductory",
        ),
        chapters=[PlannedChapter(chapter_number=1, title="Getting Started", summary="Intro", page_budget=6)],
    )

    page = await agent.write_page(planned_page, plan)

    assert page.page_number == 3
    assert page.content.headline == "Setting Up LioranDB Locally"
    # Verify TerminalBlock was injected
    assert any(isinstance(b, TerminalBlock) for b in page.content.blocks)
    # Verify CalloutBlock was injected
    assert any(isinstance(b, CalloutBlock) for b in page.content.blocks)
    # Verify no ZK cryptography drift
    full_text = " ".join([b.text for b in page.content.blocks if hasattr(b, "text")])
    assert "zero-knowledge proof" not in full_text.lower()
