"""End-to-end research service orchestrating query planning, ingestion, deduplication, and ranking."""

import asyncio
import logging
from typing import List, Optional
from vasukisquare.config import Settings, get_settings
from vasukisquare.research.models import (
    ResearchCorpus,
    ResearchPlan,
    SourceDocument,
    SourceType,
)
from vasukisquare.research.planner import ResearchPlanner
from vasukisquare.research.deduplication import DeduplicationService
from vasukisquare.research.ranking import SourceRanker
from vasukisquare.tools.search import WebSearchTool, SearchParams, MockSearchProvider, TavilySearchProvider, SerperSearchProvider
from vasukisquare.tools.wikipedia import WikipediaTool, WikipediaParams

logger = logging.getLogger(__name__)


class ResearchService:
    """Orchestrates multi-perspective research generation for book topics."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        search_tool: Optional[WebSearchTool] = None,
        wikipedia_tool: Optional[WikipediaTool] = None,
        planner: Optional[ResearchPlanner] = None,
        deduplicator: Optional[DeduplicationService] = None,
        ranker: Optional[SourceRanker] = None,
    ):
        self.settings = settings or get_settings()
        self.planner = planner or ResearchPlanner(self.settings)
        self.deduplicator = deduplicator or DeduplicationService(near_duplicate_threshold=0.80)
        self.ranker = ranker or SourceRanker()

        # Configure search tool provider based on settings
        if search_tool:
            self.search_tool = search_tool
        elif self.settings.tavily_api_key:
            self.search_tool = WebSearchTool(TavilySearchProvider(self.settings.tavily_api_key))
        elif self.settings.serper_api_key:
            self.search_tool = WebSearchTool(SerperSearchProvider(self.settings.serper_api_key))
        else:
            self.search_tool = WebSearchTool(MockSearchProvider())

        self.wikipedia_tool = wikipedia_tool or WikipediaTool()

    async def execute_query(self, query_text: str, target_types: List[SourceType]) -> List[SourceDocument]:
        """Execute a single query across appropriate tools."""
        collected: List[SourceDocument] = []
        tasks = []

        # Wikipedia orientation
        if SourceType.WIKIPEDIA in target_types:
            tasks.append(self.wikipedia_tool.execute(WikipediaParams(query=query_text, max_results=2)))

        # Web search
        tasks.append(self.search_tool.execute(SearchParams(query=query_text, max_results=self.settings.research_max_pages_per_source)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                collected.extend(res)
            elif isinstance(res, Exception):
                logger.warning(f"Error executing research query '{query_text}': {res}")

        return collected

    async def research_topic(self, topic: str) -> ResearchCorpus:
        """Run full deep research pipeline on a topic."""
        # 1. Plan queries
        plan: ResearchPlan = await self.planner.plan_research(topic)

        # 2. Ingest documents across queries
        all_raw_docs: List[SourceDocument] = []
        queries_executed: List[str] = []

        for q in plan.queries:
            queries_executed.append(q.query)
            docs = await self.execute_query(q.query, q.target_source_types)
            all_raw_docs.extend(docs)

        # 3. Deduplicate exact and near-duplicates
        deduped_docs = self.deduplicator.deduplicate(all_raw_docs)

        # 4. Rank documents by authority and source type
        ranked_docs = self.ranker.rank(deduped_docs)

        # 5. Apply max source limit
        final_docs = ranked_docs[: self.settings.research_max_sources]

        # 6. Extract key findings / summary highlights
        key_findings = [f"{d.title} ({d.domain})" for d in final_docs[:5]]

        return ResearchCorpus(
            topic=topic,
            documents=final_docs,
            queries_executed=queries_executed,
            key_findings=key_findings,
        )

