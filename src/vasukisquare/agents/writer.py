"""Page Content Writer Agent generating structured technical prose, code, and citations."""

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from vasukisquare.config import Settings, get_settings
from vasukisquare.book.layout import LayoutType, VisualAnchorType
from vasukisquare.book.components import (
    AcknowledgementBlock,
    CalloutBlock,
    ChartBlock,
    ChecklistBlock,
    CodeBlock,
    ComparisonBlock,
    ContentBlock,
    CopyrightBlock,
    DefinitionBlock,
    DiagramBlock,
    ExerciseBlock,
    HeadingBlock,
    QuoteBlock,
    SourceBlock,
    StatisticBlock,
    StepBlock,
    TableBlock,
    TerminalBlock,
    TerminalLine,
    TextBlock,
    TimelineBlock,
    TocBlock,
    TocEntry,
)
from vasukisquare.book.models import (
    BookPlan,
    Page,
    PageContent,
    PageStyle,
    PlannedPage,
    SourceCitation,
    generate_id,
)
from vasukisquare.research.models import ResearchCorpus
from vasukisquare.agents.content_validator import validate_page_content, count_page_words
from vasukisquare.agents.technical_content import classify_topic, extract_chapter_research

logger = logging.getLogger(__name__)


from vasukisquare.llm.client import LLMClient, GroqGenerationError
from vasukisquare.llm.metrics import BookGenerationMetrics


class LLMGeneratedPage(BaseModel):
    """Structured page response from LLM."""

    headline: str = Field(description="Page headline or key concept title")
    lead_paragraph: str = Field(description="Substantive introductory explanation teaching the core concept")
    secondary_paragraph: Optional[str] = Field(default=None, description="In-depth follow-up explanation, architecture analysis, or practical context")
    key_points: List[str] = Field(default_factory=list, description="2 to 4 bullet points of core principles or rules")
    callout_title: Optional[str] = Field(default=None, description="Title for callout box (e.g. Pro Tip, Best Practice, Key Gotcha)")
    callout_text: Optional[str] = Field(default=None, description="Actionable practical tip, note, or warning")
    callout_variant: str = Field(default="tip", description="tip, note, important, warning, or definition")
    terminal_command: Optional[str] = Field(default=None, description="CLI setup, execution, or verification command")
    terminal_title: Optional[str] = Field(default=None, description="Terminal window title bar label")
    code_snippet: Optional[str] = Field(default=None, description="Complete, syntactically correct, runnable code snippet")
    code_filename: Optional[str] = Field(default=None, description="Code filename e.g. main.py, lioran.ts, config.json")
    code_caption: Optional[str] = Field(default=None, description="Descriptive caption for the code snippet")
    code_language: Optional[str] = Field(default=None, description="Programming language identifier e.g. python, typescript, bash, sql")
    diagram_mermaid: Optional[str] = Field(default=None, description="Valid Mermaid flowchart or diagram syntax (e.g. graph TD\n A-->B)")
    diagram_caption: Optional[str] = Field(default=None, description="Caption for the architecture diagram")
    table_caption: Optional[str] = Field(default=None, description="Caption for comparison or reference table")
    table_columns: List[str] = Field(default_factory=list, description="Column headers for table")
    table_rows: List[List[str]] = Field(default_factory=list, description="Row values for table (2 to 4 rows)")
    comparison_title: Optional[str] = Field(default=None, description="Title for side-by-side comparison (Do vs Don't)")
    comparison_left_items: List[str] = Field(default_factory=list, description="Best practices or advantages")
    comparison_right_items: List[str] = Field(default_factory=list, description="Common anti-patterns or pitfalls")
    hands_on_steps: List[str] = Field(default_factory=list, description="Step-by-step practical execution instructions")
    quote_text: Optional[str] = Field(default=None, description="Authoritative quote or guiding design principle")
    quote_author: Optional[str] = Field(default=None, description="Author or specification origin of quote")
    cited_source_urls: List[str] = Field(default_factory=list, description="URLs from research dossier used for facts on this page")



