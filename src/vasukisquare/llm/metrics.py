"""Metrics tracking and observability models for VasukiSquare generation pipeline."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GroqMetrics(BaseModel):
    """Metrics specifically tracking Groq LLM invocations."""

    calls: int = 0
    model: str = ""
    failures: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_duration_seconds: float = 0.0
    calls_by_stage: Dict[str, int] = Field(default_factory=dict)


class ResearchMetrics(BaseModel):
    """Metrics tracking internet search, retrieval, and source grounding."""

    provider: str = "mock"
    web_search_calls: int = 0
    wikipedia_calls: int = 0
    webpage_fetch_calls: int = 0
    sources_retrieved: int = 0
    sources_accepted: int = 0
    sources_used: int = 0
    queries_planned: List[str] = Field(default_factory=list)


class BookGenerationMetrics(BaseModel):
    """Complete per-book generation telemetry and observability metrics."""

    topic: str = ""
    target_pages: int = 0
    pages_total: int = 0
    pages_generated_by_llm: int = 0
    fallback_pages: int = 0
    mock_mode: bool = False

    # LLM Telemetry
    llm_provider: str = "groq"
    llm_model: str = ""
    llm_calls_total: int = 0
    llm_calls_by_stage: Dict[str, int] = Field(default_factory=dict)
    llm_failures: int = 0
    fallback_occurred: bool = False
    fallback_reason: Optional[str] = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_duration_seconds: float = 0.0

    # Backwards compatibility sub-models
    groq: GroqMetrics = Field(default_factory=GroqMetrics)
    research: ResearchMetrics = Field(default_factory=ResearchMetrics)

    @property
    def web_search_calls(self) -> int:
        return self.research.web_search_calls

    @property
    def sources_retrieved(self) -> int:
        return self.research.sources_retrieved

    @property
    def sources_accepted(self) -> int:
        return self.research.sources_accepted

    @property
    def sources_used(self) -> int:
        return self.research.sources_used

    def record_llm_call(
        self,
        stage: str,
        model: str,
        duration: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        provider: str = "groq",
        success: bool = True,
    ) -> None:
        """Record an individual LLM execution."""
        self.llm_provider = provider
        self.llm_model = model
        self.llm_calls_total += 1
        self.llm_calls_by_stage[stage] = self.llm_calls_by_stage.get(stage, 0) + 1
        self.total_duration_seconds += duration
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += (prompt_tokens + completion_tokens)

        if not success:
            self.llm_failures += 1

        # Keep groq submodel in sync for legacy references
        if provider == "groq":
            self.groq.calls += 1
            self.groq.model = model
            self.groq.total_duration_seconds += duration
            self.groq.total_prompt_tokens += prompt_tokens
            self.groq.total_completion_tokens += completion_tokens
            self.groq.calls_by_stage[stage] = self.groq.calls_by_stage.get(stage, 0) + 1
            if not success:
                self.groq.failures += 1

    def record_web_search(self, count: int = 1, provider: Optional[str] = None) -> None:
        """Record a web search query execution."""
        self.research.web_search_calls += count
        if provider:
            self.research.provider = provider

    def record_wikipedia_call(self, count: int = 1) -> None:
        """Record a Wikipedia API query."""
        self.research.wikipedia_calls += count

    def record_webpage_fetch(self, count: int = 1) -> None:
        """Record a webpage HTML fetch & extraction."""
        self.research.webpage_fetch_calls += count

    def record_page_generated_by_llm(self) -> None:
        """Record a page successfully authored by LLM."""
        self.pages_generated_by_llm += 1

    def record_fallback_page(self) -> None:
        """Record a page produced via fallback."""
        self.fallback_pages += 1

    def summary_string(self) -> str:
        """Format metrics as a human-readable CLI summary."""
        tps = (
            f"{self.total_completion_tokens / self.total_duration_seconds:.1f} tok/s"
            if self.total_duration_seconds > 0 and self.total_completion_tokens > 0
            else "N/A"
        )
        lines = [
            "Generation Metrics:",
            f"  LLM Provider: {self.llm_provider.upper()} (Model: {self.llm_model or 'None'})",
            f"  LLM Calls: {self.llm_calls_total} (Failures: {self.llm_failures})",
            f"  Total Tokens: {self.total_tokens} (Prompt: {self.total_prompt_tokens}, Completion: {self.total_completion_tokens}, Speed: {tps})",
            f"  Web searches: {self.research.web_search_calls} (Provider: {self.research.provider})",
            f"  Wikipedia calls: {self.research.wikipedia_calls}",
            f"  Webpage fetches: {self.research.webpage_fetch_calls}",
            f"  Research sources retrieved: {self.research.sources_retrieved}",
            f"  Research sources accepted: {self.research.sources_accepted}",
            f"  Research sources used: {self.research.sources_used}",
            f"  Pages generated by LLM: {self.pages_generated_by_llm}",
            f"  Fallback pages used: {self.fallback_pages}",
        ]
        if self.fallback_occurred:
            lines.append(f"  Provider Fallback: Triggered ({self.fallback_reason})")
        return "\n".join(lines)

