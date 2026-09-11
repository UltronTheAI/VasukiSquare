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
from vasukisquare.tools.search import (
    WebSearchTool,
    SearchParams,
    MockSearchProvider,
    TavilySearchProvider,
    SerperSearchProvider,
    BraveSearchProvider,
)
from vasukisquare.tools.fetcher import WebpageFetcherTool, FetchParams
from vasukisquare.tools.wikipedia import WikipediaTool, WikipediaParams
from vasukisquare.llm.metrics import BookGenerationMetrics

logger = logging.getLogger(__name__)


class ResearchGenerationError(Exception):
    """Raised when research collection fails to meet minimum quality or source requirements."""
    pass


class ResearchService:
    """Orchestrates multi-perspective research generation for book topics."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        search_tool: Optional[WebSearchTool] = None,
        wikipedia_tool: Optional[WikipediaTool] = None,
        fetcher_tool: Optional[WebpageFetcherTool] = None,
        planner: Optional[ResearchPlanner] = None,
        deduplicator: Optional[DeduplicationService] = None,
        ranker: Optional[SourceRanker] = None,
        metrics: Optional[BookGenerationMetrics] = None,
    ):
        self.settings = settings or get_settings()
        self.metrics = metrics or BookGenerationMetrics()
        self.planner = planner or ResearchPlanner(self.settings, metrics=self.metrics)
        self.deduplicator = deduplicator or DeduplicationService(near_duplicate_threshold=0.80)
        self.ranker = ranker or SourceRanker()
        self.fetcher_tool = fetcher_tool or WebpageFetcherTool()

        # Configure search tool provider based on settings
        if search_tool:
            self.search_tool = search_tool
        elif self.settings.tavily_api_key:
            self.search_tool = WebSearchTool(TavilySearchProvider(self.settings.tavily_api_key), provider_name="tavily")
        elif self.settings.serper_api_key:
            self.search_tool = WebSearchTool(SerperSearchProvider(self.settings.serper_api_key), provider_name="serper")
        elif self.settings.brave_search_api_key:
            self.search_tool = WebSearchTool(BraveSearchProvider(self.settings.brave_search_api_key), provider_name="brave")
        else:
            self.search_tool = WebSearchTool(MockSearchProvider(), provider_name="mock")

        self.wikipedia_tool = wikipedia_tool or WikipediaTool()

    async def execute_query(self, query_text: str, target_types: List[SourceType]) -> List[SourceDocument]:
        """Execute a single query across appropriate tools."""
        collected: List[SourceDocument] = []
        tasks = []

        # Wikipedia orientation
        if SourceType.WIKIPEDIA in target_types:
            self.metrics.record_wikipedia_call(1)
            tasks.append(self.wikipedia_tool.execute(WikipediaParams(query=query_text, max_results=2)))

        # Web search
        self.metrics.record_web_search(1, provider=self.settings.active_search_provider_name)
        tasks.append(self.search_tool.execute(SearchParams(query=query_text, max_results=self.settings.research_max_pages_per_source)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                collected.extend(res)
            elif isinstance(res, Exception):
                logger.warning(f"Error executing research query '{query_text}': {res}")

        return collected

    async def _fetch_and_enrich_pages(self, docs: List[SourceDocument]) -> List[SourceDocument]:
        """Fetch full HTML text for top non-Wikipedia web documents."""
        enriched: List[SourceDocument] = []
        fetch_tasks = []
        doc_map = {}

        # Limit deep page fetching to top 10 documents
        fetch_candidates = [d for d in docs if d.source_type != SourceType.WIKIPEDIA and d.url.startswith("http")][:10]

        for doc in fetch_candidates:
            self.metrics.record_webpage_fetch(1)
            t = self.fetcher_tool.execute(FetchParams(url=doc.url, source_type=doc.source_type))
            fetch_tasks.append(t)
            doc_map[doc.url] = doc

        if fetch_tasks:
            fetched_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            for res in fetched_results:
                if isinstance(res, SourceDocument) and res.extracted_text:
                    orig = doc_map.get(res.url)
                    if orig:
                        orig.extracted_text = res.extracted_text
                        if not orig.title or orig.title == "Untitled":
                            orig.title = res.title
                        if len(res.extracted_text) > len(orig.summary or ""):
                            orig.summary = res.extracted_text[:400] + "..."

        return docs

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

        # Record total retrieved
        self.metrics.research.sources_retrieved = len(all_raw_docs)

        # 3. Deduplicate exact and near-duplicates
        deduped_docs = self.deduplicator.deduplicate(all_raw_docs)

        # 4. Fetch and enrich full page content for top documents
        enriched_docs = await self._fetch_and_enrich_pages(deduped_docs)

        # 5. Rank documents by authority and source type
        ranked_docs = self.ranker.rank(enriched_docs)

        # 6. Apply max source limit
        final_docs = ranked_docs[: self.settings.research_max_sources]
        self.metrics.research.sources_accepted = len(final_docs)

        # 7. Production quality check: Fail if research is empty or insufficient in production mode
        if not self.settings.vasukisquare_mock_mode:
            if len(final_docs) == 0:
                raise ResearchGenerationError(
                    f"Deep research failed for topic '{topic}': zero accepted research sources were retrieved. "
                    "Ensure internet access and valid web search API keys (TAVILY_API_KEY / SERPER_API_KEY / BRAVE_SEARCH_API_KEY)."
                )

        # 8. Extract key findings / summary highlights
        key_findings = [f"{d.title} ({d.domain}): {d.summary[:150]}" for d in final_docs[:6] if d.title]

        return ResearchCorpus(
            topic=topic,
            documents=final_docs,
            queries_executed=queries_executed,
            key_findings=key_findings,
        )

