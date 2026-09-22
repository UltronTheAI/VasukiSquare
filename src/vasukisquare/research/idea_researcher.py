"""Automated trending topic research agent and editorial idea formulation service."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from vasukisquare.config import Settings, get_settings
from vasukisquare.llm.client import LLMClient
from vasukisquare.llm.metrics import BookGenerationMetrics

if TYPE_CHECKING:
    from vasukisquare.database.connection import DatabaseManager
    from vasukisquare.database.repository import BookIdeaRepository
from vasukisquare.research.deduplication import IdeaDeduplicationService
from vasukisquare.research.models import (
    BookIdea,
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
        "topic": "How to Write Better AI Prompts",
        "category": "Technology",
        "title": "The Art of Effective AI Prompting",
        "why_now": "Generative AI is ubiquitous, but most people struggle to get precise, high-value outputs without frustration.",
        "target_audience": "Knowledge Workers, Creators, and Students",
        "intended_reader": "Professionals and learners using AI tools daily for writing, research, and ideation",
        "problem_solved": "Vague, repetitive, or inaccurate responses from AI models due to poor framing and context",
        "practical_outcome": "Structured prompting frameworks, persona-constraint setups, and iterative refinement techniques",
        "estimated_depth": "narrow",
        "suggested_pages": 46,
        "angle": "Pragmatic mental models for clear context, constraints, few-shot examples, and systematic prompt refinement.",
        "keywords": ["ai prompting", "prompt engineering", "generative ai", "productivity", "workflows"],
        "trend_signals": ["Workplace AI adoption surveys", "Knowledge worker productivity discussions"],
    },
    {
        "topic": "A Practical Guide to Digital Privacy",
        "category": "Technology",
        "title": "Practical Digital Privacy Handbook",
        "why_now": "Data harvesting, targeted tracking, and frequent data leaks affect everyday digital life.",
        "target_audience": "Everyday Internet Users and Remote Professionals",
        "intended_reader": "Individuals seeking to protect personal data without extreme paranoia or technical complexity",
        "problem_solved": "Unchecked tracking, identity theft risks, and intrusive data broker profiling",
        "practical_outcome": "Actionable security hygiene: password management, 2FA, data broker removal, and browser hardening",
        "estimated_depth": "moderate",
        "suggested_pages": 52,
        "angle": "A sensible, layered approach to securing personal data, accounts, and communications without disrupting daily habits.",
        "keywords": ["digital privacy", "online security", "data protection", "identity theft", "passwords"],
        "trend_signals": ["Consumer privacy regulation updates", "Digital rights reports"],
    },
    {
        "topic": "Understanding Cloud Computing Without the Jargon",
        "category": "Technology",
        "title": "Cloud Computing Demystified",
        "why_now": "Modern businesses operate on cloud infrastructure, yet non-technical leaders and professionals struggle with basic concepts.",
        "target_audience": "Non-Technical Managers, Entrepreneurs, and Tech Enthusiasts",
        "intended_reader": "Business operators and curious thinkers collaborating with technical teams",
        "problem_solved": "Confusion over cloud architecture, buzzwords, pricing models, and trade-offs",
        "practical_outcome": "Intuitive mental models for compute, storage, serverless, and cost management",
        "estimated_depth": "moderate",
        "suggested_pages": 55,
        "angle": "Analogy-driven breakdowns of cloud infrastructure, elasticity, storage tiers, and architectural tradeoffs.",
        "keywords": ["cloud computing", "infrastructure", "mental models", "tech for beginners", "business tech"],
        "trend_signals": ["Business tech literacy studies", "Digital transformation leadership surveys"],
    },
    {
        "topic": "Deep Work and Attention Management in Remote Teams",
        "category": "Productivity",
        "title": "Deep Work for Distributed Teams",
        "why_now": "Asynchronous workplaces suffer from continuous communication fragmentation and notification overload.",
        "target_audience": "Remote Knowledge Workers and Team Leads",
        "intended_reader": "Remote and hybrid professionals struggling with fractured focus and alert fatigue",
        "problem_solved": "Constant interruptions, shallow reactive work, and meeting fatigue in distributed environments",
        "practical_outcome": "Concrete frameworks for batching communications, async handoffs, and focus sprint scheduling",
        "estimated_depth": "narrow",
        "suggested_pages": 48,
        "angle": "Concrete frameworks for batching communications, async handoffs, and focus sprint scheduling.",
        "keywords": ["deep work", "asynchronous work", "attention management", "productivity", "remote work"],
        "trend_signals": ["Remote work productivity studies", "Substack management essays"],
    },
    {
        "topic": "Building Better Daily Habits",
        "category": "Personal Growth",
        "title": "The Architecture of Daily Habits",
        "why_now": "High-stress environments lead people to rely on willpower instead of sustainable environmental design.",
        "target_audience": "Students, Professionals, and Lifelong Learners",
        "intended_reader": "Individuals wanting to make lasting behavioral changes without burnout",
        "problem_solved": "Habit decay, lack of consistency, and reliance on fleeting motivation",
        "practical_outcome": "Friction reduction, habit stacking, identity-based reinforcement, and recovery systems",
        "estimated_depth": "narrow",
        "suggested_pages": 45,
        "angle": "Designing behavioral environments, micro-habits, cue-routine loops, and friction manipulation.",
        "keywords": ["habits", "behavioral design", "personal growth", "routines", "discipline"],
        "trend_signals": ["Behavioral psychology research", "Self-improvement reading trends"],
    },
    {
        "topic": "How AI Agents Actually Work",
        "category": "Technology",
        "title": "Demystifying AI Agents",
        "why_now": "Autonomous AI agents are emerging everywhere, yet few understand how planning, tools, and memory connect.",
        "target_audience": "Curious Professionals, Product Managers, and Tech Enthusiasts",
        "intended_reader": "Anyone wanting to understand autonomous agent architecture without wading through code repositories",
        "problem_solved": "Hype, mystery, and confusion surrounding what autonomous AI systems can and cannot do",
        "practical_outcome": "Clear mental models of agent loops, tool use, reasoning frameworks, and real-world limitations",
        "estimated_depth": "moderate",
        "suggested_pages": 54,
        "angle": "Conceptual breakdowns of reasoning loops, memory systems, tool execution, and human-in-the-loop oversight.",
        "keywords": ["ai agents", "autonomous systems", "artificial intelligence", "tech mental models"],
        "trend_signals": ["Autonomous AI agent breakthroughs", "Tech industry strategy publications"],
    },
    {
        "topic": "Protecting Yourself From Online Scams and Social Engineering",
        "category": "Technology",
        "title": "The Everyday Anti-Scam Playbook",
        "why_now": "AI-generated phishing, deepfakes, and sophisticated financial scams are growing exponentially.",
        "target_audience": "Everyday Consumers and Small Business Owners",
        "intended_reader": "Non-technical individuals and families navigating increasingly sophisticated scams",
        "problem_solved": "Vulnerability to urgent manipulative messaging, deceptive links, and social engineering",
        "practical_outcome": "Verification checklists, red-flag recognition, payment safety rules, and breach recovery protocols",
        "estimated_depth": "narrow",
        "suggested_pages": 44,
        "angle": "Psychological deception tactics explained simply with rapid verification rules and emergency recovery steps.",
        "keywords": ["cybersecurity", "scam prevention", "social engineering", "consumer protection", "fraud"],
        "trend_signals": ["Consumer protection bureau warnings", "Global scam trend reports"],
    },
    {
        "topic": "Practical Personal Knowledge Management",
        "category": "Productivity",
        "title": "Organizing Your Digital Mind",
        "why_now": "Information overload creates digital clutter and note-taking systems that get abandoned within weeks.",
        "target_audience": "Researchers, Writers, Students, and Knowledge Workers",
        "intended_reader": "Anyone who collects articles, books, and ideas but struggles to retrieve or apply them",
        "problem_solved": "Information hoarding without synthesis, fragmented notes, and forgotten insights",
        "practical_outcome": "A lightweight capture-curate-connect workflow that survives long-term use",
        "estimated_depth": "narrow",
        "suggested_pages": 48,
        "angle": "A minimalist, sustainable approach to capturing, organizing, and synthesizing information for creative output.",
        "keywords": ["pkm", "knowledge management", "second brain", "productivity", "note taking"],
        "trend_signals": ["Personal knowledge management community insights", "Academic workflow research"],
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
    intended_reader: Optional[str] = None,
    problem_solved: Optional[str] = None,
    practical_outcome: Optional[str] = None,
) -> str:
    """Construct an exhaustive, production-grade VasukiSquare prompt enforcing practical, human-first guides."""
    reader = intended_reader or target_audience
    problem = problem_solved or f"Challenges and inefficiencies related to {topic}"
    outcome = practical_outcome or f"Clear understanding, actionable mental models, and practical frameworks for {topic}"

    return (
        f"Create an authoritative, beautifully structured {pages}-page {category.lower()} guide titled '{title}'.\n\n"
        f"CORE TOPIC & ANGLE:\n"
        f"Subject: {topic}\n"
        f"Editorial Angle: {angle}\n"
        f"Why Now / Timeliness: {why_now}\n\n"
        f"AUDIENCE & PURPOSE:\n"
        f"Target Audience: {target_audience}\n"
        f"Intended Reader: {reader}\n"
        f"Core Problem Solved: {problem}\n"
        f"Practical Outcome: {outcome}\n"
        f"Tone: Clear, approachable, highly engaging, empathetic, and intellectually rigorous.\n\n"
        f"EDITORIAL & PEDAGOGICAL MANDATE (STRICT NON-TUTORIAL GUIDELINES):\n"
        f"- Target Page Count: {pages} pages (balanced evenly across logical conceptual progression).\n"
        f"- VasukiSquare Publishing Identity: Publish short, practical, approachable guides that help ordinary people understand something, improve something, or accomplish something.\n"
        f"- NO CODING TUTORIALS: Do NOT generate code blocks, terminal commands, framework installation steps, or API reference manuals. Explain technical concepts through mental models, analogies, workflows, trade-offs, and practical implications.\n"
        f"- ACTIONABLE STRUCTURE: Integrate diagnostic checklists, comparison tables, step-by-step frameworks, before-and-after scenarios, common misconceptions, and practical self-reflection exercises.\n"
        f"- ZERO AI CLICHES: Strictly avoid tropes like 'In today's fast-paced world', 'In the digital age', 'Unlock the power of', 'Game-changing', 'Let's dive in', and redundant summary paragraphs.\n"
        f"- INCREMENTAL VALUE: Every page must introduce fresh, meaningful insights with strong visual hierarchy and distinct visual anchors."
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
            "You are the Chief Editorial Strategist for VasukiSquare, an elite publishing engine for high-impact books.\n"
            "VasukiSquare publishes short, practical, approachable guides that help ordinary people understand something, "
            "improve something, or accomplish something.\n\n"
            "EDITORIAL MANDATE & IDENTITY:\n"
            "1. Focus on practical guides, mental models, workflows, decisions, frameworks, and real-world clarity.\n"
            "2. Technology, AI, cybersecurity, productivity, career, and business topics are welcome, but NEVER as coding tutorials, "
            "programming manuals, API reference docs, syntax walk-throughs, or CLI installation guides.\n"
            "3. Each topic must have sufficient depth and practical substance to sustain a 40 to 100 page book.\n"
            "4. Target page counts intentionally:\n"
            "   - 40-50 pages: focused practical how-to, beginner guides, single-skill mastery\n"
            "   - 50-70 pages: standard comprehensive practical guides\n"
            "   - 70-85 pages: broader conceptual or systemic deep-dives\n"
            "   - 85-100 pages: multi-dimensional subjects requiring substantial exploration\n"
            "5. Explicitly identify the intended reader, the core problem solved, and the practical outcome."
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

        intended_reader = trend.intended_reader or trend.target_audience
        problem_solved = trend.problem_solved or f"Challenges and inefficiencies related to {trend.topic}"
        practical_outcome = trend.practical_outcome or f"Actionable understanding and workflows for {trend.topic}"
        content_category = trend.content_category or trend.category

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
                intended_reader=intended_reader,
                problem_solved=problem_solved,
                practical_outcome=practical_outcome,
                content_category=content_category,
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
            intended_reader=intended_reader,
            problem_solved=problem_solved,
            practical_outcome=practical_outcome,
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
            intended_reader=intended_reader,
            problem_solved=problem_solved,
            practical_outcome=practical_outcome,
            content_category=content_category,
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
