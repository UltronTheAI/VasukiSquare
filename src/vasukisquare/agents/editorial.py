"""Editorial Planning Agent inferring intent and generating structured BookPlans."""

import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from vasukisquare.config import Settings, get_settings
from vasukisquare.book.layout import LayoutType
from vasukisquare.book.models import (
    BookIntent,
    BookPlan,
    PlannedChapter,
    PlannedPage,
    SectionPlan,
    VisualAnchorType,
)
from vasukisquare.design.theme import Theme, get_chapter_theme
from vasukisquare.research.models import ResearchCorpus

logger = logging.getLogger(__name__)


from vasukisquare.llm.client import LLMClient, GroqGenerationError
from vasukisquare.llm.metrics import BookGenerationMetrics

logger = logging.getLogger(__name__)


# Default icons mapped to common chapter motifs
MOTIF_ICONS = [
    "sparkles",
    "cpu",
    "database",
    "layers",
    "code",
    "compass",
    "book-open",
    "terminal",
    "shield-check",
    "zap",
    "git-branch",
    "globe",
]


class GeneratedChapterPlan(BaseModel):
    """Schema for LLM-generated chapter plan."""

    title: str = Field(description="Chapter title")
    summary: str = Field(description="Summary of topics covered in this chapter")
    icon: str = Field(default="code", description="Lucide icon name")
    key_sections: List[str] = Field(default_factory=list, description="3 to 5 distinct section titles for this chapter")


class GeneratedBookOutline(BaseModel):
    """Schema for LLM-generated complete book outline."""

    chapters: List[GeneratedChapterPlan] = Field(description="Sequential list of chapters")


