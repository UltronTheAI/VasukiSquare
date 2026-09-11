"""Research planner decomposing book prompts into multi-perspective research queries."""

import logging
from typing import Optional
from vasukisquare.config import Settings, get_settings
from vasukisquare.research.models import (
    ResearchPlan,
    ResearchQuery,
    SourceType,
)

logger = logging.getLogger(__name__)


from vasukisquare.llm.client import LLMClient, GroqGenerationError
from vasukisquare.llm.metrics import BookGenerationMetrics

logger = logging.getLogger(__name__)


class ResearchPlanner:
    """Produces multi-perspective research queries using Groq/LangChain."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[LLMClient] = None,
        metrics: Optional[BookGenerationMetrics] = None,
    ):
        self.settings = settings or get_settings()
        self.metrics = metrics or BookGenerationMetrics()
        self.llm_client = llm_client or LLMClient(self.settings, self.metrics)

    def _extract_subject(self, prompt: str) -> str:
        """Extract core subject keyword from verbose title."""
        # e.g. "LioranDB for Noobs: From Zero Knowledge..." -> "LioranDB"
        main_part = prompt.split(":")[0].split("–")[0].split("-")[0].strip()
        stop_words = {"getting", "started", "with", "guide", "handbook", "complete", "for", "noobs", "beginners", "from", "zero"}
        words = [w for w in main_part.split() if w.lower() not in stop_words]
        return " ".join(words) if words else main_part

    def _generate_fallback_plan(self, prompt: str) -> ResearchPlan:
        """Generate structured multi-perspective research plan deterministically for mock mode."""
        subject = self._extract_subject(prompt)
        queries = [
            ResearchQuery(
                query=f"{subject} official documentation overview",
                perspective="foundations",
                target_source_types=[SourceType.DOCUMENTATION, SourceType.WEB],
                priority=1,
            ),
            ResearchQuery(
                query=f"{subject} architecture GitHub repository",
                perspective="architecture",
                target_source_types=[SourceType.DOCUMENTATION, SourceType.WEB],
                priority=1,
            ),
            ResearchQuery(
                query=f"{subject} installation setup getting started tutorial",
                perspective="implementation",
                target_source_types=[SourceType.DOCUMENTATION, SourceType.BLOG],
                priority=2,
            ),
            ResearchQuery(
                query=f"{subject} API usage code examples CRUD operations",
                perspective="implementation",
                target_source_types=[SourceType.DOCUMENTATION, SourceType.BLOG],
                priority=2,
            ),
            ResearchQuery(
                query=f"{subject} deployment benchmarks production best practices",
                perspective="production",
                target_source_types=[SourceType.DOCUMENTATION, SourceType.WEB],
                priority=3,
            ),
        ]
        goals = {
            "foundations": "Understand terminology, history, and theoretical baseline.",
            "architecture": "Capture internal mechanics, data structures, and protocol specs.",
            "implementation": "Gather clean code samples and integration workflows.",
            "benchmarks": "Identify throughput/latency metrics and architectural trade-offs.",
            "production": "Analyze real-world post-mortems, scaling limits, and best practices.",
        }
        return ResearchPlan(topic=prompt, queries=queries, perspective_goals=goals)

    async def plan_research(self, prompt: str) -> ResearchPlan:
        """Create a multi-perspective research plan."""
        if self.settings.vasukisquare_mock_mode:
            return self._generate_fallback_plan(prompt)

        system_prompt = (
            "You are an expert technical research director preparing an exhaustive research dossier for a technical ebook.\n"
            "Analyze the book topic and decompose it into 4 to 6 concise, targeted web search queries covering:\n"
            "1. Official documentation & overview\n"
            "2. Architecture, data models & internals\n"
            "3. Installation, CLI, SDKs & getting started\n"
            "4. Practical code examples & API usage\n"
            "5. Deployment, benchmarks & production best practices\n\n"
            "IMPORTANT RULES:\n"
            "- Generate concise search queries (2 to 5 keywords each).\n"
            "- Never copy the entire long book title as a single query.\n"
            "- If the topic is a specific database or tool (e.g. 'LioranDB'), generate queries targeting its official docs, GitHub, SDKs, and CLI.\n"
            "- Explicitly specify target source types (documentation, web, blog, academic, wikipedia) for each query."
        )

        user_prompt = f"Topic to research: {prompt}\n\nGenerate the structured ResearchPlan."

        try:
            plan = await self.llm_client.invoke_structured(
                schema=ResearchPlan,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                stage="research_planning",
                temperature=0.2,
            )
            # Record planned queries into metrics
            self.metrics.research.queries_planned = [q.query for q in plan.queries]
            return plan
        except Exception as e:
            if self.settings.vasukisquare_mock_mode:
                logger.warning(f"Groq research planning invocation failed in mock mode, falling back: {e}")
                return self._generate_fallback_plan(prompt)
            raise GroqGenerationError(f"Research query planning failed via Groq: {e}") from e

