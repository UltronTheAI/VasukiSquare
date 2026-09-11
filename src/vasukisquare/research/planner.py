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


class ResearchPlanner:
    """Produces multi-perspective research queries using Groq/LangChain with offline heuristic fallback."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def _generate_fallback_plan(self, prompt: str) -> ResearchPlan:
        """Generate structured multi-perspective research plan deterministically without external LLM."""
        topic = prompt.strip()
        queries = [
            ResearchQuery(
                query=f"{topic} overview definition fundamentals",
                perspective="foundations",
                target_source_types=[SourceType.WIKIPEDIA, SourceType.WEB],
                priority=1,
            ),
            ResearchQuery(
                query=f"{topic} architecture technical specifications",
                perspective="architecture",
                target_source_types=[SourceType.DOCUMENTATION, SourceType.ACADEMIC, SourceType.WEB],
                priority=1,
            ),
            ResearchQuery(
                query=f"{topic} practical implementation code guide tutorial",
                perspective="implementation",
                target_source_types=[SourceType.DOCUMENTATION, SourceType.BLOG],
                priority=2,
            ),
            ResearchQuery(
                query=f"{topic} benchmarks performance comparison trade-offs",
                perspective="benchmarks",
                target_source_types=[SourceType.BLOG, SourceType.ACADEMIC, SourceType.WEB],
                priority=2,
            ),
            ResearchQuery(
                query=f"{topic} production deployment best practices case studies",
                perspective="production",
                target_source_types=[SourceType.DOCUMENTATION, SourceType.BLOG, SourceType.NEWS],
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
        return ResearchPlan(topic=topic, queries=queries, perspective_goals=goals)

    async def plan_research(self, prompt: str) -> ResearchPlan:
        """Create a multi-perspective research plan."""
        if not self.settings.groq_api_key:
            return self._generate_fallback_plan(prompt)

        try:
            from langchain_groq import ChatGroq
            from langchain_core.prompts import ChatPromptTemplate

            llm = ChatGroq(
                api_key=self.settings.groq_api_key,
                model_name=self.settings.groq_model,
                temperature=0.2,
            )
            structured_llm = llm.with_structured_output(ResearchPlan)

            system_prompt = (
                "You are an expert technical researcher preparing an exhaustive research dossier for a technical ebook. "
                "Decompose the user topic into 4 to 6 focused search queries covering multiple perspectives: "
                "1. Foundations/Theory, 2. Core Architecture, 3. Implementation/Code, 4. Benchmarks/Trade-offs, 5. Production Case Studies. "
                "Explicitly designate target source types (documentation, academic, web, wikipedia, blog, news) for each query."
            )

            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "Topic to research: {topic}"),
            ])

            chain = prompt_template | structured_llm
            result = await chain.ainvoke({"topic": prompt})
            if isinstance(result, ResearchPlan) and result.queries:
                return result
            return self._generate_fallback_plan(prompt)
        except Exception as e:
            logger.warning(f"Groq research planning invocation failed, falling back to deterministic plan: {e}")
            return self._generate_fallback_plan(prompt)