class EditorialPlannerAgent:
    """Agent responsible for intent inference and structural editorial book planning."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[LLMClient] = None,
        metrics: Optional[BookGenerationMetrics] = None,
    ):
        self.settings = settings or get_settings()
        self.metrics = metrics or BookGenerationMetrics()
        self.llm_client = llm_client or LLMClient(self.settings, self.metrics)

    async def infer_intent(
        self,
        prompt: str,
        corpus: Optional[ResearchCorpus] = None,
    ) -> BookIntent:
        """Infer editorial intent, target audience, depth, and requirements from prompt."""
        if self.settings.vasukisquare_mock_mode:
            return self._heuristic_intent(prompt)

        system_prompt = (
            "You are an executive book editor and educational curriculum architect. "
            "Analyze the user's book topic and research findings. "
            "Infer the book_type (e.g. beginner_guide, tutorial_manual, technical_deep_dive, architecture_guide), "
            "target_audience, technical_depth (introductory, intermediate, advanced, expert), tone, "
            "approximate_length, chapter_count (5 to 10), code_requirements, diagram_requirements, "
            "primary_programming_language (e.g. python, typescript, rust, go, or null if language-agnostic), and domain_topic."
        )

        findings_summary = "\n".join([f"- {d.title} ({d.domain}): {d.summary[:200]}" for d in corpus.documents[:5]]) if corpus and corpus.documents else "None"
        user_prompt = f"Topic prompt: {prompt}\n\nResearch dossier findings:\n{findings_summary}\n\nInfer the structured BookIntent."

        try:
            result = await self.llm_client.invoke_structured(
                schema=BookIntent,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                stage="intent_inference",
                temperature=0.2,
            )
            if not result.primary_programming_language:
                result.primary_programming_language = self._detect_language(prompt)
            return result
        except Exception as e:
            if self.settings.vasukisquare_mock_mode:
                logger.warning(f"LLM Intent inference failed in mock mode, falling back to heuristic: {e}")
                return self._heuristic_intent(prompt)
            raise GroqGenerationError(f"Book intent inference failed via Groq: {e}") from e

    def _detect_language(self, prompt: str) -> Optional[str]:
        """Detect primary programming language from prompt."""
        p_lower = prompt.lower()
        languages = {
            "python": "python",
            "rust": "rust",
            "golang": "go",
            "go ": "go",
            "typescript": "typescript",
            "javascript": "javascript",
            "c++": "cpp",
            "cpp": "cpp",
            "java ": "java",
            "kotlin": "kotlin",
            "swift": "swift",
            "sql": "sql",
        }
        for kw, lang in languages.items():
            if kw in p_lower:
                return lang
        return None

    def _heuristic_intent(self, prompt: str) -> BookIntent:
        """Deterministic heuristic intent inference based on prompt keywords."""
        p_lower = prompt.lower()
        primary_lang = self._detect_language(prompt)

        # Technical depth & Audience
        if any(w in p_lower for w in ["beginner", "zero to", "getting started", "from scratch", "basics", "introduction", "intro", "noob", "noobs"]):
            depth = "introductory"
            audience = "Absolute Beginners, Self-Taught Learners, and New Practitioners"
            book_type = "beginner_guide"
            tone = "educational and encouraging"
        elif any(w in p_lower for w in ["expert", "internals", "under the hood", "advanced architecture"]):
            depth = "expert"
            audience = "Principal Engineers, System Architects, and Technical Leaders"
            book_type = "technical_deep_dive"
            tone = "authoritative and analytical"
        elif any(w in p_lower for w in ["advanced", "deep dive", "performance"]):
            depth = "advanced"
            audience = "Senior Software Engineers and Architects"
            book_type = "technical_deep_dive"
            tone = "authoritative"
        else:
            depth = "intermediate"
            audience = "Software Developers and Engineering Practitioners"
            book_type = "technical_handbook"
            tone = "practical and comprehensive"

        # Length & Chapter count
        if any(w in p_lower for w in ["comprehensive", "in-depth", "complete", "definitive"]):
            length = "comprehensive"
            chapter_count = 8
        elif any(w in p_lower for w in ["short", "brief", "quick", "pocket"]):
            length = "short"
            chapter_count = 5
        else:
            length = "standard"
            chapter_count = 6

        code_keywords = [
            "code", "programming", "python", "rust", "go", "java", "c++", "typescript",
            "javascript", "framework", "algorithm", "developer", "api", "database",
            "concurrency", "memory", "async", "backend", "programs", "building", "liorandb", "db"
        ]
        diagram_keywords = [
            "architecture", "system", "distributed", "network", "cloud", "pipeline",
            "design", "protocol", "concurrency", "memory", "management", "workflow"
        ]

        code_req = any(w in p_lower for w in code_keywords) or (primary_lang is not None)
        diagram_req = any(w in p_lower for w in diagram_keywords)

        domain_topic = "programming_guide" if primary_lang else "systems_architecture"

        return BookIntent(
            book_type=book_type,
            target_audience=audience,
            technical_depth=depth,
            tone=tone,
            approximate_length=length,
            chapter_count=chapter_count,
            research_intensity="deep",
            code_requirements=code_req,
            diagram_requirements=diagram_req,
            primary_programming_language=primary_lang,
            domain_topic=domain_topic,
        )

    async def _plan_chapters_with_llm(
        self,
        title: str,
        intent: BookIntent,
        corpus: Optional[ResearchCorpus],
        chapter_count: int,
    ) -> Optional[List[PlannedChapter]]:
        """Use Groq LLM to generate topic-specific, progression-aligned chapters."""
        if self.settings.vasukisquare_mock_mode:
            return None

        # Format research evidence to ground the outline
        findings = []
        if corpus and corpus.documents:
            for d in corpus.documents[:8]:
                findings.append(f"Source: {d.title} ({d.url})\nSummary: {d.summary}")
        findings_text = "\n\n".join(findings) if findings else "No external research available."

        system_prompt = (
            f"You are a master technical author and book architect. "
            f"Create a logically structured, progressive Table of Contents for an ebook titled: '{title}'.\n"
            f"Target Audience: {intent.target_audience} (Depth: {intent.technical_depth}).\n"
            f"Primary Language / Ecosystem: {intent.primary_programming_language or 'Domain Standard'}.\n\n"
            f"CRITICAL INSTRUCTIONS:\n"
            f"1. Generate EXACTLY {chapter_count} sequential chapters that take the reader from zero knowledge to building real applications.\n"
            f"2. Ground the chapter titles directly in the research dossier provided (e.g. if researching LioranDB, include chapters on its core concepts, installation, drivers/SDKs, collection models, CRUD queries, indexes, and real-world project deployment).\n"
            f"3. For EACH chapter, specify 3 to 4 distinct key_sections covering concrete subtopics.\n"
            f"4. Assign a relevant Lucide icon (e.g. terminal, code, database, layers, cpu, shield-check, zap, compass) to each chapter."
        )

        user_prompt = f"Research Dossier:\n{findings_text}\n\nGenerate the complete GeneratedBookOutline."

        try:
            result: GeneratedBookOutline = await self.llm_client.invoke_structured(
                schema=GeneratedBookOutline,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                stage="chapter_planning",
                temperature=0.3,
            )

            if not result or not result.chapters or len(result.chapters) < 2:
                raise ValueError("LLM returned insufficient chapters in GeneratedBookOutline.")

            source_urls = [d.url for d in corpus.documents] if corpus else []
            chapters: List[PlannedChapter] = []

            for i, gen_ch in enumerate(result.chapters[:chapter_count]):
                ch_num = i + 1
                theme = get_chapter_theme(ch_num)
                icon = gen_ch.icon if gen_ch.icon in MOTIF_ICONS else MOTIF_ICONS[i % len(MOTIF_ICONS)]
                ch_sources = source_urls[i * 2 : (i + 1) * 2] if source_urls else []

                # Build sections with visual anchors
                sections: List[SectionPlan] = []
                raw_sections = gen_ch.key_sections if len(gen_ch.key_sections) >= 3 else [
                    f"Understanding {gen_ch.title}",
                    f"Core Concepts and Mechanics of {gen_ch.title}",
                    f"Practical Workflows and Code Examples",
                    f"Best Practices and Troubleshooting",
                ]

                for sec_idx, sec_title in enumerate(raw_sections):
                    anchors = [VisualAnchorType.TEXT]
                    if intent.code_requirements:
                        if sec_idx % 2 == 0:
                            anchors.append(VisualAnchorType.CODE)
                        else:
                            anchors.append(VisualAnchorType.TABLE)
                    sections.append(SectionPlan(title=sec_title, visual_anchors=anchors))

                chapters.append(
                    PlannedChapter(
                        chapter_number=ch_num,
                        title=gen_ch.title,
                        summary=gen_ch.summary,
                        icon=icon,
                        theme=theme,
                        page_budget=4,
                        sections=sections,
                        sources_to_cite=ch_sources,
                    )
                )
            return chapters

        except Exception as e:
            if self.settings.vasukisquare_mock_mode:
                logger.warning(f"LLM chapter outline generation failed in mock mode, falling back to heuristic: {e}")
                return None
            raise GroqGenerationError(f"Chapter planning failed via Groq: {e}") from e

    def _build_deterministic_chapters(
        self,
        title: str,
        intent: BookIntent,
        corpus: Optional[ResearchCorpus] = None,
        chapter_count: Optional[int] = None,
    ) -> List[PlannedChapter]:
        """Generate structured chapter definitions tailored to the topic domain."""
        t_lower = title.lower()
        p_lang = (intent.primary_programming_language or "").lower()

        # Domain 1: Python for Beginners / Zero to Real Programs
        if "python" in t_lower or p_lang == "python":
            chapter_topics = [
                ("Introduction to Python & Setting Up Your Environment", "Installing Python, understanding the interpreter, running your first script, and configuring VS Code.", "terminal", [
                    SectionPlan(title="Why Python & How the Interpreter Works", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Installation, Tooling & Your First 'Hello World'", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Interactive REPL & Script Execution", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Syntax Fundamentals & Common Beginner Errors", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                ]),
                ("Variables, Data Types & Core Operators", "Understanding dynamic typing, strings, integers, floats, booleans, and arithmetic operators.", "code", [
                    SectionPlan(title="Primitive Data Types & Type Conversion", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="String Manipulation & Formatted Output", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Numeric Calculations & Math Operations", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.CODE]),
                    SectionPlan(title="Boolean Logic & Comparison Operators", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TEXT]),
                ]),
                ("Control Flow: Conditionals & Iteration", "Mastering if-else logic, while loops, for loops, break, continue, and the range function.", "layers", [
                    SectionPlan(title="Conditional Logic & Boolean Expressions", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Looping Patterns & Iteration Idioms", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                    SectionPlan(title="While Loops & Sentinel Controlled Flow", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Loop Control: Break, Continue & Else Clauses", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.QUOTE]),
                ]),
                ("Functions, Scope & Modular Code", "Defining reusable functions, positional vs keyword arguments, return values, and variable scope.", "cpu", [
                    SectionPlan(title="Function Syntax, Parameters & Return Values", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Scope Resolution & Module Organization", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Keyword Arguments, Defaults & Arbitrary Args", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                    SectionPlan(title="Docstrings, Type Hints & Pure Functions", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.QUOTE]),
                ]),
                ("Core Data Structures: Lists, Tuples, Dictionaries & Sets", "Organizing collections, indexing, slicing, dictionary key-value mappings, and list comprehensions.", "database", [
                    SectionPlan(title="Lists, Tuples & Slicing Operations", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.CODE]),
                    SectionPlan(title="Dictionaries, Sets & Hash Lookups", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.STATISTIC]),
                    SectionPlan(title="List Comprehensions & Transformation Pipelines", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.COMPARISON]),
                    SectionPlan(title="Data Structure Selection Guide & Complexity", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.DIAGRAM]),
                ]),
                ("File Handling, Error Handling & Defensiveness", "Reading and writing files, structured exception handling with try-except, and context managers.", "shield-check", [
                    SectionPlan(title="Working with Files & Context Managers", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Exception Handling with try/except/finally", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Handling Structured Formats: JSON & CSV", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                    SectionPlan(title="Defensive Programming & Custom Exception Types", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                ]),
                ("Building Your First Real-World Python Programs", "Step-by-step construction of practical CLI applications: task managers, data parsers, and automation scripts.", "zap", [
                    SectionPlan(title="Architecture of a Complete CLI Application", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.CODE]),
                    SectionPlan(title="Task Model & Storage Implementation", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Interactive Command Loop & User Experience", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="End-to-End Implementation & Testing", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                ]),
                ("Next Steps: Standard Library, Virtual Environments & Best Practices", "Exploring Python's built-in modules, pip packaging, virtual environments, and PEP 8 style standards.", "compass", [
                    SectionPlan(title="The Python Standard Library Power Tools", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Virtual Environments, PEP 8 & Best Practices", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Package Management with pip and pyproject.toml", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.DIAGRAM]),
                    SectionPlan(title="Developer Roadmap: From Beginner to Professional", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                ]),
            ]
        # Domain 2: Distributed Systems / Databases
        elif any(w in t_lower for w in ["database", "distributed", "raft", "storage", "consensus", "kv"]):
            chapter_topics = [
                ("Foundations of Distributed Storage Systems", "Theoretical baselines, consistency models, and the evolution of data architectures.", "sparkles", [
                    SectionPlan(title="CAP Theorem & Consistency Spectrum", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Partitioning & Consistent Hashing", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Vector Clocks & Causal Ordering", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.CODE]),
                    SectionPlan(title="Replication Strategies: Active vs Passive", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TABLE]),
                ]),
                ("Consensus Protocols & State Machine Replication", "Raft, Paxos, and leader election mechanisms under network partitions.", "cpu", [
                    SectionPlan(title="Quorum Verification & Term Transitions", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Log Replication & Commit Invariants", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.STATISTIC]),
                    SectionPlan(title="Joint Consensus & Cluster Membership Changes", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Snapshotting & Log Compaction Mechanics", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.DIAGRAM]),
                ]),
                ("Storage Engine Internals: B+ Trees vs LSM-Trees", "Data structures for persistent storage, write-ahead logging, and tiered compaction.", "database", [
                    SectionPlan(title="B+ Tree Page Management & In-Place Updates", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TEXT]),
                    SectionPlan(title="LSM-Tree MemTable Ingestion & SSTable Compaction", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.DIAGRAM]),
                    SectionPlan(title="Write-Ahead Logging & Crash Recovery Protocols", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Bloom Filters & Block Indexing Accelerators", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.CODE]),
                ]),
                ("Concurrency Control & Isolation Levels", "Multi-Version Concurrency Control (MVCC), 2-Phase Locking, and serializable transactions.", "layers", [
                    SectionPlan(title="Snapshot Isolation & Read Views", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Deadlock Detection & Resolution Strategies", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.CODE]),
                    SectionPlan(title="Two-Phase Commit & Distributed Transactions", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Optimistic vs Pessimistic Concurrency Trade-offs", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TABLE]),
                ]),
                ("Performance Benchmarks & Architectural Trade-offs", "Empirical evaluations of throughput, tail latency, and hardware tiering.", "activity", [
                    SectionPlan(title="Ingestion Throughput & Latency Profiles", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.COMPARISON]),
                    SectionPlan(title="Hardware Offloading & NVMe Tiering", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Tail Latency Mitigation & Read Amplification", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.CODE]),
                    SectionPlan(title="System Architecture Decision Matrix", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.QUOTE]),
                ]),
                ("Production Reliability & Operational Best Practices", "Scaling distributed clusters, chaos testing, monitoring, and real-world post-mortems.", "compass", [
                    SectionPlan(title="Observability, Replica Drift & Alerting", visual_anchors=[VisualAnchorType.QUOTE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Incident Retrospective & Disaster Recovery", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TABLE]),
                    SectionPlan(title="Chaos Engineering & Fault Injection", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.DIAGRAM]),
                    SectionPlan(title="Production Readiness Checklist & Runbooks", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                ]),
            ]
        # Domain 3: General Technical & Software Engineering
        else:
            words = [w.capitalize() for w in title.replace(":", " ").replace("-", " ").split() if len(w) > 2]
            key_subject = " ".join(words[:4]) if words else title

            chapter_topics = [
                (f"Foundations & Core Principles of {key_subject}", "Fundamental concepts, historical context, and mental models.", "sparkles", [
                    SectionPlan(title="Historical Context & Core Terminology", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Guiding Principles & System Philosophy", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Core Mental Models & Abstractions", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Prerequisites & Environmental Setup", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.QUOTE]),
                ]),
                ("Core Architecture & Component Models", "Structural components, lifecycle mechanics, and interaction patterns.", "cpu", [
                    SectionPlan(title="System Topology & Component Topology", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Data Flow & Interaction Lifecycles", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="State Management & Coordination", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.STATISTIC]),
                    SectionPlan(title="Interface Contracts & Protocol Design", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.CODE]),
                ]),
                ("Implementation Patterns & Practical Techniques", "Real-world engineering patterns, idiomatic implementations, and code structures.", "code", [
                    SectionPlan(title="Reference Implementation Patterns", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Developer Workflows & Tooling", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.TABLE]),
                    SectionPlan(title="Error Handling & Resilience Patterns", visual_anchors=[VisualAnchorType.CODE, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Testing Strategies & Quality Assurance", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.CODE]),
                ]),
                ("Performance, Scalability & Trade-offs", "Quantitative evaluations, bottleneck analysis, and optimization strategies.", "layers", [
                    SectionPlan(title="Throughput & Efficiency Benchmarks", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.COMPARISON]),
                    SectionPlan(title="Trade-off Matrix & Decision Trees", visual_anchors=[VisualAnchorType.COMPARISON, VisualAnchorType.TABLE]),
                    SectionPlan(title="Profiling, Bottleneck Detection & Tuning", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.CODE]),
                    SectionPlan(title="Resource Allocation & Scaling Dynamics", visual_anchors=[VisualAnchorType.STATISTIC, VisualAnchorType.TABLE]),
                ]),
                ("Production Best Practices & Case Studies", "Operational readiness, security patterns, and real-world lessons learned.", "database", [
                    SectionPlan(title="Security & Resilience Patterns", visual_anchors=[VisualAnchorType.QUOTE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Real-World Deployment Case Study", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Monitoring, Telemetry & SRE Runbooks", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TABLE]),
                    SectionPlan(title="Post-Mortem Lessons & Anti-Patterns", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.QUOTE]),
                ]),
                ("Emerging Trends & Future Outlook", "Next-generation paradigms, ecosystem evolution, and forward-looking recommendations.", "compass", [
                    SectionPlan(title="Horizon Technologies & Evolution", visual_anchors=[VisualAnchorType.DIAGRAM, VisualAnchorType.TEXT]),
                    SectionPlan(title="Strategic Recommendations", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                    SectionPlan(title="Ecosystem Tooling & Community Direction", visual_anchors=[VisualAnchorType.TIMELINE, VisualAnchorType.QUOTE]),
                    SectionPlan(title="Continuous Learning & Mastery Roadmap", visual_anchors=[VisualAnchorType.TABLE, VisualAnchorType.TEXT]),
                ]),
            ]

        desired_count = chapter_count or intent.chapter_count
        count = max(1, desired_count)

        source_urls = [d.url for d in corpus.documents] if corpus else []
        chapters: List[PlannedChapter] = []

        for i in range(count):
            ch_num = i + 1
            ch_title, ch_summary, default_icon, sections = chapter_topics[i % len(chapter_topics)]
            icon = default_icon if default_icon in MOTIF_ICONS else MOTIF_ICONS[i % len(MOTIF_ICONS)]
            theme = get_chapter_theme(ch_num)
            ch_sources = source_urls[i * 2 : (i + 1) * 2] if source_urls else []

            chapters.append(
                PlannedChapter(
                    chapter_number=ch_num,
                    title=ch_title,
                    summary=ch_summary,
                    icon=icon,
                    theme=theme,
                    page_budget=4,
                    sections=sections,
                    sources_to_cite=ch_sources,
                )
            )

        return chapters

    @staticmethod
    def calculate_adaptive_chapter_count(target_pages: int) -> int:
        """Calculate the ideal chapter count so that every chapter has an opener and adequate content pages,
        while keeping the total physical page count close to target_pages."""
        if target_pages <= 8:
            return 1
        elif target_pages <= 14:
            return 2
        elif target_pages <= 22:
            return 3
        elif target_pages <= 30:
            return 4
        elif target_pages <= 50:
            return 6
        elif target_pages <= 80:
            return 8
        elif target_pages <= 100:
            return 10
        else:
            return min(12, max(8, target_pages // 10))


    def _assemble_pages(
        self,
        book_title: str,
        chapters: List[PlannedChapter],
        target_total_pages: int = 40,
    ) -> tuple[List[PlannedPage], List[PlannedPage], List[PlannedPage]]:
        """Pre-allocate all book pages with strict sequential page numbering and exact target budgeting."""
        frontmatter: List[PlannedPage] = []
        backmatter: List[PlannedPage] = []
        all_pages: List[PlannedPage] = []
        curr_page_num = 1

        # 1. Frontmatter
        # Page 1: Cover (always physical page 1)
        p_cover = PlannedPage(
            page_number=curr_page_num,
            page_type=LayoutType.COVER.value,
            layout=LayoutType.COVER.value,
            theme=Theme.DARK,
            brief="High-impact visual book cover.",
        )
        frontmatter.append(p_cover)
        all_pages.append(p_cover)
        curr_page_num += 1

        if target_total_pages <= 12:
            # Compact frontmatter for short books: Title/Imprint & Notice (1 page) + TOC (1 page)
            p_title = PlannedPage(
                page_number=curr_page_num,
                page_type="imprint",
                layout=LayoutType.TEXT_HEAVY.value,
                theme=Theme.LIGHT,
                brief="Title, publisher imprint, and copyright notice.",
            )
            frontmatter.append(p_title)
            all_pages.append(p_title)
            curr_page_num += 1

            p_toc = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.TOC.value,
                layout=LayoutType.TOC.value,
                theme=Theme.LIGHT,
                brief="Table of contents.",
            )
            frontmatter.append(p_toc)
            all_pages.append(p_toc)
            curr_page_num += 1
        else:
            # Full frontmatter: Imprint (1 page), Copyright (1 page), TOC (1 page)
            p_imprint = PlannedPage(
                page_number=curr_page_num,
                page_type="imprint",
                layout=LayoutType.TEXT_HEAVY.value,
                theme=Theme.LIGHT,
                brief="Half-title and publisher imprint.",
            )
            frontmatter.append(p_imprint)
            all_pages.append(p_imprint)
            curr_page_num += 1

            p_copyright = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.COPYRIGHT.value,
                layout=LayoutType.COPYRIGHT.value,
                theme=Theme.LIGHT,
                brief="Copyright notice, versioning, and legal disclaimer.",
            )
            frontmatter.append(p_copyright)
            all_pages.append(p_copyright)
            curr_page_num += 1

            p_toc = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.TOC.value,
                layout=LayoutType.TOC.value,
                theme=Theme.LIGHT,
                brief="Complete structured table of contents.",
            )
            frontmatter.append(p_toc)
            all_pages.append(p_toc)
            curr_page_num += 1

        # Determine backmatter page budget
        if target_total_pages <= 12:
            backmatter_count = 1  # References only
        elif target_total_pages <= 24:
            backmatter_count = 2  # References + Thank You
        else:
            backmatter_count = 3  # References + Acknowledgements + Thank You

        # 2. Strict Page Budgeting for Chapters
        structural_pages = len(all_pages) + backmatter_count + len(chapters)  # cover + front + back + chapter openers
        available_content_pages = max(len(chapters), target_total_pages - structural_pages)

        num_chapters = len(chapters)
        base_budget = available_content_pages // num_chapters
        remainder = available_content_pages % num_chapters

        for i, ch in enumerate(chapters):
            ch_content_budget = base_budget + (1 if i < remainder else 0)
            ch.page_budget = 1 + ch_content_budget  # 1 opener + content pages

        # 3. Chapters
        for ch in chapters:
            # Opener page (Page 1 of chapter budget)
            p_opener = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.CHAPTER_OPENER.value,
                layout=LayoutType.CHAPTER_OPENER.value,
                chapter_number=ch.chapter_number,
                chapter_title=ch.title,
                theme=ch.theme,
                icon=ch.icon,
                brief=f"Chapter {ch.chapter_number} Opener: Lucide icon, number, and title only.",
            )
            all_pages.append(p_opener)
            curr_page_num += 1

            # Content pages in chapter budget (page_budget - 1)
            content_page_count = ch.page_budget - 1
            for cp_idx in range(content_page_count):
                if ch.sections and cp_idx < len(ch.sections):
                    sec = ch.sections[cp_idx]
                    anchor = sec.visual_anchors[0] if sec.visual_anchors else VisualAnchorType.TEXT
                    brief_text = sec.title
                else:
                    sec_idx = cp_idx % len(ch.sections) if ch.sections else 0
                    sec = ch.sections[sec_idx] if ch.sections else None
                    anchor = sec.visual_anchors[cp_idx % len(sec.visual_anchors)] if sec and sec.visual_anchors else VisualAnchorType.TEXT
                    brief_text = f"{sec.title} (Part {cp_idx + 1})" if sec else f"{ch.title} In-Depth Exploration"

                layout_type = LayoutType.EDITORIAL.value
                if anchor == VisualAnchorType.CODE:
                    layout_type = LayoutType.CODE_FOCUS.value
                elif anchor in (VisualAnchorType.COMPARISON, VisualAnchorType.TABLE):
                    layout_type = LayoutType.COMPARISON.value
                elif anchor == VisualAnchorType.DIAGRAM:
                    layout_type = LayoutType.DIAGRAM_FOCUS.value
                elif anchor == VisualAnchorType.STATISTIC:
                    layout_type = LayoutType.LARGE_NUMBER.value
                elif anchor == VisualAnchorType.QUOTE:
                    layout_type = LayoutType.QUOTE.value
                elif anchor == VisualAnchorType.TIMELINE:
                    layout_type = LayoutType.TIMELINE.value

                p_content = PlannedPage(
                    page_number=curr_page_num,
                    page_type="chapter_content",
                    layout=layout_type,
                    chapter_number=ch.chapter_number,
                    chapter_title=ch.title,
                    theme=ch.theme,
                    visual_anchor=anchor,
                    brief=brief_text,
                )
                all_pages.append(p_content)
                curr_page_num += 1

        # 4. Backmatter
        # References Page
        p_refs = PlannedPage(
            page_number=curr_page_num,
            page_type=LayoutType.REFERENCES.value,
            layout=LayoutType.REFERENCES.value,
            theme=Theme.LIGHT,
            brief="Comprehensive bibliography and primary source citations.",
        )
        backmatter.append(p_refs)
        all_pages.append(p_refs)
        curr_page_num += 1

        if backmatter_count >= 3:
            # Acknowledgement Page
            p_ack = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.ACKNOWLEDGEMENT.value,
                layout=LayoutType.ACKNOWLEDGEMENT.value,
                theme=Theme.LIGHT,
                icon="heart",
                brief="Author and institutional acknowledgments.",
            )
            backmatter.append(p_ack)
            all_pages.append(p_ack)
            curr_page_num += 1

        if backmatter_count >= 2:
            # Thank You Page
            p_thanks = PlannedPage(
                page_number=curr_page_num,
                page_type=LayoutType.THANK_YOU.value,
                layout=LayoutType.THANK_YOU.value,
                theme=Theme.DARK,
                icon="sparkles",
                brief="Concluding acknowledgments and publisher note.",
            )
            backmatter.append(p_thanks)
            all_pages.append(p_thanks)

        # Log detailed Page Budget
        frontmatter_count_clean = len(frontmatter) - 1  # excluding cover
        content_count = sum(ch.page_budget - 1 for ch in chapters)
        logger.info(
            f"Page Budget:\n"
            f"  Requested final pages: {target_total_pages}\n"
            f"  Cover: 1\n"
            f"  Front matter: {frontmatter_count_clean}\n"
            f"  Chapter openers: {len(chapters)}\n"
            f"  Content pages: {content_count}\n"
            f"  Back matter: {len(backmatter)}\n"
            f"  Planned total: {len(all_pages)}"
        )

        # Hard validation guard: ensure planned pages stay strictly within allowed variance
        max_variance = 1 if target_total_pages <= 20 else 2
        if abs(len(all_pages) - target_total_pages) > max_variance:
            raise ValueError(
                f"Page planning error: Planned {len(all_pages)} pages for target {target_total_pages}, "
                f"which exceeds allowed variance (±{max_variance})."
            )

        return frontmatter, backmatter, all_pages

    async def generate_book_plan(
        self,
        prompt: str,
        intent: Optional[BookIntent] = None,
        corpus: Optional[ResearchCorpus] = None,
        target_pages: int = 40,
    ) -> BookPlan:
        """Create a complete editorial BookPlan from prompt, intent, and research corpus."""
        if intent is None:
            intent = await self.infer_intent(prompt, corpus)

        title = prompt.strip().title()
        
        # Format subtitle
        if intent.book_type == "beginner_guide":
            subtitle = "A Practical, Hands-On Guide from Zero to Mastery"
        elif intent.book_type == "tutorial_manual":
            subtitle = "A Step-by-Step Developer Tutorial and Code Reference"
        else:
            subtitle = f"A Definitive {intent.book_type.replace('_', ' ').title()}"

        description = (
            f"An authoritative, {intent.technical_depth} guide tailored for {intent.target_audience}, "
            f"covering foundational mental models, progressive code implementations, and practical patterns."
        )

        calculated_chapter_count = intent.chapter_count
        # Adapt chapter count to requested target page budget
        if target_pages <= 14:
            calculated_chapter_count = self.calculate_adaptive_chapter_count(target_pages)
        elif intent and intent.chapter_count and intent.chapter_count != 6:
            calculated_chapter_count = intent.chapter_count
        else:
            calculated_chapter_count = self.calculate_adaptive_chapter_count(target_pages)

        chapters = await self._plan_chapters_with_llm(title, intent, corpus, calculated_chapter_count)

        if not chapters:
            chapters = self._build_deterministic_chapters(title, intent, corpus, calculated_chapter_count)

        frontmatter, backmatter, all_pages = self._assemble_pages(title, chapters, target_total_pages=target_pages)

        return BookPlan(
            title=title,
            subtitle=subtitle,
            description=description,
            intent=intent,
            frontmatter_pages=frontmatter,
            chapters=chapters,
            backmatter_pages=backmatter,
            all_planned_pages=all_pages,
            total_pages=len(all_pages),
        )

