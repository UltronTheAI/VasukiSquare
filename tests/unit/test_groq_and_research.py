"""Unit and regression tests for Groq LLM client prompt construction with arbitrary braces,
research planning structured output, and research service integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import BaseModel, Field
from typing import List, Optional

from vasukisquare.config import Settings
from vasukisquare.llm.client import LLMClient, GroqGenerationError
from vasukisquare.llm.metrics import BookGenerationMetrics
from vasukisquare.research.models import ResearchPlan, ResearchQuery, SourceDocument, SourceType
from vasukisquare.research.planner import ResearchPlanner
from vasukisquare.research.service import ResearchService


class DummyOutputSchema(BaseModel):
    title: str
    summary: str
    tags: List[str] = Field(default_factory=list)


@pytest.mark.asyncio
async def test_llm_client_dynamic_prompt_with_complex_braces():
    """Verify that prompts containing arbitrary braces (JSON, JS, Rust, CSS, Python dicts, etc.)
    do not trigger LangChain template ValueError and pass through safely to the chat model."""
    settings = Settings(
        app_env="test",
        groq_api_key="gsk_test_mock_key",
        groq_model="openai/gpt-oss-120b",
        vasukisquare_mock_mode=True,
    )
    metrics = BookGenerationMetrics()
    client = LLMClient(settings, metrics)

    # 10 Diverse brace-heavy snippets
    json_snippet = '{"name": "LioranDB", "config": {"port": 27018, "auth": true}}'
    js_snippet = 'const server = { host: "127.0.0.1", port: 3000, listeners: [() => {}] };'
    py_snippet = 'config = {"timeout": 30, "headers": {"Authorization": "Bearer {TOKEN}"}}'
    rust_snippet = 'struct Store<T> { data: Arc<RwLock<HashMap<String, T>>>, version: u64 }'
    css_snippet = '@page { size: A4; margin: 0; } .card { padding: 16px; border: 1px solid #333; }'
    mermaid_snippet = 'graph TD\n  A[Client] -->|Request {action}| B(LioranDB Node)\n  B --> C{Quorum?}'
    nested_braces = 'Template syntax: {{item.name}} and {{{raw_html}}} and {escaped}'
    source_excerpts = 'Excerpt from paper: "Let S = { x in X | f(x) > 0 } and kernel K(x, y) = exp(-{gamma}||x - y||^2)"'
    html_with_styles = '<div style="background: rgba(0, 237, 100, 0.1); border-radius: 8px;">{content}</div>'
    mixed_content = (
        f"JSON: {json_snippet}\n"
        f"JS: {js_snippet}\n"
        f"Python: {py_snippet}\n"
        f"Rust: {rust_snippet}\n"
        f"CSS: {css_snippet}\n"
        f"Mermaid: {mermaid_snippet}\n"
        f"Nested: {nested_braces}\n"
        f"Source: {source_excerpts}\n"
        f"HTML: {html_with_styles}"
    )

    system_prompt = f"You are a technical author. Technical rules:\n{css_snippet}\n{json_snippet}"
    user_prompt = f"Research Context:\n{mixed_content}\n\nGenerate structured response."

    # Mock ChatGroq underlying model
    expected_output = DummyOutputSchema(
        title="LioranDB Internals",
        summary="Overview of storage engine and network protocols.",
        tags=["database", "lsm-tree"],
    )

    mock_chat_groq = MagicMock()
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=expected_output)
    mock_chat_groq.with_structured_output.return_value = mock_structured_llm

    client.get_chat_model = MagicMock(return_value=mock_chat_groq)

    # Invoke structured - MUST NOT raise ValueError: unmatched '{' in format spec
    res = await client.invoke_structured(
        schema=DummyOutputSchema,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        stage="test_brace_regression",
    )

    assert isinstance(res, DummyOutputSchema)
    assert res.title == "LioranDB Internals"

    # Verify messages passed to ainvoke were direct SystemMessage and HumanMessage with content preserved
    mock_structured_llm.ainvoke.assert_called_once()
    passed_messages = mock_structured_llm.ainvoke.call_args[0][0]
    assert len(passed_messages) == 2
    assert passed_messages[0].content == system_prompt
    assert passed_messages[1].content == user_prompt
    assert json_snippet in passed_messages[1].content
    assert css_snippet in passed_messages[0].content


@pytest.mark.asyncio
async def test_research_planner_with_mock_and_structured_output():
    """Verify ResearchPlanner generates multi-perspective queries correctly."""
    settings = Settings(
        app_env="test",
        groq_api_key="gsk_test_mock_key",
        vasukisquare_mock_mode=True,
    )
    planner = ResearchPlanner(settings)
    plan = await planner.plan_research("LioranDB for Noobs: From Zero Knowledge to Building Real Apps")

    assert plan.topic == "LioranDB for Noobs: From Zero Knowledge to Building Real Apps"
    assert len(plan.queries) >= 4
    for q in plan.queries:
        assert isinstance(q.query, str)
        assert len(q.target_source_types) > 0


def test_research_query_schema_supports_arbitrary_source_type_strings():
    """Verify ResearchQuery accepts varied source type strings without enum validation failures."""
    query = ResearchQuery(
        query="LioranDB GitHub repository source code",
        perspective="implementation",
        target_source_types=["github", "documentation", "forum", "blog", "web"],
        priority=1,
    )
    assert "github" in query.target_source_types
    assert "forum" in query.target_source_types

    plan = ResearchPlan(
        topic="LioranDB",
        queries=[query],
        perspective_goals={"implementation": "Gather source code samples"},
    )
    json_data = plan.model_dump_json()
    assert "github" in json_data

