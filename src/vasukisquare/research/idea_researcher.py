"""Automated trending topic research agent and editorial idea formulation service."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from uuid import uuid4

from vasukisquare.config import Settings, get_settings
from vasukisquare.llm.client import LLMClient
from vasukisquare.llm.metrics import BookGenerationMetrics

if TYPE_CHECKING:
    from vasukisquare.database.connection import DatabaseManager
    from vasukisquare.database.repository import BookIdeaRepository
from vasukisquare.research.deduplication import IdeaDeduplicationService, normalize_title, normalize_topic
from vasukisquare.research.models import (
    BookIdea,
    DetailedIdeaPrompt,
    IdeaGenerationInfo,
    IdeaScores,
    IdeaSource,
    IdeaStatus,
    RawTrendDiscovery,
    TrendDiscoveryList,
    TrendSignal,
)
from vasukisquare.research.ranking import IdeaRanker
from vasukisquare.tools.feed import RssNewsTool

logger = logging.getLogger("vasukisquare.research.ideas")

# High-quality fallback trend corpus used in mock mode or when network retrieval is disabled
CURATED_TREND_CORPUS = [
    {
        "topic": "High-Throughput Vector Databases and ANN Indexing",
        "category": "Technology",
        "title": "Vector Databases in Production",
        "why_now": "Rapid expansion of semantic search and enterprise retrieval augmented generation systems.",
        "target_audience": "Senior Backend Engineers and ML Infrastructure Architects",
        "estimated_depth": "broad",
        "suggested_pages": 75,
        "angle": "Practical internals of HNSW, IVF-PQ, quantization benchmarks, and distributed vector storage.",
        "keywords": ["vector database", "HNSW", "ANN search", "embeddings", "RAG", "quantization"],
        "trend_signals": ["Hacker News AI infrastructure discussions", "GitHub trending vector projects"],
    },
    {
        "topic": "Event-Driven Microservices with Kafka and Debezium",
        "category": "Technology",
        "title": "Event-Driven Architecture with Kafka",
        "why_now": "Companies migrating from monolithic DB polling to resilient CDC event streams.",
        "target_audience": "Cloud Architects and Distributed Systems Engineers",
        "estimated_depth": "comprehensive",
        "suggested_pages": 85,
        "angle": "Transactional outbox pattern, exactly-once delivery, schema registries, and multi-region failover.",
        "keywords": ["Kafka", "Debezium", "CDC", "event-driven", "microservices", "outbox pattern"],
        "trend_signals": ["Enterprise cloud conference keynotes", "StackOverflow trend metrics"],
    },
    {
        "topic": "Zero-Trust Cloud Security and Identity Architecture",
        "category": "Technology",
        "title": "Zero-Trust Cloud Security Handbook",
        "why_now": "Perimeter-based network security is obsolete in hybrid and multi-cloud environments.",
        "target_audience": "Security Engineers and DevOps Practitioners",
        "estimated_depth": "moderate",
        "suggested_pages": 65,
        "angle": "Hands-on implementation of SPIFFE/SPIRE, micro-segmentation, and ephemeral credential rotation.",
        "keywords": ["zero-trust", "SPIFFE", "mTLS", "cloud security", "IAM", "least privilege"],
        "trend_signals": ["NIST security standards updates", "Cloud security survey reports"],
    },
    {
        "topic": "Deep Work and Attention Management in Remote Teams",
        "category": "Productivity",
        "title": "Deep Work for Distributed Teams",
        "why_now": "Asynchronous workplaces suffer from continuous communication fragmentation and notification overload.",
        "target_audience": "Remote Knowledge Workers and Team Leads",
        "estimated_depth": "narrow",
        "suggested_pages": 48,
        "angle": "Concrete frameworks for batching communications, async handoffs, and focus sprint scheduling.",
        "keywords": ["deep work", "asynchronous work", "attention management", "productivity", "remote work"],
        "trend_signals": ["Remote work productivity studies", "Substack management essays"],
    },
    {
        "topic": "Rust Systems Programming for Python Engineers",
        "category": "Technology",
        "title": "Rust for Python Engineers",
        "why_now": "PyO3 and Rust extensions are becoming standard for accelerating Python ML and backend pipelines.",
        "target_audience": "Intermediate to Advanced Python Developers",
        "estimated_depth": "moderate",
        "suggested_pages": 68,
        "angle": "Bridging Python idioms to Rust ownership, PyO3 bindings, and memory-safe native extensions.",
        "keywords": ["Rust", "Python", "PyO3", "systems programming", "concurrency", "performance"],
        "trend_signals": ["Python package ecosystem migration to Rust", "PyPI performance benchmarks"],
    },
    {
        "topic": "eBPF Observability and Linux Kernel Tracing",
        "category": "Technology",
        "title": "eBPF Observability and Performance",
        "why_now": "eBPF has revolutionized cloud-native networking, security profiling, and zero-overhead observability.",
        "target_audience": "Site Reliability Engineers and Linux Systems Engineers",
        "estimated_depth": "comprehensive",
        "suggested_pages": 90,
        "angle": "Writing custom kprobes, tracepoints, Cilium integration, and production performance profiling.",
        "keywords": ["eBPF", "Linux kernel", "observability", "Cilium", "kprobes", "BCC"],
        "trend_signals": ["Linux Foundation eBPF summit", "Cloud Native Computing Foundation roadmaps"],
    },
    {
        "topic": "Clean Architecture and Domain-Driven Design in Go",
        "category": "Technology",
        "title": "Clean Architecture in Go",
        "why_now": "Go microservices frequently suffer from flat package spaghetti as codebases scale.",
        "target_audience": "Go Developers and Tech Leads",
        "estimated_depth": "moderate",
        "suggested_pages": 60,
        "angle": "Practical onion architecture, explicit dependency injection, domain entities, and mockable interfaces.",
        "keywords": ["Go", "clean architecture", "DDD", "microservices", "interfaces", "dependency injection"],
        "trend_signals": ["Go Developer Survey insights", "Enterprise Go architecture patterns"],
    },
    {
        "topic": "Applied Mental Models for Engineering Decisions",
        "category": "Leadership",
        "title": "Mental Models for Engineers",
        "why_now": "Senior engineers must navigate complex architectural trade-offs without dogma.",
        "target_audience": "Staff Engineers, Architects, and Tech Leads",
        "estimated_depth": "narrow",
        "suggested_pages": 50,
        "angle": "First-principles thinking, inversion, second-order effects, and reversible decision frameworks in software.",
        "keywords": ["mental models", "decision making", "first principles", "systems thinking", "tech leadership"],
        "trend_signals": ["Engineering leadership podcasts", "Tech management literature"],
    },
]


def generate_production_prompt(
    topic: str,
    title: str,
    target_audience: str,
    pages: int,
    angle: str,
    why_now: str,
    category: str,
) -> str:
    """Construct an exhaustive, production-grade VasukiSquare prompt."""
    is_tech = category.lower() in ("technology", "engineering", "programming", "devops")
    tech_guidelines = (
        "- Include syntax-checked, runnable code snippets illustrating core patterns.\n"
        "- Explain architectural tradeoffs, failure modes, and production gotchas.\n"
        "- Avoid pseudo-code; provide realistic, industry-standard implementations.\n"
    ) if is_tech else (
        "- Provide concrete practical frameworks, step-by-step diagnostic checklists, and real-world case studies.\n"
        "- Ground concepts in empirical evidence, behavioral science, or operational practice.\n"
        "- Avoid vague motivational fluff; focus on actionable execution protocols.\n"
    )

    return (
        f"Create an authoritative, beautifully structured {pages}-page {category.lower()} book titled '{title}'.\n\n"
        f"CORE TOPIC & ANGLE:\n"
        f"Subject: {topic}\n"
        f"Editorial Angle: {angle}\n"
        f"Why Now / Timeliness: {why_now}\n\n"
        f"AUDIENCE & TONE:\n"
        f"Target Audience: {target_audience}\n"
        f"Tone: Authoritative, pragmatic, highly engaging, and intellectually rigorous.\n\n"
        f"CONTENT & PEDAGOGICAL REQUIREMENTS:\n"
        f"{tech_guidelines}"
        f"- Target Page Count: {pages} pages (evenly balanced across chapters and technical deep-dives).\n"
        f"- Structural Variety: Integrate clear headings, key takeaway callouts, diagrams/tables where appropriate, and structured visual anchors.\n"
        f"- Repetition Avoidance: Every page must introduce distinct, incremental concepts without re-hashing earlier definitions.\n"
        f"- Strict Exclusions: Avoid generic high-level summaries, filler introductions, and redundant recaps.\n"
        f"- Research & Accuracy: Factually accurate claims adhering to authoritative industry documentation and primary sources."
    )


class IdeaResearchService:
    """Orchestrates trending topic discovery, historical catalog deduplication, depth validation, and idea persistence."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[LLMClient] = None,
        repository: Optional[BookIdeaRepository] = None,
        deduplicator: Optional[IdeaDeduplicationService] = None,
        ranker: Optional[IdeaRanker] = None,
        metrics: Optional[BookGenerationMetrics] = None,
        rss_tool: Optional[RssNewsTool] = None,
    ):
        self.settings = settings or get_settings()
        self.metrics = metrics or BookGenerationMetrics()
        self.llm_client = llm_client or LLMClient(self.settings, self.metrics)
        self.deduplicator = deduplicator or IdeaDeduplicationService()
        self.ranker = ranker or IdeaRanker(min_score_threshold=self.settings.research_min_score)
        self.rss_tool = rss_tool or RssNewsTool()

        self._repo = repository
        self._db_manager: Optional[DatabaseManager] = None

    @property
    def repository(self) -> BookIdeaRepository:
        """Lazy-initialize BookIdeaRepository with DatabaseManager."""
        if self._repo is None:
            from vasukisquare.database.connection import DatabaseManager
            from vasukisquare.database.repository import BookIdeaRepository
            self._db_manager = DatabaseManager(self.settings)
            self._repo = BookIdeaRepository(
                self._db_manager.db,
                collection_name=self.settings.idea_collection,
            )
        return self._repo

    def discover_trends(
        self,
        category: Optional[str] = None,
        count: int = 8,
    ) -> List[RawTrendDiscovery]:
        """Discover candidate trends from curated corpus or via LLM."""
        if self.settings.vasukisquare_mock_mode:
            candidates: List[RawTrendDiscovery] = []
            for item in CURATED_TREND_CORPUS:
                if category and category.lower() not in item["category"].lower():
                    continue
                candidates.append(
                    RawTrendDiscovery(
                        topic=item["topic"],
                        category=item["category"],
                        why_now=item["why_now"],
                        target_audience=item["target_audience"],
                        estimated_depth=item["estimated_depth"],
                        suggested_pages=item["suggested_pages"],
                        angle=item["angle"],
                        trend_signals=item["trend_signals"],
                    )
                )
            return candidates[:count]

        # In production LLM mode, prompt LLM for trend discovery
        system_prompt = (
            "You are the Chief Editorial Strategist for VasukiSquare, an elite AI ebook publishing engine.\n"
            "Identify current, high-demand, evergreen book topics with genuine reader value.\n"
            "REQUIREMENTS:\n"
            "1. Each topic must have sufficient depth and practical substance to sustain a 40 to 100 page book.\n"
            "2. Intentionally determine page count:\n"
            "   - 40-50 pages: focused beginner guides, compact how-to, narrow subjects\n"
            "   - 50-70 pages: standard practical guides\n"
            "   - 70-85 pages: broader technical or educational deep-dives\n"
            "   - 85-100 pages: comprehensive subjects requiring substantial depth\n"
            "3. Reject ephemeral social media fads or shallow listicles.\n"
            "4. Provide a distinct angle and clear reader target."
        )

        category_prompt = f" Focusing primarily on category: '{category}'." if category else ""
        user_prompt = f"Generate a list of {count} high-potential, trending book topic ideas.{category_prompt}"

        try:
            import asyncio
            result = asyncio.run(
                self.llm_client.invoke_structured(
                    schema=TrendDiscoveryList,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    stage="idea_trend_discovery",
                    temperature=0.3,
                )
            )
            return result.trends[:count]
        except Exception as e:
            logger.warning(f"LLM trend discovery failed ({e}), falling back to curated trend catalog.")
            return [
                RawTrendDiscovery(**item)
                for item in CURATED_TREND_CORPUS
                if not category or category.lower() in item["category"].lower()
            ][:count]

    def formulate_idea_candidate(
        self,
        trend: RawTrendDiscovery,
        historical_records: List[Dict[str, Any]],
    ) -> BookIdea:
        """Formulate a polished, fully validated BookIdea from a raw trend candidate."""
        # Clean and constrain title
        initial_title = trend.topic
        if ":" in initial_title:
            initial_title = initial_title.split(":")[0].strip()
        if len(initial_title) > 48:
            initial_title = initial_title[:48].rsplit(" ", 1)[0]

        # Constrain pages to strict [40, 100] range
        pages = max(40, min(100, trend.suggested_pages))

        # Check deduplication against historical catalog
        dedup_match = self.deduplicator.check_duplicate(
            candidate_title=initial_title,
            candidate_topic=trend.topic,
            candidate_summary=f"{trend.why_now} {trend.angle}",
            candidate_angle=trend.angle,
            historical_records=historical_records,
        )

        signals = [
            TrendSignal(source="Editorial Discovery", signal=s, weight=0.85)
            for s in trend.trend_signals
        ]
        if not signals:
            signals.append(TrendSignal(source="Market Analysis", signal=trend.why_now or "Industry demand", weight=0.80))

        sources = [
            IdeaSource(
                title=f"Documentation & Reference for {trend.topic}",
                url=f"https://en.wikipedia.org/wiki/{trend.topic.replace(' ', '_')}",
                publisher="Authoritative Reference",
                accessed_at=datetime.now(timezone.utc),
            )
        ]

        if dedup_match.is_duplicate:
            # Create a rejected idea record explaining the duplication
            scores = self.ranker.score_idea(
                trend=0.5,
                uniqueness=0.1,
                bookworthiness=0.4,
                evergreen=0.5,
                confidence=0.5,
                pages=pages,
                summary=trend.why_now,
            )
            return BookIdea(
                topic=trend.topic,
                title=initial_title,
                pages=pages,
                prompt=f"Rejected duplicate: {dedup_match.reason}",
                category=trend.category,
                audience=trend.target_audience,
                book_type="practical_guide",
                summary=trend.why_now,
                angle=trend.angle,
                why_now=trend.why_now,
                trend_signals=signals,
                sources=sources,
                scores=scores,
                similar_to=[dedup_match.matched_title or ""] if dedup_match.matched_title else [],
                status=IdeaStatus.REJECTED,
                rejection_reason=dedup_match.reason,
            )

        # Generate detailed generation prompt
        full_prompt = generate_production_prompt(
            topic=trend.topic,
            title=initial_title,
            target_audience=trend.target_audience,
            pages=pages,
            angle=trend.angle,
            why_now=trend.why_now,
            category=trend.category,
        )

        uniqueness_val = 0.90 if not dedup_match.distinct_angle_accepted else 0.75
        scores = self.ranker.score_idea(
            trend=0.85,
            uniqueness=uniqueness_val,
            bookworthiness=0.88,
            evergreen=0.82,
            confidence=0.85,
            pages=pages,
            book_type="practical_guide",
            summary=trend.why_now,
            sources_count=len(sources),
            signals_count=len(signals),
        )

        similar_list = [dedup_match.matched_title] if dedup_match.matched_title else []

        return BookIdea(
            topic=trend.topic,
            title=initial_title,
            pages=pages,
            prompt=full_prompt,
            category=trend.category,
            audience=trend.target_audience,
            book_type="practical_guide",
            summary=f"A comprehensive {pages}-page guide covering {trend.topic}.",
            angle=trend.angle,
            why_now=trend.why_now,
            keywords=[w.lower() for w in trend.topic.split() if len(w) > 3],
            research_queries=[f"{trend.topic} core architecture", f"{trend.topic} practical patterns"],
            sources=sources,
            trend_signals=signals,
            scores=scores,
            similar_to=similar_list,
            status=IdeaStatus.READY,
            rejection_reason=None,
        )

    def research_ideas(
        self,
        count: int = 5,
        min_score: float = 0.70,
        category: Optional[str] = None,
        dry_run: bool = False,
    ) -> List[BookIdea]:
        """Execute complete automated book idea research workflow."""
        logger.info(f"Starting idea research: target_count={count}, min_score={min_score}, category={category}, dry_run={dry_run}")

        # 1. Fetch historical records for deduplication
        historical_records: List[Dict[str, Any]] = []
        if not dry_run:
            try:
                historical_records = self.repository.get_historical_records()
                logger.info(f"Loaded {len(historical_records)} historical catalog records from MongoDB.")
            except Exception as e:
                logger.warning(f"Could not load historical records from MongoDB ({e}). Proceeding with local deduplication.")

        # 2. Discover raw trends
        raw_trends = self.discover_trends(category=category, count=max(count * 2, 8))

        # 3. Formulate and deduplicate candidates
        accepted_ideas: List[BookIdea] = []
        rejected_ideas: List[BookIdea] = []

        for trend in raw_trends:
            if len(accepted_ideas) >= count:
                break

            idea = self.formulate_idea_candidate(trend, historical_records)

            if idea.status == IdeaStatus.READY and idea.scores.composite_score >= min_score:
                accepted_ideas.append(idea)
                # Add to local historical records so subsequent candidates in this batch deduplicate against it
                historical_records.append({
                    "id": idea.id,
                    "title": idea.title,
                    "topic": idea.topic,
                    "slug": idea.slug,
                    "summary": idea.summary,
                    "angle": idea.angle,
                    "category": idea.category,
                    "status": "ready",
                })
            else:
                if idea.status != IdeaStatus.READY:
                    rejected_ideas.append(idea)
                elif idea.scores.composite_score < min_score:
                    idea.status = IdeaStatus.REJECTED
                    idea.rejection_reason = f"Score {idea.scores.composite_score:.2f} below min_score threshold {min_score:.2f}"
                    rejected_ideas.append(idea)

        # 4. Rank accepted ideas
        ranked_ideas = self.ranker.rank_ideas(accepted_ideas, min_score=min_score)

        # 5. Persist to MongoDB if not dry-run
        if not dry_run:
            for idea in ranked_ideas:
                try:
                    self.repository.create(idea)
                    logger.info(f"Persisted READY idea: '{idea.title}' (slug: {idea.slug})")
                except Exception as e:
                    logger.error(f"Failed to persist idea '{idea.title}' to MongoDB: {e}")

            for rej in rejected_ideas:
                try:
                    self.repository.create(rej)
                    logger.debug(f"Recorded REJECTED idea: '{rej.title}' ({rej.rejection_reason})")
                except Exception:
                    pass

        return ranked_ideas

    @staticmethod
    def export_ideas_to_json(
        ideas: List[BookIdea],
        file_path: Union[str, Path],
    ) -> str:
        """Export book ideas to a formatted JSON file for manual inspection."""
        out_path = Path(file_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        export_data = []
        for idea in ideas:
            export_data.append({
                "id": idea.id,
                "topic": idea.topic,
                "title": idea.title,
                "slug": idea.slug,
                "pages": idea.pages,
                "prompt": idea.prompt,
                "category": idea.category,
                "audience": idea.audience,
                "book_type": idea.book_type,
                "summary": idea.summary,
                "angle": idea.angle,
                "why_now": idea.why_now,
                "keywords": idea.keywords,
                "research_queries": idea.research_queries,
                "scores": {
                    "trend": idea.scores.trend,
                    "uniqueness": idea.scores.uniqueness,
                    "bookworthiness": idea.scores.bookworthiness,
                    "evergreen": idea.scores.evergreen,
                    "confidence": idea.scores.confidence,
                    "composite": idea.scores.composite_score,
                },
                "sources": [s.model_dump() for s in idea.sources],
                "trend_signals": [ts.model_dump() for ts in idea.trend_signals],
                "status": idea.status.value,
                "rejection_reason": idea.rejection_reason,
                "created_at": idea.created_at.isoformat(),
            })

        formatted_json = json.dumps(export_data, indent=2, default=str)
        out_path.write_text(formatted_json, encoding="utf-8")
        return str(out_path.resolve())