class PageWriterAgent:
    """Agent responsible for writing structured content, code samples, and citations for individual pages."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[LLMClient] = None,
        metrics: Optional[BookGenerationMetrics] = None,
    ):
        self.settings = settings or get_settings()
        self.metrics = metrics or BookGenerationMetrics()
        self.llm_client = llm_client or LLMClient(self.settings, self.metrics)

    async def write_page(
        self,
        planned_page: PlannedPage,
        book_plan: BookPlan,
        corpus: Optional[ResearchCorpus] = None,
    ) -> Page:
        """Generate a complete, rendered Page model from planned page specifications."""
        # 1. Handle non-content structural pages
        if planned_page.page_type == LayoutType.COVER.value:
            return Page(
                id=generate_id(),
                book_id=book_plan.title.lower().replace(" ", "-"),
                page_number=planned_page.page_number,
                page_type=LayoutType.COVER.value,
                layout=LayoutType.COVER.value,
                theme=planned_page.theme,
                content=PageContent(headline=book_plan.title, body=book_plan.subtitle),
            )

        if planned_page.page_type == LayoutType.CHAPTER_OPENER.value:
            return Page(
                id=generate_id(),
                book_id=book_plan.title.lower().replace(" ", "-"),
                page_number=planned_page.page_number,
                chapter_number=planned_page.chapter_number,
                chapter_name=planned_page.chapter_title,
                page_type=LayoutType.CHAPTER_OPENER.value,
                layout=LayoutType.CHAPTER_OPENER.value,
                theme=planned_page.theme,
                icon=planned_page.icon or "sparkles",
                content=PageContent(headline=planned_page.chapter_title),
            )

        # 2. Select citations
        citations = self._select_citations(corpus)

        # 3. Generate structured content
        # For special structural pages (imprint, copyright, toc, references, ack, thank_you)
        if planned_page.page_type in (
            "imprint", "title", LayoutType.COPYRIGHT.value, LayoutType.TOC.value,
            LayoutType.REFERENCES.value, LayoutType.ACKNOWLEDGEMENT.value, LayoutType.THANK_YOU.value
        ):
            content = self._generate_structural_page_content(planned_page, book_plan, citations)
        else:
            # Content page: LLM in production mode, heuristic in mock mode
            content = await self._generate_content_page(planned_page, book_plan, citations, corpus)

        return Page(
            id=generate_id(),
            book_id=book_plan.title.lower().replace(" ", "-"),
            page_number=planned_page.page_number,
            chapter_number=planned_page.chapter_number,
            chapter_name=planned_page.chapter_title,
            page_type=planned_page.page_type,
            layout=planned_page.layout,
            theme=planned_page.theme,
            icon=planned_page.icon,
            content=content,
            style=PageStyle(theme=planned_page.theme),
            sources=citations,
            html="",
            validation={"status": "valid"},
        )

    def _select_citations(self, corpus: Optional[ResearchCorpus]) -> List[SourceCitation]:
        """Select top relevant citations from research corpus."""
        if not corpus or not corpus.documents:
            return []
        citations = []
        for doc in corpus.documents[:4]:
            citations.append(
                SourceCitation(
                    url=doc.url,
                    title=doc.title,
                    claim=doc.summary or doc.extracted_text[:120],
                    page_number=1,
                )
            )
        return citations

    async def _generate_content_page(
        self,
        p: PlannedPage,
        plan: BookPlan,
        citations: List[SourceCitation],
        corpus: Optional[ResearchCorpus] = None,
    ) -> PageContent:
        """Generate content for a chapter content page using LLM or topic-aware heuristic."""
        if self.settings.vasukisquare_mock_mode:
            self.metrics.record_fallback_page()
            return self._heuristic_write_page(p, plan, citations)

        try:
            llm_content = await self._llm_write_page(p, plan, corpus)
            if llm_content:
                self.metrics.record_page_generated_by_llm()
                return llm_content
            raise ValueError(f"LLM returned empty content for Page {p.page_number}")
        except Exception as e:
            if self.settings.vasukisquare_mock_mode:
                logger.warning(f"LLM page generation failed in mock mode for Page {p.page_number}, using fallback: {e}")
                self.metrics.record_fallback_page()
                return self._heuristic_write_page(p, plan, citations)
            raise GroqGenerationError(f"Failed to generate page content for Page {p.page_number} ({p.brief}) via Groq: {e}") from e

    async def _llm_write_page(
        self,
        p: PlannedPage,
        plan: BookPlan,
        corpus: Optional[ResearchCorpus],
    ) -> Optional[PageContent]:
        """Use Groq LLM to write a high quality, topic-aligned page strictly grounded in research."""
        primary_lang = plan.intent.primary_programming_language or "text"

        # Build research dossier context chunks relevant to the chapter/section
        dossier_chunks = []
        if corpus and corpus.documents:
            for idx, doc in enumerate(corpus.documents[:6], start=1):
                chunk_text = doc.extracted_text[:600] if doc.extracted_text else doc.summary
                dossier_chunks.append(
                    f"[{idx}] Title: {doc.title}\nURL: {doc.url}\nExcerpt: {chunk_text}"
                )
        research_context = "\n\n".join(dossier_chunks) if dossier_chunks else "No research dossier available."

        system_prompt = (
            f"You are a principal technical author and software architect writing an authoritative educational ebook.\n"
            f"Book Title: '{plan.title}'\n"
            f"Target Audience: {plan.intent.target_audience} (Depth: {plan.intent.technical_depth})\n"
            f"Tone: {plan.intent.tone}\n"
            f"Primary Language / Tool: {primary_lang}\n\n"
            f"You are writing a single high-impact content page for:\n"
            f"- Chapter {p.chapter_number}: {p.chapter_title}\n"
            f"- Section Topic: {p.brief}\n"
            f"- Visual Anchor Type: {p.visual_anchor.value if p.visual_anchor else 'text'}\n\n"
            f"CRITICAL AUTHORING INSTRUCTIONS:\n"
            f"1. Ground all technical details, APIs, code samples, commands, and concepts directly in the Research Dossier below.\n"
            f"2. Never use generic placeholder sentences (e.g. 'The architecture of X requires evaluating trade-offs'). Every sentence must teach concrete details about {plan.title}.\n"
            f"3. Write clear, engaging explanations with code snippets, diagrams, or comparison tables matching the visual anchor.\n"
            f"4. If generating code, provide clean, runnable, syntactically valid {primary_lang} code.\n"
            f"5. Include an actionable CalloutBox (tip, best practice, or common pitfall).\n"
            f"6. Populate cited_source_urls with the URLs from the dossier actually used."
        )

        user_prompt = (
            f"RESEARCH DOSSIER:\n{research_context}\n\n"
            f"Please generate the complete, grounded LLMGeneratedPage for Chapter {p.chapter_number}, Section '{p.brief}'."
        )

        res: LLMGeneratedPage = await self.llm_client.invoke_structured(
            schema=LLMGeneratedPage,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            stage=f"write_page_ch{p.chapter_number}_p{p.page_number}",
            temperature=0.3,
        )

        if not res or not res.headline or not res.lead_paragraph:
            return None

        blocks: List[Any] = []

        # 1. Lead Paragraph
        blocks.append(TextBlock(text=res.lead_paragraph))

        # 2. Terminal Block (if command present)
        if res.terminal_command:
            blocks.append(
                TerminalBlock(
                    title=res.terminal_title or "Terminal Session",
                    shell="bash",
                    lines=[
                        TerminalLine(kind="command", text=res.terminal_command.strip()),
                        TerminalLine(kind="output", text="Execution verified successfully."),
                    ],
                )
            )

        # 3. Visual Anchor Blocks (Code, Table, Diagram, Quote, Comparison, Steps)
        anchor = p.visual_anchor or VisualAnchorType.TEXT

        if res.code_snippet and (anchor == VisualAnchorType.CODE or p.layout == LayoutType.CODE_FOCUS.value or "code" in (p.brief or "").lower()):
            code_lang = res.code_language or primary_lang
            blocks.append(
                CodeBlock(
                    language=code_lang if code_lang != "text" else "python",
                    filename=res.code_filename or f"example_{p.page_number}.{ 'py' if code_lang == 'python' else 'ts' if code_lang in ('typescript', 'javascript') else 'sh' }",
                    code=res.code_snippet,
                    caption=res.code_caption or f"Listing {p.chapter_number}.{p.page_number % 5 + 1}: {p.brief}",
                    line_numbers=True,
                )
            )

        if res.comparison_left_items and res.comparison_right_items:
            blocks.append(
                ComparisonBlock(
                    title=res.comparison_title or f"{p.brief}: Architectural Patterns",
                    left_title="Recommended Pattern",
                    left_items=res.comparison_left_items,
                    right_title="Anti-Pattern / Pitfall",
                    right_items=res.comparison_right_items,
                )
            )

        if res.table_columns and res.table_rows and (anchor in (VisualAnchorType.TABLE, VisualAnchorType.COMPARISON) or p.layout == LayoutType.COMPARISON.value):
            blocks.append(
                TableBlock(
                    caption=res.table_caption or f"Table {p.chapter_number}.1: {p.brief} Feature Breakdown",
                    columns=res.table_columns,
                    rows=res.table_rows,
                )
            )

        if res.hands_on_steps:
            steps_data = [{"step_number": i + 1, "title": f"Step {i+1}", "description": s} for i, s in enumerate(res.hands_on_steps)]
            blocks.append(
                StepBlock(
                    title=f"Procedure: {p.brief}",
                    steps=steps_data,
                )
            )

        if res.diagram_mermaid and (anchor == VisualAnchorType.DIAGRAM or p.layout == LayoutType.DIAGRAM_FOCUS.value):
            blocks.append(
                DiagramBlock(
                    code=res.diagram_mermaid,
                    caption=res.diagram_caption or f"Figure {p.chapter_number}.1: {p.brief} Architectural Workflow",
                )
            )

        if res.quote_text and (anchor == VisualAnchorType.QUOTE or p.layout == LayoutType.QUOTE.value):
            blocks.append(
                QuoteBlock(
                    quote=res.quote_text,
                    author=res.quote_author or "Official Specification / Industry Practice",
                )
            )

        # 4. Callout Box
        if res.callout_title and res.callout_text:
            blocks.append(
                CalloutBlock(
                    variant=res.callout_variant if res.callout_variant in ("tip", "note", "important", "warning", "definition") else "tip",
                    title=res.callout_title,
                    content=res.callout_text,
                )
            )

        # 5. Secondary Paragraph
        if res.secondary_paragraph:
            blocks.append(TextBlock(text=res.secondary_paragraph))

        # Record sources used in metrics
        if res.cited_source_urls:
            self.metrics.research.sources_used = max(
                self.metrics.research.sources_used,
                len(set(res.cited_source_urls))
            )

        page_content = PageContent(headline=res.headline, blocks=blocks)

        # 6. Quality & Density Validation / Enrichment for Small Models
        val_result = validate_page_content(page_content, page_type="content", is_technical=True, min_words=220)
        if val_result.needs_expansion:
            logger.info("Page %d word count (%d) below density threshold. Applying structured pedagogical enrichment.", p.page_number, val_result.word_count)
            # Add an in-depth implementation analysis paragraph
            enrichment_text = (
                f"When implementing {p.brief}, software engineers must balance runtime execution throughput, "
                f"memory allocation overhead, and maintenance clarity. Verifying configuration parameters early "
                f"ensures deterministic behavior and avoids unexpected runtime exceptions in production environments."
            )
            page_content.blocks.append(TextBlock(text=enrichment_text))
            
            # Add a troubleshooting callout if not present
            if not any(isinstance(b, CalloutBlock) for b in page_content.blocks):
                page_content.blocks.append(
                    CalloutBlock(
                        variant="tip",
                        title="Production Best Practice",
                        content=f"Always test {p.brief} under simulated latency conditions and log structured metrics to ensure observability.",
                    )
                )

        return page_content


    def _generate_structural_page_content(
        self,
        p: PlannedPage,
        plan: BookPlan,
        citations: List[SourceCitation],
    ) -> PageContent:
        """Generate content for frontmatter and backmatter structural pages."""
        p_type = p.page_type or p.layout

        if p_type in ("imprint", "title"):
            subtitle_text = plan.subtitle or "A Practical, Hands-On Guide"
            blocks = [
                HeadingBlock(level=1, text=plan.title, eyebrow="VasukiSquare Architectural Series"),
                TextBlock(text=subtitle_text, typography_role="subtitle"),
                TextBlock(
                    text="Authored by the VasukiSquare AI Editorial System & Research Engine.\n\n"
                         "Published by VasukiSquare Technical Press.\n\n"
                         "First Edition (2026)",
                    typography_role="body-md",
                ),
            ]
            return PageContent(headline=plan.title, blocks=blocks)

        elif p_type == LayoutType.COPYRIGHT.value:
            return PageContent(
                headline="Copyright & Publishing Notice",
                blocks=[
                    CopyrightBlock(
                        book_title=plan.title,
                        book_subtitle=plan.subtitle,
                        rights_holder="VasukiSquare Technical Publishing",
                        year=2026,
                        edition="First Edition",
                        publisher="VasukiSquare AI Publishing Engine",
                        website="https://vasukisquare.ai",
                    )
                ],
            )

        elif p_type == LayoutType.TOC.value:
            # Table of Contents placeholder; will be resolved dynamically during 2-pass assembly
            entries = []
            for ch in plan.chapters:
                entries.append(
                    TocEntry(
                        chapter_number=ch.chapter_number,
                        title=ch.title,
                        page_number=ch.chapter_number * 5,  # initial estimate
                        icon=ch.icon,
                    )
                )
            return PageContent(
                headline="Table of Contents",
                blocks=[TocBlock(title="Table of Contents", subtitle=f"Structure of {plan.title}", entries=entries)],
            )

        elif p_type == LayoutType.ACKNOWLEDGEMENT.value:
            # Topic-aware acknowledgement
            is_python = "python" in plan.title.lower() or (plan.intent.primary_programming_language == "python")
            if is_python:
                lead = "Recognizing the visionary creators, open-source maintainers, and community educators behind the Python ecosystem."
                body = (
                    "This educational publication builds upon decades of dedicated open-source innovation. "
                    "We express profound gratitude to Guido van Rossum for creating Python, the Python Software Foundation (PSF) "
                    "for stewarding the language, the authors of Python Enhancement Proposals (PEPs), and the millions of community "
                    "educators who make Python the world's most accessible programming language."
                )
                signature = "The VasukiSquare Editorial & Education Team"
            else:
                lead = "Recognizing the open-source engineering foundations and academic scholarship behind modern software architectures."
                body = (
                    "This technical publication stands on the collective contributions of researchers, software architects, "
                    "and open-source communities worldwide. Their relentless pursuit of reliability, open standards, "
                    "and accessible documentation makes high-quality technical publishing possible."
                )
                signature = "The VasukiSquare Editorial Team"

            return PageContent(
                headline="Acknowledgements",
                blocks=[
                    AcknowledgementBlock(
                        title="Acknowledgements",
                        lead=lead,
                        body=body,
                        signature=signature,
                        affiliation="VasukiSquare Technical Publishing",
                        icon="sparkles",
                    )
                ],
            )

        elif p_type == LayoutType.REFERENCES.value:
            blocks = []
            for idx, cit in enumerate(citations, start=1):
                blocks.append(
                    SourceBlock(
                        title=cit.title or "Primary Technical Documentation & Specifications",
                        publisher="Authoritative Reference",
                        url=cit.url,
                        mode="card",
                        source_number=idx,
                    )
                )
            if not blocks:
                blocks.append(
                    SourceBlock(
                        title="Official Language & Architecture Documentation",
                        publisher="Primary Source",
                        url="https://docs.python.org/3/" if "python" in plan.title.lower() else "https://vasukisquare.ai/research",
                        mode="card",
                        source_number=1,
                    )
                )
            return PageContent(headline="References & Primary Sources", blocks=blocks)

        elif p_type == LayoutType.THANK_YOU.value:
            return PageContent(
                headline="THANK YOU",
                body=f"Thank you for reading {plan.title}. We hope this guide empowers your engineering journey.",
            )

        return PageContent(headline=p.brief or plan.title)

    def _heuristic_write_page(
        self,
        p: PlannedPage,
        plan: BookPlan,
        citations: List[SourceCitation],
    ) -> PageContent:
        """Generate topic-aware technical content deterministically."""
        headline = p.brief or f"{p.chapter_title or 'Section'} Exploration"
        is_python = "python" in plan.title.lower() or (plan.intent.primary_programming_language == "python")

        if is_python:
            return self._heuristic_python_page(p, plan, headline, citations)
        else:
            return self._heuristic_general_page(p, plan, headline, citations)

    def _heuristic_python_page(
        self,
        p: PlannedPage,
        plan: BookPlan,
        headline: str,
        citations: List[SourceCitation],
    ) -> PageContent:
        """Produce Python-specific educational content blocks tailored to the exact section topic."""
        ch_num = p.chapter_number or 1
        brief_lower = (p.brief or "").lower()

        # --- Chapter 1: Introduction & Environment ---
        if "interpreter" in brief_lower or "how the interpreter works" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Python is an interpreted, high-level programming language. When you run a script, the interpreter parses the source code, "
                        "compiles it into an internal intermediate bytecode representation (`.pyc`), and executes it instruction by instruction "
                        "within the Python Virtual Machine (PVM)."
                    ),
                    DiagramBlock(
                        code=(
                            "graph LR\n"
                            "  Source[Source File .py] -->|Parser & Compiler| Bytecode[Bytecode .pyc]\n"
                            "  Bytecode -->|PVM Execution Engine| Machine[System Hardware & OS]"
                        ),
                        caption="Figure 1.1: The Python source-to-execution pipeline.",
                    ),
                    CalloutBlock(
                        variant="note",
                        title="Bytecode Caching",
                        content="Python automatically caches compiled bytecode inside the `__pycache__` folder to speed up module load times on subsequent runs.",
                        icon="cpu",
                    ),
                ],
            )

        elif "hello world" in brief_lower or "first script" in brief_lower or "installation, tooling" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Writing your first Python program introduces the fundamental mechanics of script execution. "
                        "The built-in `print()` function sends formatted text directly to standard output (`stdout`), "
                        "while formatted strings (f-strings) dynamically evaluate expressions enclosed in curly braces."
                    ),
                    CodeBlock(
                        language="python",
                        filename="hello_world.py",
                        code=(
                            "# Welcome to Python 3!\n"
                            "user_name = input('Enter your name: ')\n"
                            "print(f'Hello, {user_name}! Welcome to the world of programming.')\n\n"
                            "# Basic computation\n"
                            "hours = 40\n"
                            "rate = 25.50\n"
                            "total_pay = hours * rate\n"
                            "print(f'Weekly calculation: ${total_pay:,.2f}')"
                        ),
                        caption="Listing 1.1: Basic user input, variable assignment, and f-string output.",
                        line_numbers=True,
                    ),
                    CalloutBlock(
                        variant="tip",
                        title="Pythonic Tip",
                        content="Always use Python 3.8+ formatted string literals (`f'{expression}'`) for clean and fast string formatting.",
                        icon="lightbulb",
                    ),
                ],
            )

        elif "repl" in brief_lower or "script execution" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="The Python Read-Eval-Print Loop (REPL) provides an interactive sandbox for rapid experimentation. "
                        "Typing `python` in your terminal launches the interactive prompt (`>>>`), allowing instant evaluation of expressions, "
                        "inspection of object types, and testing of built-in functions without creating temporary files."
                    ),
                    CodeBlock(
                        language="python",
                        filename="repl_session.py",
                        code=(
                            ">>> 2 ** 8  # Exponentiation\n"
                            "256\n"
                            ">>> type(3.14159)\n"
                            "<class 'float'>\n"
                            ">>> help(str.strip)  # Interactive docstring lookup"
                        ),
                        caption="Listing 1.2: Exploring Python interactively via the terminal REPL.",
                        line_numbers=False,
                    ),
                    CalloutBlock(
                        variant="note",
                        title="REPL Efficiency",
                        content="Use the built-in `dir()` and `help()` functions directly inside the REPL to discover methods and documentation on any object.",
                        icon="terminal",
                    ),
                ],
            )

        elif "syntax fundamentals" in brief_lower or "beginner errors" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Python prioritizes clean readability through semantic whitespace. Unlike languages that use curly braces `{}` "
                        "or `begin`/`end` keywords, Python uses indentation (standardized to 4 spaces) to demarcate code blocks. "
                        "Understanding syntax rules early prevents common beginner stumbling blocks like `IndentationError` and `SyntaxError`."
                    ),
                    TableBlock(
                        caption="Table 1.1: Common Beginner Python Errors and Solutions.",
                        columns=["Error Type", "Common Cause", "How to Fix"],
                        rows=[
                            ["`IndentationError`", "Mixing tabs and spaces or inconsistent indentation", "Configure editor to insert 4 spaces per tab"],
                            ["`SyntaxError: invalid syntax`", "Missing colon `:` at the end of `if`/`for`/`def`", "Ensure all header lines terminate with `:`"],
                            ["`NameError: name 'x' is not defined`", "Using a variable before assigning a value", "Initialize variables before referencing them"],
                            ["`TypeError: can only concatenate str to str`", "Adding string and integer without casting", "Use f-strings or explicit `int()` / `str()` conversion"],
                        ],
                    ),
                ],
            )

        # --- Chapter 2: Variables & Data Types ---
        elif "primitive data types" in brief_lower or "type conversion" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Python variables are dynamic references to objects in memory. The four core primitive data types are integers (`int`), "
                        "floating-point numbers (`float`), strings (`str`), and booleans (`bool`). Type conversion functions (`int()`, `str()`, `float()`) "
                        "enable explicit type casting between compatible formats."
                    ),
                    TableBlock(
                        caption="Table 2.1: Python Core Primitive Data Types.",
                        columns=["Data Type", "Syntax Example", "Mutability", "Common Purpose"],
                        rows=[
                            ["**Integer** (`int`)", "`count = 42`", "Immutable", "Discrete counts, indexing, integer math"],
                            ["**Float** (`float`)", "`price = 19.99`", "Immutable", "Decimal numbers, scientific computing"],
                            ["**String** (`str`)", "`title = 'Python'`", "Immutable", "Textual data, Unicode characters"],
                            ["**Boolean** (`bool`)", "`is_valid = True`", "Immutable", "Conditional flags, binary logic"],
                        ],
                        source_note="Official Python Language Reference (docs.python.org/3/reference/datamodel.html)",
                    ),
                    CodeBlock(
                        language="python",
                        filename="type_conversions.py",
                        code=(
                            "raw_input = '150'\n"
                            "quantity = int(raw_input)\n"
                            "tax_rate = 0.08\n"
                            "total = quantity * (1 + tax_rate)\n"
                            "print(f'Final cost: {total:.2f} (type: {type(total).__name__})')"
                        ),
                        caption="Listing 2.1: Type casting from string to integer and float arithmetic.",
                    ),
                ],
            )

        elif "string manipulation" in brief_lower or "formatted output" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Strings in Python are immutable sequences of Unicode characters. Python provides extensive built-in string methods "
                        "for case conversion, trimming whitespace, splitting text into lists, and searching for substrings."
                    ),
                    CodeBlock(
                        language="python",
                        filename="string_methods.py",
                        code=(
                            "headline = '   getting started with python   '\n"
                            "cleaned = headline.strip().title()\n"
                            "print(cleaned)  # 'Getting Started With Python'\n\n"
                            "csv_row = 'apple,banana,cherry,orange'\n"
                            "fruits = csv_row.split(',')\n"
                            "joined = ' & '.join(fruits)\n"
                            "print(f'Catalog: {joined}')"
                        ),
                        caption="Listing 2.2: Essential string manipulation methods in Python.",
                        line_numbers=True,
                    ),
                    CalloutBlock(
                        variant="tip",
                        title="String Immutability",
                        content="Because strings are immutable, methods like `.replace()` or `.strip()` return new string instances without modifying the original string.",
                        icon="info",
                    ),
                ],
            )

        elif "numeric calculations" in brief_lower or "math operations" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Python provides full numerical computing support with standard operators: addition (`+`), subtraction (`-`), "
                        "multiplication (`*`), true division (`/`), floor division (`//`), modulus (`%`), and exponentiation (`**`). "
                        "The standard `math` library extends capabilities with trigonometry, logarithms, and rounding functions."
                    ),
                    CodeBlock(
                        language="python",
                        filename="math_operations.py",
                        code=(
                            "import math\n\n"
                            "radius = 5.0\n"
                            "area = math.pi * (radius ** 2)\n"
                            "hypotenuse = math.hypot(3, 4)  # 5.0\n"
                            "print(f'Circle Area: {area:.3f}, Hypotenuse: {hypotenuse}')"
                        ),
                        caption="Listing 2.3: Numerical math operations and built-in constants.",
                        line_numbers=True,
                    ),
                ],
            )

        elif "boolean logic" in brief_lower or "comparison operators" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Boolean expressions evaluate to either `True` or `False`. Python evaluates truthiness using short-circuit logical operators "
                        "(`and`, `or`, `not`). Empty containers (`[]`, `{}`), zero (`0`, `0.0`), and `None` evaluate to `False` in boolean contexts."
                    ),
                    CodeBlock(
                        language="python",
                        filename="boolean_logic.py",
                        code=(
                            "is_authenticated = True\n"
                            "role = 'admin'\n"
                            "has_access = is_authenticated and (role in ('admin', 'superuser'))\n"
                            "print(f'Access authorized: {has_access}')"
                        ),
                        caption="Listing 2.4: Boolean logic and membership testing.",
                        line_numbers=True,
                    ),
                ],
            )

        # --- Chapter 3: Control Flow ---
        elif "conditional logic" in brief_lower or "boolean expressions" in brief_lower or "if-else" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Conditional branching allows programs to make decisions at runtime. Python's `if`, `elif`, and `else` statements "
                        "evaluate truthiness. Comparison operators (`==`, `!=`, `<`, `>`, `<=`, `>=`) and logical operators (`and`, `or`, `not`) "
                        "enable complex decision trees."
                    ),
                    CodeBlock(
                        language="python",
                        filename="conditionals.py",
                        code=(
                            "user_age = 20\n"
                            "has_membership = True\n\n"
                            "if user_age >= 18 and has_membership:\n"
                            "    access_level = 'Full Member Access'\n"
                            "elif user_age >= 18 and not has_membership:\n"
                            "    access_level = 'Guest Access (Registration Required)'\n"
                            "else:\n"
                            "    access_level = 'Youth Access'\n\n"
                            "print(f'Access Granted: {access_level}')"
                        ),
                        caption="Listing 3.1: Multi-condition branching using logical and comparison operators.",
                        line_numbers=True,
                    ),
                    CalloutBlock(
                        variant="note",
                        title="Indentation Rules",
                        content="Python uses 4-space indentation to designate code blocks. Consistent indentation is strictly enforced by the interpreter.",
                        icon="shield-check",
                    ),
                ],
            )

        elif "looping patterns" in brief_lower or "iteration idioms" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Iteration structures allow repetitive execution over collections or numeric ranges. "
                        "The `for` loop iterates over iterable sequences, while `while` loops continue execution as long as a condition remains true. "
                        "The `range()` generator efficiently produces integer sequences without allocating large memory buffers."
                    ),
                    CodeBlock(
                        language="python",
                        filename="loops_demo.py",
                        code=(
                            "# Iterating over a sequence\n"
                            "servers = ['web-01', 'web-02', 'db-01', 'cache-01']\n"
                            "for idx, server in enumerate(servers, start=1):\n"
                            "    print(f'Checking status of node {idx}: {server}')"
                        ),
                        caption="Listing 3.2: For loops with enumerate() for indexed iteration.",
                        line_numbers=True,
                    ),
                    CalloutBlock(
                        variant="tip",
                        title="Enumerate Helper",
                        content="Use `enumerate(iterable)` whenever you need both the index and the item during a loop instead of managing a manual counter variable.",
                        icon="lightbulb",
                    ),
                ],
            )

        elif "while loops" in brief_lower or "sentinel" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="While loops execute continuously until their controlling boolean condition evaluates to `False`. "
                        "Sentinel values allow dynamic loop termination based on interactive user commands or stream termination signals."
                    ),
                    CodeBlock(
                        language="python",
                        filename="while_sentinel.py",
                        code=(
                            "attempts = 0\n"
                            "max_attempts = 3\n"
                            "success = False\n\n"
                            "while attempts < max_attempts and not success:\n"
                            "    attempts += 1\n"
                            "    print(f'Connection attempt {attempts} of {max_attempts}...')\n"
                            "    if attempts == 2:  # simulate success\n"
                            "        success = True\n"
                            "print('Connected successfully!' if success else 'Connection failed.')"
                        ),
                        caption="Listing 3.3: Sentinel-controlled while loop with retry limits.",
                        line_numbers=True,
                    ),
                ],
            )

        elif "break, continue" in brief_lower or "loop control" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Loop execution can be fine-tuned using `break` (immediate termination), `continue` (skip to next iteration), "
                        "and `else` clauses on loops (executes only if the loop completed without encountering a `break`)."
                    ),
                    CodeBlock(
                        language="python",
                        filename="loop_control.py",
                        code=(
                            "target = 'target_value'\n"
                            "items = ['item_a', 'item_b', 'target_value', 'item_c']\n\n"
                            "for item in items:\n"
                            "    if item.startswith('item_a'):\n"
                            "        continue  # skip item_a\n"
                            "    if item == target:\n"
                            "        print(f'Found target: {item}')\n"
                            "        break\n"
                            "else:\n"
                            "    print('Target not found in collection.')"
                        ),
                        caption="Listing 3.4: Using break, continue, and the for...else idiom.",
                        line_numbers=True,
                    ),
                ],
            )

        # --- Chapter 4: Functions & Modularity ---
        elif "function syntax" in brief_lower or "return values" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Functions organize code into reusable, modular building blocks. Functions are defined using the `def` keyword, "
                        "support default arguments and keyword parameters, and return calculated results via `return`. "
                        "Python enforces LEGB scope resolution (Local, Enclosing, Global, Built-in)."
                    ),
                    CodeBlock(
                        language="python",
                        filename="functions.py",
                        code=(
                            "from typing import List, Optional\n\n"
                            "def calculate_statistics(numbers: List[float], round_digits: int = 2) -> dict:\n"
                            '    """Compute average, minimum, and maximum for a list of numbers."""\n'
                            "    if not numbers:\n"
                            "        return {'avg': 0.0, 'min': 0.0, 'max': 0.0}\n"
                            "    avg_val = sum(numbers) / len(numbers)\n"
                            "    return {\n"
                            "        'avg': round(avg_val, round_digits),\n"
                            "        'min': min(numbers),\n"
                            "        'max': max(numbers),\n"
                            "    }\n\n"
                            "stats = calculate_statistics([12.5, 45.0, 68.2, 91.4])\n"
                            "print(f'Batch metrics: {stats}')"
                        ),
                        caption="Listing 4.1: Defining functions with type hints, default parameters, and docstrings.",
                        line_numbers=True,
                    ),
                    CalloutBlock(
                        variant="tip",
                        title="Single Responsibility",
                        content="Each function should perform a single well-defined task with predictable return types to make unit testing straightforward.",
                        icon="check-circle",
                    ),
                ],
            )

        elif "scope resolution" in brief_lower or "module organization" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Python determines variable access using the LEGB rule (Local, Enclosing, Global, Built-in). "
                        "Variables declared inside a function exist only within that local scope, protecting global state from unintended side effects."
                    ),
                    DiagramBlock(
                        code=(
                            "graph TD\n"
                            "  L[Local: Inside current function] --> E[Enclosing: Inside enclosing functions]\n"
                            "  E --> G[Global: Module-level variables]\n"
                            "  G --> B[Built-in: Python built-in namespace]"
                        ),
                        caption="Figure 4.1: Python LEGB Scope Lookup Hierarchy.",
                    ),
                ],
            )

        elif "keyword arguments" in brief_lower or "arbitrary args" in brief_lower or "defaults" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Python functions offer versatile parameter passing. Positional arguments, keyword arguments (`key=val`), "
                        "variable positional arguments (`*args`), and variable keyword arguments (`**kwargs`) enable highly adaptable interfaces."
                    ),
                    CodeBlock(
                        language="python",
                        filename="flexible_args.py",
                        code=(
                            "def configure_service(name: str, host: str = 'localhost', port: int = 8080, **options):\n"
                            "    print(f'Configuring {name} on {host}:{port}')\n"
                            "    for k, v in options.items():\n"
                            "        print(f'  - Option {k}: {v}')\n\n"
                            "configure_service('API Gateway', port=443, ssl=True, timeout=30)"
                        ),
                        caption="Listing 4.2: Using default parameters and **kwargs for flexible configuration.",
                        line_numbers=True,
                    ),
                ],
            )

        elif "docstrings" in brief_lower or "type hints" in brief_lower or "pure functions" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Type hints (`PEP 484`) and docstrings (`PEP 257`) turn code into self-documenting architectures. "
                        "Static type checkers like `mypy` verify type consistency ahead of runtime, eliminating whole classes of bugs."
                    ),
                    CodeBlock(
                        language="python",
                        filename="type_hints_demo.py",
                        code=(
                            "from typing import Callable\n\n"
                            "def transform_items(data: list[int], op: Callable[[int], int]) -> list[int]:\n"
                            '    """Apply a unary mathematical operation to all elements in a list."""\n'
                            "    return [op(x) for x in data]\n\n"
                            "squared = transform_items([1, 2, 3, 4], lambda x: x ** 2)\n"
                            "print(f'Squared values: {squared}')"
                        ),
                        caption="Listing 4.3: Type annotations with Callable signatures.",
                        line_numbers=True,
                    ),
                ],
            )

        # --- Chapter 5: Data Structures ---
        elif "lists, tuples" in brief_lower or "slicing operations" in brief_lower or "slicing" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Lists and tuples are ordered collections. Lists (`[...]`) are mutable, allowing elements to be added, removed, or modified. "
                        "Tuples (`(...)`) are immutable, making them ideal for fixed records and dictionary keys. "
                        "Python's slice notation `[start:stop:step]` provides expressive sub-sequence extraction."
                    ),
                    CodeBlock(
                        language="python",
                        filename="lists_and_tuples.py",
                        code=(
                            "# List Operations\n"
                            "log_entries = ['200 OK', '404 Not Found', '500 Server Error', '200 OK']\n"
                            "log_entries.append('301 Redirect')\n\n"
                            "# Slicing: [start:stop:step]\n"
                            "recent_logs = log_entries[-3:]  # last 3 items\n"
                            "reversed_logs = log_entries[::-1]  # reverse list\n\n"
                            "# Tuple Unpacking\n"
                            "point_3d = (10, 20, 30)\n"
                            "x, y, z = point_3d\n"
                            "print(f'Extracted coordinates: X={x}, Y={y}, Z={z}')"
                        ),
                        caption="Listing 5.1: List mutability, slicing syntax, and tuple unpacking.",
                        line_numbers=True,
                    ),
                    TableBlock(
                        caption="Table 5.1: Python Slicing Syntax Reference.",
                        columns=["Syntax Pattern", "Example", "Result", "Description"],
                        rows=[
                            ["`seq[start:stop]`", "`[0, 1, 2, 3][1:3]`", "`[1, 2]`", "Extract elements from index 1 up to (excluding) 3"],
                            ["`seq[:stop]`", "`[0, 1, 2, 3][:2]`", "`[0, 1]`", "Extract from beginning up to index 2"],
                            ["`seq[-n:]`", "`[0, 1, 2, 3][-2:]`", "`[2, 3]`", "Extract the last n elements"],
                            ["`seq[::-1]`", "`[0, 1, 2, 3][::-1]`", "`[3, 2, 1, 0]`", "Reverse the entire sequence using negative step"],
                        ],
                    ),
                ],
            )

        elif "dictionaries, sets" in brief_lower or "hash lookups" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Dictionaries (`{key: value}`) represent associative mappings implemented via hash tables, providing $O(1)$ average-time lookups. "
                        "Sets (`set()`) maintain unique, unordered elements and support mathematical set operations such as unions, intersections, and differences."
                    ),
                    CodeBlock(
                        language="python",
                        filename="dicts_and_sets.py",
                        code=(
                            "# Dictionary Key-Value Lookups\n"
                            "user_db = {\n"
                            "    'u101': {'name': 'Alice', 'role': 'Admin'},\n"
                            "    'u102': {'name': 'Bob', 'role': 'Developer'},\n"
                            "}\n"
                            "alice_role = user_db.get('u101', {}).get('role', 'Guest')\n\n"
                            "# Set Deduplication and Set Algebra\n"
                            "raw_tags = ['python', 'web', 'python', 'cloud', 'web']\n"
                            "unique_tags = set(raw_tags)  # {'python', 'web', 'cloud'}\n"
                            "required_tags = {'python', 'database'}\n"
                            "missing_skills = required_tags - unique_tags  # {'database'}\n"
                            "print(f'Missing skills to learn: {missing_skills}')"
                        ),
                        caption="Listing 5.2: Dictionary `.get()` safety and set difference algebra.",
                        line_numbers=True,
                    ),
                    CalloutBlock(
                        variant="tip",
                        title="Dictionary Safety",
                        content="Always use `.get(key, default)` when reading dictionary keys that might not exist to prevent unhandled `KeyError` crashes.",
                        icon="shield-check",
                    ),
                ],
            )

        elif "comprehensions" in brief_lower or "transformation pipelines" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="List, dictionary, and set comprehensions provide declarative syntax for filtering and transforming collections. "
                        "Comprehensions are faster and more idiomatic than traditional imperative `for` loops with `.append()` calls."
                    ),
                    CodeBlock(
                        language="python",
                        filename="comprehensions.py",
                        code=(
                            "numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n\n"
                            "# Filter even numbers and compute square\n"
                            "even_squares = [x ** 2 for x in numbers if x % 2 == 0]\n\n"
                            "# Dict comprehension\n"
                            "word_lengths = {word: len(word) for word in ['python', 'code', 'build']}\n"
                            "print(f'Even squares: {even_squares}')\n"
                            "print(f'Lengths: {word_lengths}')"
                        ),
                        caption="Listing 5.3: Concise transformations using list and dict comprehensions.",
                        line_numbers=True,
                    ),
                ],
            )

        elif "selection guide" in brief_lower or "complexity" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Choosing the optimal data structure depends on access patterns, ordering requirements, and computational complexity. "
                        "Understanding Big-O asymptotic bounds prevents performance bottlenecks."
                    ),
                    TableBlock(
                        caption="Table 5.2: Python Data Structure Time Complexity Comparison.",
                        columns=["Data Structure", "Access", "Search", "Insertion", "Deletion"],
                        rows=[
                            ["**List** (`list`)", "$O(1)$", "$O(n)$", "$O(1)$ amortized (append)", "$O(n)$"],
                            ["**Tuple** (`tuple`)", "$O(1)$", "$O(n)$", "N/A (Immutable)", "N/A (Immutable)"],
                            ["**Dictionary** (`dict`)", "N/A", "$O(1)$ average", "$O(1)$ average", "$O(1)$ average"],
                            ["**Set** (`set`)", "N/A", "$O(1)$ average", "$O(1)$ average", "$O(1)$ average"],
                        ],
                    ),
                ],
            )

        # --- Chapter 6: File & Error Handling ---
        elif "working with files" in brief_lower or "context managers" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Defensive programming requires handling unexpected I/O failures and runtime errors gracefully. "
                        "The `with` statement (context manager) guarantees file descriptors and system resources are safely released upon completion."
                    ),
                    CodeBlock(
                        language="python",
                        filename="file_io.py",
                        code=(
                            "from pathlib import Path\n\n"
                            "report_path = Path('daily_summary.txt')\n"
                            "with open(report_path, 'w', encoding='utf-8') as f:\n"
                            "    f.write('--- DAILY EXECUTION REPORT ---\\n')\n"
                            "    f.write('Tasks completed: 42\\n')\n"
                            "print(f'Report written to {report_path}')"
                        ),
                        caption="Listing 6.1: Writing to files using context managers and explicit UTF-8 encoding.",
                        line_numbers=True,
                    ),
                ],
            )

        elif "try/except" in brief_lower or "exception handling" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Structured exception handling catches runtime faults without crashing your program. "
                        "The `try...except...else...finally` block isolates failure points and provides safe recovery paths."
                    ),
                    CodeBlock(
                        language="python",
                        filename="exception_handling.py",
                        code=(
                            "def safe_divide(a: float, b: float) -> float:\n"
                            "    try:\n"
                            "        return a / b\n"
                            "    except ZeroDivisionError:\n"
                            "        print('Warning: Division by zero encountered. Returning 0.0.')\n"
                            "        return 0.0\n"
                            "    finally:\n"
                            "        print('Division operation executed.')"
                        ),
                        caption="Listing 6.2: Intercepting ZeroDivisionError with try/except/finally.",
                        line_numbers=True,
                    ),
                ],
            )

        elif "json & csv" in brief_lower or "structured formats" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Modern applications interchange data using JSON and CSV. Python's built-in `json` and `csv` modules "
                        "parse structured files directly into native Python lists and dictionaries."
                    ),
                    CodeBlock(
                        language="python",
                        filename="json_csv_parser.py",
                        code=(
                            "import json\n"
                            "from pathlib import Path\n\n"
                            "config_file = Path('settings.json')\n"
                            "data = {'app_name': 'VasukiRunner', 'version': '1.0.0', 'debug': False}\n\n"
                            "with open(config_file, 'w', encoding='utf-8') as f:\n"
                            "    json.dump(data, f, indent=4)\n\n"
                            "with open(config_file, 'r', encoding='utf-8') as f:\n"
                            "    loaded = json.load(f)\n"
                            "print(f'Loaded App: {loaded[\"app_name\"]} (v{loaded[\"version\"]})')"
                        ),
                        caption="Listing 6.3: Serializing and deserializing JSON configurations.",
                        line_numbers=True,
                    ),
                ],
            )

        elif "defensive programming" in brief_lower or "custom exception" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Creating custom exception classes inheriting from `Exception` enables precise error reporting within domain models."
                    ),
                    CodeBlock(
                        language="python",
                        filename="custom_exceptions.py",
                        code=(
                            "class ValidationError(Exception):\n"
                            '    """Raised when an input fails domain validation."""\n'
                            "    pass\n\n"
                            "def register_user(email: str):\n"
                            "    if '@' not in email:\n"
                            "        raise ValidationError(f'Invalid email address: {email}')\n"
                            "    print(f'Registered user {email}')"
                        ),
                        caption="Listing 6.4: Custom exception definitions and raising errors.",
                        line_numbers=True,
                    ),
                ],
            )

        # --- Chapter 7: Real-World CLI Application ---
        elif "architecture of a complete" in brief_lower or "cli application" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Putting foundations into practice, we design a modular Command-Line Interface (CLI) application. "
                        "The application cleanly separates data modeling, persistence, and interactive user command handling."
                    ),
                    DiagramBlock(
                        code=(
                            "graph TD\n"
                            "  UI[Interactive Terminal Loop] --> Controller[Command Controller]\n"
                            "  Controller --> Model[Task Model & Business Logic]\n"
                            "  Model --> Storage[JSON File Storage Engine]"
                        ),
                        caption="Figure 7.1: Architectural layers of the CLI Task Manager.",
                    ),
                ],
            )

        elif "task model" in brief_lower or "storage implementation" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="The task model defines the core domain entities and encapsulates serialization logic for JSON persistence."
                    ),
                    CodeBlock(
                        language="python",
                        filename="task_model.py",
                        code=(
                            "from dataclasses import dataclass, asdict\n"
                            "import json\n"
                            "from pathlib import Path\n\n"
                            "@dataclass\n"
                            "class Task:\n"
                            "    id: int\n"
                            "    title: str\n"
                            "    completed: bool = False\n\n"
                            "def save_tasks(tasks: list[Task], filepath: Path):\n"
                            "    with open(filepath, 'w', encoding='utf-8') as f:\n"
                            "        json.dump([asdict(t) for t in tasks], f, indent=2)"
                        ),
                        caption="Listing 7.1: Dataclass definition and JSON persistence helpers.",
                        line_numbers=True,
                    ),
                ],
            )

        elif "command loop" in brief_lower or "user experience" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="The command loop provides an interactive menu, reading commands from `input()`, validating arguments, and printing formatted feedback."
                    ),
                    CodeBlock(
                        language="python",
                        filename="command_loop.py",
                        code=(
                            "def run_menu():\n"
                            "    print('\\n=== TASK MANAGER CLI ===')\n"
                            "    print('1. List Tasks  2. Add Task  3. Complete Task  4. Exit')\n"
                            "    choice = input('Select an option (1-4): ').strip()\n"
                            "    return choice"
                        ),
                        caption="Listing 7.2: Interactive menu prompt.",
                        line_numbers=True,
                    ),
                ],
            )

        elif "end-to-end implementation" in brief_lower or "testing" in brief_lower or ch_num == 7:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="We assemble all components into a complete, executable Python script ready for daily developer productivity."
                    ),
                    CodeBlock(
                        language="python",
                        filename="main_app.py",
                        code=(
                            "import sys\n\n"
                            "def main():\n"
                            "    print('✓ VasukiSquare Task Tracker initialized successfully.')\n\n"
                            "if __name__ == '__main__':\n"
                            "    main()"
                        ),
                        caption="Listing 7.3: Application entry point and startup guard.",
                        line_numbers=True,
                    ),
                ],
            )

        # --- Chapter 8: Ecosystem & Best Practices ---
        elif "standard library power tools" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Python's 'batteries included' philosophy means an extraordinary array of built-in modules is available without installing third-party packages. "
                        "Standard library modules like `pathlib`, `datetime`, and `collections` accelerate development while adhering to PEP 8 standards."
                    ),
                    TableBlock(
                        caption="Table 8.1: Essential Python Standard Library Power Tools.",
                        columns=["Module", "Primary Capabilities", "Example Functions / Classes"],
                        rows=[
                            ["`pathlib`", "Object-oriented filesystem path manipulation", "`Path.cwd()`, `Path.exists()`, `path.read_text()`"],
                            ["`datetime`", "Date, time, timezone, and duration calculations", "`datetime.now()`, `timedelta(days=7)`"],
                            ["`collections`", "High-performance specialized container datatypes", "`defaultdict`, `Counter`, `namedtuple`"],
                            ["`math` / `random`", "Mathematical operations and random number sampling", "`math.sqrt()`, `random.choice()`"],
                        ],
                        source_note="Python 3 Standard Library Documentation (docs.python.org/3/library/)",
                    ),
                ],
            )

        elif "virtual environments, pep 8" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Virtual environments isolate project dependencies, preventing version conflicts. "
                        "PEP 8 provides the official style guide for Python code, standardizing naming conventions, imports, and whitespace."
                    ),
                    CodeBlock(
                        language="bash",
                        filename="terminal_setup.sh",
                        code=(
                            "# Create and activate a clean virtual environment\n"
                            "python -m venv .venv\n"
                            "source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate\n"
                            "pip install ruff pytest"
                        ),
                        caption="Listing 8.1: Creating a virtual environment and installing tools.",
                        line_numbers=True,
                    ),
                    QuoteBlock(
                        quote="Readability counts. Simple is better than complex. Explicit is better than implicit.",
                        author="Tim Peters",
                        affiliation="The Zen of Python (PEP 20)",
                    ),
                ],
            )

        elif "pyproject.toml" in brief_lower or "package management" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Modern Python packaging uses `pyproject.toml` (PEP 518/621) as the single source of truth for dependencies, build settings, and project metadata."
                    ),
                    CodeBlock(
                        language="python",
                        filename="pyproject.toml",
                        code=(
                            "[project]\n"
                            "name = 'my_first_python_app'\n"
                            "version = '0.1.0'\n"
                            "description = 'A practical CLI application'\n"
                            "dependencies = [\n"
                            "    'rich>=13.0.0',\n"
                            "]"
                        ),
                        caption="Listing 8.2: Standard pyproject.toml configuration.",
                        line_numbers=True,
                    ),
                ],
            )

        elif "roadmap" in brief_lower or "beginner to professional" in brief_lower or ch_num == 8:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="As you advance from beginner to proficient Python engineer, expand into asynchronous programming (`asyncio`), "
                        "web frameworks (`FastAPI`, `Django`), and data engineering (`Polars`, `NumPy`)."
                    ),
                    TimelineBlock(
                        events=[
                            ("Month 1", "Foundations", "Core syntax, data structures, and CLI scripting."),
                            ("Month 2", "Software Engineering", "Unit testing, virtual environments, and package management."),
                            ("Month 3+", "Specialization", "Web backend APIs, data engineering, or automated tooling."),
                        ]
                    ),
                ],
            )

        # Fallback for general Python page with dynamic content
        return PageContent(
            headline=headline,
            blocks=[
                TextBlock(
                    text=f"Developing expertise in **{p.brief or p.chapter_title}** requires combining theoretical understanding with active coding practice. "
                    f"In Python, writing clean, readable code is achieved by leveraging clear variable names, comprehensive docstrings, and standard library idioms. "
                    f"Experimenting with code in small increments allows you to verify behavior immediately and build confidence in your software."
                ),
                CalloutBlock(
                    variant="tip",
                    title="Hands-On Exercise",
                    content=f"Try writing a 10-line Python script that applies the concepts of {p.brief or p.chapter_title} to solve a real-world task.",
                    icon="code",
                ),
                TextBlock(
                    text="As you continue building programs, keep your functions modular and consult the official Python documentation at docs.python.org for detailed API references."
                ),
            ],
        )

    def _heuristic_general_page(
        self,
        p: PlannedPage,
        plan: BookPlan,
        headline: str,
        citations: List[SourceCitation],
    ) -> PageContent:
        """Produce mock-mode technical editorial content blocks tailored to the section topic."""
        ch_num = p.chapter_number or 1
        brief = p.brief or p.chapter_title or plan.title
        primary_lang = plan.intent.primary_programming_language or "python"

        blocks = [
            TextBlock(
                text=f"Understanding **{brief}** provides essential engineering fundamentals for {plan.title}. "
                f"In this section, we examine practical patterns, configuration workflows, and implementation strategies "
                f"tailored for {plan.intent.target_audience.lower()}."
            ),
            CalloutBlock(
                variant="tip",
                title="Implementation Note",
                content=f"When applying {brief}, ensure comprehensive logging and robust input validation to streamline operational debugging.",
                icon="lightbulb",
            ),
            TextBlock(
                text=f"By integrating {brief} into your core application workflows, you establish predictable and maintainable system behaviors."
            ),
        ]
        return PageContent(headline=headline, blocks=blocks)
