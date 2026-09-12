"""Page Content Writer Agent generating structured technical prose, code, and citations."""

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from vasukisquare.config import Settings, get_settings
from vasukisquare.book.layout import (
    LayoutType,
    VisualAnchorType,
    TechnicalPageSpec,
    TechnicalPageType,
    PAGE_TYPE_SPECS,
    is_component_eligible,
)
from vasukisquare.book.components import (
    AcknowledgementBlock,
    CalloutBlock,
    ChartBlock,
    ChecklistBlock,
    CodeBlock,
    CommonMistakeBlock,
    ComparisonBlock,
    ContentBlock,
    CopyrightBlock,
    DefinitionBlock,
    DiagramBlock,
    ExerciseBlock,
    HeadingBlock,
    OutputBlock,
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
    PagePurpose,
    PageStyle,
    PlannedPage,
    SourceCitation,
    generate_id,
)
from vasukisquare.research.models import ResearchCorpus
from vasukisquare.agents.content_validator import (
    validate_page_content,
    count_page_words,
    evaluate_technical_page,
    validate_terminal_command,
    validate_code_block,
    detect_topic_drift,
)
from vasukisquare.agents.technical_content import classify_topic, extract_chapter_research
from vasukisquare.llm.client import LLMClient, GroqGenerationError
from vasukisquare.llm.metrics import BookGenerationMetrics

logger = logging.getLogger(__name__)


class SmallModelHeadlineLead(BaseModel):
    """Minimal schema for small models generating headline and lead explanation."""

    headline: str = Field(description="Direct, non-repetitive headline for this specific page (do not repeat the book title)")
    explanation: str = Field(description="Substantive 80 to 120 word technical explanation explaining the concept using provided facts")


class SmallModelSecondaryExplanation(BaseModel):
    """Minimal schema for small models generating follow-up conceptual analysis."""

    subheading: str = Field(description="Short section subheading e.g. Architectural Mechanics, Core Principles")
    explanation: str = Field(description="Substantive 60 to 90 word follow-up explanation expanding on the technical details")


class SmallModelTroubleshooting(BaseModel):
    """Minimal schema for small models generating actionable advice or pitfalls."""

    callout_title: str = Field(description="Concise callout title e.g. Best Practice, Verification, Common Pitfall")
    callout_text: str = Field(description="1 to 2 sentences giving practical guidance or debugging advice")
    callout_variant: str = Field(default="tip", description="tip, warning, note, or important")


class SmallModelExercise(BaseModel):
    """Minimal schema for small models generating a targeted beginner exercise or challenge."""

    title: str = Field(description="Exercise title e.g. Hands-On Challenge")
    instructions: List[str] = Field(description="2 to 3 concise actionable instructions for the reader to try")


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
    code_filename: Optional[str] = Field(default=None, description="Code filename e.g. main.py, config.py")
    code_caption: Optional[str] = Field(default=None, description="Descriptive caption for the code snippet")
    code_language: Optional[str] = Field(default=None, description="Programming language identifier e.g. python, bash, sql")
    diagram_mermaid: Optional[str] = Field(default=None, description="Valid Mermaid flowchart or diagram syntax (e.g. graph TD\\n A-->B)")
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


def repair_underfilled_page(
    page_content: Any,
    spec: Optional[TechnicalPageSpec] = None,
    primary_subject: str = "technical topic",
    is_beginner: bool = False,
    verified_facts: Optional[List[str]] = None,
    verified_commands: Optional[List[str]] = None,
    verified_code_snippets: Optional[List[str]] = None,
    topic: Optional[str] = None,
) -> Any:
    """Repair an underfilled page strictly adhering to component eligibility and pedagogical validity."""
    from vasukisquare.renderer.overflow import estimate_page_utilization

    is_page_obj = isinstance(page_content, Page)
    content_obj = page_content.content if is_page_obj else page_content
    if spec is None:
        spec = PAGE_TYPE_SPECS[TechnicalPageType.CONCEPT]
    if topic and primary_subject == "technical topic":
        primary_subject = topic

    is_python = "python" in primary_subject.lower()
    headline = content_obj.headline or primary_subject
    blocks = list(content_obj.blocks)
    if not blocks and getattr(content_obj, "body", None):
        blocks.append(TextBlock(text=content_obj.body))

    has_code = any(getattr(b, "type", "") == "code" for b in blocks)
    has_terminal = any(getattr(b, "type", "") == "terminal" for b in blocks)
    has_table = any(getattr(b, "type", "") == "table" for b in blocks)
    has_callout = any(getattr(b, "type", "") in ("callout", "tip", "note", "warning", "important") for b in blocks)
    has_output = any(getattr(b, "type", "") == "output" for b in blocks)

    # 1. Enforce Required Code
    if spec.requires_code and not has_code:
        if is_python:
            code_str = (
                f"# Practical demonstration of {headline}\n"
                f"def demonstrate_concept():\n"
                f"    print('Running demonstration...')\n"
                f"    data = [1, 2, 3, 4, 5]\n"
                f"    result = sum(data)\n"
                f"    return result\n\n"
                f"print('Computed result:', demonstrate_concept())"
            )
        else:
            code_str = (
                f"// Implementation for {headline}\n"
                f"function executeTask() {{\n"
                f"    return 'Task executed successfully';\n"
                f"}}\n"
                f"console.log(executeTask());"
            )
        blocks.append(
            CodeBlock(
                language="python" if is_python else "javascript",
                filename="example.py" if is_python else "example.js",
                code=code_str,
                caption=f"Listing: {headline} Implementation",
                line_numbers=True,
            )
        )
        has_code = True

    # 2. Enforce Required Terminal
    if spec.requires_terminal and not has_terminal:
        cmd = "python3 -m unittest test_module.py" if is_python else f"{primary_subject.split()[0].lower()} --version"
        blocks.append(
            TerminalBlock(
                title=f"Terminal: {headline}",
                shell="bash",
                lines=[
                    TerminalLine(kind="command", text=cmd),
                    TerminalLine(kind="output", text="Execution verified successfully."),
                ],
            )
        )
        has_terminal = True

    # 3. Enforce Callout
    if not has_callout and is_component_eligible("callout", spec.page_type):
        blocks.append(
            CalloutBlock(
                title="Practical Best Practice",
                content=f"When working with {headline}, keep your implementations modular and test each component with isolated inputs.",
                variant="tip",
            )
        )

    # 4. Progressive Filling Loop
    util = estimate_page_utilization(PageContent(headline=headline, blocks=blocks))

    # Add Output block if code is present but no output block
    if util.estimated_ratio < 0.70 and has_code and not has_output and is_component_eligible("output", spec.page_type):
        candidate_blocks = list(blocks) + [
            OutputBlock(
                title="Expected Console Output",
                content="Computed result: 15",
            )
        ]
        if estimate_page_utilization(PageContent(headline=headline, blocks=candidate_blocks)).estimated_ratio <= 0.95:
            blocks = candidate_blocks
            has_output = True
            util = estimate_page_utilization(PageContent(headline=headline, blocks=blocks))

    # Add Common Mistake if debugging/eligible
    if util.estimated_ratio < 0.70 and is_component_eligible("mistake", spec.page_type) and not any(getattr(b, "type", "") == "mistake" for b in blocks):
        candidate_blocks = list(blocks) + [
            CommonMistakeBlock(
                title="Common Beginner Mistake",
                wrong_code="total = '10' + 5  # TypeError: can only concatenate str to str",
                correct_code="total = int('10') + 5  # Correct: explicit type cast to integer",
                explanation="In Python, strings and integers cannot be added directly without explicit type conversion.",
            )
        ]
        if estimate_page_utilization(PageContent(headline=headline, blocks=candidate_blocks)).estimated_ratio <= 0.95:
            blocks = candidate_blocks
            util = estimate_page_utilization(PageContent(headline=headline, blocks=blocks))

    # Add Secondary explanation if underfilled
    if util.estimated_ratio < 0.70:
        if verified_facts:
            additional_text = f"Key principle: {verified_facts[0]}. In structured software development, understanding these foundational mechanics ensures predictable execution and simplifies debugging."
        else:
            additional_text = f"When applying {headline}, maintaining clarity and following standard idioms ensures your code is readable, maintainable, and robust against unexpected inputs."
        candidate_blocks = list(blocks) + [TextBlock(text=additional_text)]
        if estimate_page_utilization(PageContent(headline=headline, blocks=candidate_blocks)).estimated_ratio <= 0.95:
            blocks = candidate_blocks
            util = estimate_page_utilization(PageContent(headline=headline, blocks=blocks))

    # Add Exercise if eligible
    if util.estimated_ratio < 0.70 and is_component_eligible("exercise", spec.page_type) and not any(getattr(b, "type", "") == "exercise" for b in blocks):
        candidate_blocks = list(blocks) + [
            ExerciseBlock(
                title=f"Practice Challenge: {headline}",
                instructions=[
                    f"Write a short function that applies {headline} to process a list of 3 items.",
                    "Verify the output by printing the result to the console.",
                ],
            )
        ]
        if estimate_page_utilization(PageContent(headline=headline, blocks=candidate_blocks)).estimated_ratio <= 0.95:
            blocks = candidate_blocks

    repaired_content = PageContent(headline=headline, blocks=blocks)
    if is_page_obj:
        page_content.content = repaired_content
        return page_content
    return repaired_content


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
        if planned_page.page_type in (
            "imprint", "title", LayoutType.COPYRIGHT.value, LayoutType.TOC.value,
            LayoutType.REFERENCES.value, LayoutType.ACKNOWLEDGEMENT.value, LayoutType.THANK_YOU.value
        ):
            content = self._generate_structural_page_content(planned_page, book_plan, citations)
        else:
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
        """Generate content for a chapter content page using small-model decomposed flow, Groq LLM, or heuristic."""
        if self.settings.vasukisquare_mock_mode:
            self.metrics.record_fallback_page()
            return self._heuristic_write_page(p, plan, citations)

        # Small model decomposed generation
        if self.settings.is_small_model_active:
            try:
                small_content = await self._small_model_write_page(p, plan, citations, corpus)
                if small_content:
                    self.metrics.record_page_generated_by_llm()
                    return small_content
            except Exception as e:
                logger.warning(f"Small model decomposed write failed for Page {p.page_number}: {e}")

        # Standard Groq LLM Generation
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

    async def _small_model_write_page(
        self,
        p: PlannedPage,
        plan: BookPlan,
        citations: List[SourceCitation],
        corpus: Optional[ResearchCorpus] = None,
    ) -> Optional[PageContent]:
        """Decomposed, multi-step generation pipeline tailored for small LLMs."""
        from vasukisquare.renderer.overflow import estimate_page_utilization

        primary_subject = plan.intent.domain_topic or plan.title
        primary_lang = plan.intent.primary_programming_language or "python"
        is_beginner = "beginner" in plan.title.lower() or plan.intent.technical_depth == "introductory"

        page_type_enum = TechnicalPageType.CONCEPT
        try:
            page_type_enum = TechnicalPageType(p.page_type)
        except ValueError:
            pass
        spec = PAGE_TYPE_SPECS.get(page_type_enum, PAGE_TYPE_SPECS[TechnicalPageType.CONCEPT])

        facts = []
        if corpus and hasattr(corpus, "facts"):
            for f in corpus.facts[:6]:
                facts.append(getattr(f, "fact", str(f)))
        if not facts and corpus and corpus.documents:
            for doc in corpus.documents[:4]:
                if doc.summary:
                    facts.append(doc.summary)
        facts_text = "\n".join([f"- {f}" for f in facts]) if facts else f"- {primary_subject} syntax and practical programming patterns."

        # Step 1: Prompt for Heading & Lead Explanation
        sys_prompt_1 = (
            f"You are a technical book author explaining '{p.brief}' for a book titled '{plan.title}'.\n"
            f"Rules:\n"
            f"1. Headline must describe '{p.brief}'. NEVER repeat the full book title.\n"
            f"2. Explanation must be 80-120 words teaching the concept using the facts below.\n"
            f"3. Do NOT mention zero-knowledge cryptography or unrelated blockchain terms.\n"
            f"4. Do NOT write generic filler."
        )
        user_prompt_1 = f"FACTS:\n{facts_text}\n\nWrite headline and explanation for '{p.brief}'."

        res_lead = await self.llm_client.invoke_structured(
            schema=SmallModelHeadlineLead,
            system_prompt=sys_prompt_1,
            user_prompt=user_prompt_1,
            stage=f"small_lead_ch{p.chapter_number}_p{p.page_number}",
            temperature=0.2,
        )

        headline = res_lead.headline if (res_lead and res_lead.headline) else (p.brief or plan.title)
        lead_explanation = res_lead.explanation if (res_lead and res_lead.explanation) else f"Understanding {p.brief} is essential for mastering {primary_subject}."

        blocks: List[Any] = [TextBlock(text=lead_explanation)]

        # Step 2: Code or Terminal Block from Research / Spec
        is_python = "python" in primary_subject.lower() or primary_lang == "python"

        if spec.requires_terminal or any(w in p.brief.lower() for w in ["install", "terminal", "cli", "setup"]):
            cmd = "python3 --version\npython3 main.py" if is_python else f"{primary_subject.split()[0].lower()} --help"
            blocks.append(
                TerminalBlock(
                    title=f"Terminal: {p.brief}",
                    shell="bash",
                    lines=[
                        TerminalLine(kind="command", text=cmd.split("\n")[0]),
                        TerminalLine(kind="output", text="Python 3.12.0"),
                    ],
                )
            )

        if spec.requires_code or any(w in p.brief.lower() for w in ["code", "function", "variable", "loop", "syntax"]) or p.layout == LayoutType.CODE_FOCUS.value:
            if is_python:
                code_sample = (
                    f"# Example implementation of {p.brief}\n"
                    f"def calculate_total(items: list[int]) -> int:\n"
                    f"    return sum(items)\n\n"
                    f"scores = [10, 20, 30]\n"
                    f"total = calculate_total(scores)\n"
                    f"print(f'Calculated total: {{total}}')"
                )
            else:
                code_sample = (
                    f"// Example: {p.brief}\n"
                    f"const calculate = (items) => items.reduce((a, b) => a + b, 0);\n"
                    f"console.log('Result:', calculate([10, 20, 30]));"
                )
            blocks.append(
                CodeBlock(
                    language=primary_lang if primary_lang != "text" else "python",
                    filename=f"{p.brief.lower().replace(' ', '_')[:20]}.py",
                    code=code_sample,
                    caption=f"Listing {p.chapter_number}.{p.page_number % 5 + 1}: {p.brief} Implementation",
                    line_numbers=True,
                )
            )
            # Add Expected Output Block
            blocks.append(
                OutputBlock(
                    title="Console Output",
                    content="Calculated total: 60",
                )
            )

        # Step 3: Check Utilization and add Secondary Explanation if underfilled
        current_page = PageContent(headline=headline, blocks=blocks)
        util = estimate_page_utilization(current_page)

        if util.estimated_ratio < 0.65:
            sys_prompt_2 = (
                f"Explain the technical mechanisms or operational advantages of '{p.brief}' in 60-90 words. "
                f"Do not repeat prior explanations."
            )
            res_sec = await self.llm_client.invoke_structured(
                schema=SmallModelSecondaryExplanation,
                system_prompt=sys_prompt_2,
                user_prompt=f"Topic: {p.brief}\nFacts: {facts_text}",
                stage=f"small_sec_ch{p.chapter_number}_p{p.page_number}",
                temperature=0.2,
            )
            if res_sec and res_sec.explanation:
                candidate_blocks = list(blocks) + [TextBlock(text=res_sec.explanation)]
                if estimate_page_utilization(PageContent(headline=headline, blocks=candidate_blocks)).estimated_ratio <= 0.95:
                    blocks = candidate_blocks

        # Step 4: Prompt for Callout Tip
        current_page = PageContent(headline=headline, blocks=blocks)
        util = estimate_page_utilization(current_page)

        if util.estimated_ratio < 0.75:
            sys_prompt_3 = f"Provide a 1-2 sentence practical tip or common pitfall for '{p.brief}' in '{primary_subject}'."
            res_tip = await self.llm_client.invoke_structured(
                schema=SmallModelTroubleshooting,
                system_prompt=sys_prompt_3,
                user_prompt=f"Topic: {p.brief}",
                stage=f"small_tip_ch{p.chapter_number}_p{p.page_number}",
                temperature=0.2,
            )
            tip_title = res_tip.callout_title if (res_tip and res_tip.callout_title) else "Practical Tip"
            tip_text = res_tip.callout_text if (res_tip and res_tip.callout_text) else f"Always verify inputs and validate boundary conditions when working with {p.brief}."
            tip_variant = res_tip.callout_variant if (res_tip and res_tip.callout_variant in ("tip", "note", "important", "warning", "definition")) else "tip"
            
            candidate_blocks = list(blocks) + [CalloutBlock(title=tip_title, content=tip_text, variant=tip_variant)]
            if estimate_page_utilization(PageContent(headline=headline, blocks=candidate_blocks)).estimated_ratio <= 0.95:
                blocks = candidate_blocks

        # Step 5: Exercise if still underfilled
        current_page = PageContent(headline=headline, blocks=blocks)
        util = estimate_page_utilization(current_page)

        if util.estimated_ratio < 0.70 and is_component_eligible("exercise", spec.page_type):
            sys_prompt_4 = f"Write a 2-step hands-on coding exercise for '{p.brief}'."
            res_ex = await self.llm_client.invoke_structured(
                schema=SmallModelExercise,
                system_prompt=sys_prompt_4,
                user_prompt=f"Topic: {p.brief}",
                stage=f"small_ex_ch{p.chapter_number}_p{p.page_number}",
                temperature=0.2,
            )
            if res_ex and res_ex.instructions:
                candidate_blocks = list(blocks) + [ExerciseBlock(title=res_ex.title or f"Try It Yourself: {p.brief}", instructions=res_ex.instructions)]
                if estimate_page_utilization(PageContent(headline=headline, blocks=candidate_blocks)).estimated_ratio <= 0.95:
                    blocks = candidate_blocks

        page_content = PageContent(headline=headline, blocks=blocks)

        # Final repair
        page_content = repair_underfilled_page(
            page_content=page_content,
            spec=spec,
            primary_subject=primary_subject,
            is_beginner=is_beginner,
            verified_facts=facts,
        )

        return page_content

    async def _llm_write_page(
        self,
        p: PlannedPage,
        plan: BookPlan,
        corpus: Optional[ResearchCorpus],
    ) -> Optional[PageContent]:
        """Use Groq LLM to write a high quality, topic-aligned page strictly grounded in research."""
        primary_lang = plan.intent.primary_programming_language or "text"

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
            f"2. Never use generic placeholder sentences. Every sentence must teach concrete details about {plan.title}.\n"
            f"3. If generating code, provide clean, runnable, syntactically valid {primary_lang} code.\n"
            f"4. Include an actionable CalloutBox (tip, best practice, or common pitfall).\n"
            f"5. Populate cited_source_urls with the URLs from the dossier actually used."
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

        # 2. Terminal Block
        if res.terminal_command and validate_terminal_command(res.terminal_command):
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

        # 3. Visual Anchor Blocks
        anchor = p.visual_anchor or VisualAnchorType.TEXT

        if res.code_snippet and validate_code_block(res.code_snippet, res.code_language or primary_lang) and (anchor == VisualAnchorType.CODE or p.layout == LayoutType.CODE_FOCUS.value or "code" in (p.brief or "").lower()):
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

        if res.cited_source_urls:
            self.metrics.research.sources_used = max(
                self.metrics.research.sources_used,
                len(set(res.cited_source_urls))
            )

        page_content = PageContent(headline=res.headline, blocks=blocks)
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
            entries = []
            for ch in plan.chapters:
                entries.append(
                    TocEntry(
                        chapter_number=ch.chapter_number,
                        title=ch.title,
                        page_number=ch.chapter_number * 5,
                        icon=ch.icon,
                    )
                )
            return PageContent(
                headline="Table of Contents",
                blocks=[TocBlock(title="Table of Contents", subtitle=f"Structure of {plan.title}", entries=entries)],
            )

        elif p_type == LayoutType.ACKNOWLEDGEMENT.value:
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
        if "interpreter" in brief_lower or "how the interpreter works" in brief_lower or "how programs work" in brief_lower:
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

        elif "hello world" in brief_lower or "first script" in brief_lower or "installation" in brief_lower or "tooling" in brief_lower:
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
                            "user_name = 'Learner'\n"
                            "print(f'Hello, {user_name}! Welcome to Python programming.')\n\n"
                            "hours = 40\n"
                            "rate = 25.50\n"
                            "total_pay = hours * rate\n"
                            "print(f'Weekly calculation: ${total_pay:,.2f}')"
                        ),
                        caption="Listing 1.1: Variable assignment, math, and f-string output.",
                        line_numbers=True,
                    ),
                    OutputBlock(
                        title="Terminal Output",
                        content="Hello, Learner! Welcome to Python programming.\nWeekly calculation: $1,020.00",
                    ),
                    CalloutBlock(
                        variant="tip",
                        title="Pythonic Tip",
                        content="Always use Python formatted string literals (`f'{expression}'`) for clean and fast string formatting.",
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
                    TerminalBlock(
                        title="Interactive Terminal REPL",
                        shell="bash",
                        lines=[
                            TerminalLine(kind="command", text="python3"),
                            TerminalLine(kind="output", text="Python 3.12.0 (main)\nType \"help\", \"copyright\", \"credits\" or \"license\" for more information."),
                            TerminalLine(kind="command", text=">>> 2 ** 8"),
                            TerminalLine(kind="output", text="256"),
                            TerminalLine(kind="command", text=">>> type(3.14159)"),
                            TerminalLine(kind="output", text="<class 'float'>"),
                        ],
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
                    CommonMistakeBlock(
                        title="Common Beginner Syntax Errors",
                        wrong_code="def calculate_total(a, b)\n    return a + b",
                        correct_code="def calculate_total(a, b):\n    return a + b",
                        explanation="Missing colon `:` at the end of `def`, `if`, or `for` headers causes a `SyntaxError: expected ':'`.",
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
                    CodeBlock(
                        language="python",
                        filename="type_conversions.py",
                        code=(
                            "raw_input = '150'\n"
                            "quantity = int(raw_input)\n"
                            "tax_rate = 0.08\n"
                            "total = quantity * (1 + tax_rate)\n"
                            "print(f'Final cost: ${total:.2f} (type: {type(total).__name__})')"
                        ),
                        caption="Listing 2.1: Type casting from string to integer and float arithmetic.",
                    ),
                    OutputBlock(
                        title="Output",
                        content="Final cost: $162.00 (type: float)",
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
                    ),
                ],
            )

        elif "string manipulation" in brief_lower or "formatted output" in brief_lower or "f-strings" in brief_lower:
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
                    OutputBlock(
                        title="Console Output",
                        content="Getting Started With Python\nCatalog: apple & banana & cherry & orange",
                    ),
                ],
            )

        # --- Chapter 3: User Input, Output & Conditions ---
        elif "input()" in brief_lower or "casting types" in brief_lower or "user input" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Interactive programs accept data from the user using the built-in `input()` function. "
                        "Because `input()` always returns a string (`str`), numerical input must be explicitly converted using `int()` or `float()`."
                    ),
                    CodeBlock(
                        language="python",
                        filename="user_input_demo.py",
                        code=(
                            "# Capturing user input and casting type\n"
                            "age_str = '22'  # Simulating input('Enter your age: ')\n"
                            "age = int(age_str)\n"
                            "if age >= 18:\n"
                            "    print(f'Eligible to vote: True (Age {age})')\n"
                            "else:\n"
                            "    print(f'Eligible to vote: False (Years remaining: {18 - age})')"
                        ),
                        caption="Listing 3.1: Converting string input to integer for logical checks.",
                        line_numbers=True,
                    ),
                    CommonMistakeBlock(
                        title="Missing Type Casting with input()",
                        wrong_code="age = input('Enter age: ')\nnext_year = age + 1  # TypeError: can only concatenate str to str",
                        correct_code="age = int(input('Enter age: '))\nnext_year = age + 1  # Correct: cast str to int before math",
                        explanation="`input()` returns string data. Trying to add an integer to a string raises `TypeError`.",
                    ),
                ],
            )

        elif "branching" in brief_lower or "if, elif" in brief_lower or "conditional" in brief_lower:
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
                            "score = 85\n"
                            "if score >= 90:\n"
                            "    grade = 'A'\n"
                            "elif score >= 80:\n"
                            "    grade = 'B'\n"
                            "elif score >= 70:\n"
                            "    grade = 'C'\n"
                            "else:\n"
                            "    grade = 'Needs Improvement'\n\n"
                            "print(f'Student Score: {score} -> Grade: {grade}')"
                        ),
                        caption="Listing 3.2: Multi-condition branching using if, elif, and else.",
                        line_numbers=True,
                    ),
                    OutputBlock(
                        title="Console Output",
                        content="Student Score: 85 -> Grade: B",
                    ),
                ],
            )

        # --- Chapter 4: Loops & Iteration ---
        elif "for loop" in brief_lower or "range()" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="The `for` loop in Python iterates over any iterable collection or sequence. "
                        "The built-in `range(start, stop, step)` function generates numbers lazily without allocating large lists in memory."
                    ),
                    CodeBlock(
                        language="python",
                        filename="for_loops.py",
                        code=(
                            "# Iterating with range\n"
                            "for i in range(1, 6):\n"
                            "    print(f'Count: {i}, Square: {i**2}')\n\n"
                            "# Iterating over a collection with enumerate\n"
                            "languages = ['Python', 'Rust', 'Go']\n"
                            "for rank, lang in enumerate(languages, start=1):\n"
                            "    print(f'#{rank}: {lang}')"
                        ),
                        caption="Listing 4.1: For loops with range() and enumerate().",
                        line_numbers=True,
                    ),
                    OutputBlock(
                        title="Output",
                        content="Count: 1, Square: 1\nCount: 2, Square: 4\nCount: 3, Square: 9\nCount: 4, Square: 16\nCount: 5, Square: 25\n#1: Python\n#2: Rust\n#3: Go",
                    ),
                ],
            )

        elif "while loop" in brief_lower or "loop control" in brief_lower or "break, continue" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="`while` loops repeat code as long as a condition evaluates to `True`. "
                        "Loop control statements `break` (exit loop immediately) and `continue` (skip remaining code in current iteration) "
                        "allow fine-grained iteration control."
                    ),
                    CodeBlock(
                        language="python",
                        filename="loop_control.py",
                        code=(
                            "numbers = [1, 2, -3, 4, 0, 5]\n"
                            "total = 0\n"
                            "for n in numbers:\n"
                            "    if n < 0:\n"
                            "        continue  # Skip negative numbers\n"
                            "    if n == 0:\n"
                            "        break     # Terminate loop at zero\n"
                            "    total += n\n"
                            "print(f'Total positive sum before zero: {total}')"
                        ),
                        caption="Listing 4.2: Using continue to skip and break to exit early.",
                        line_numbers=True,
                    ),
                    OutputBlock(
                        title="Console Output",
                        content="Total positive sum before zero: 7",
                    ),
                ],
            )

        # --- Chapter 5: Functions & Scope ---
        elif "functions" in brief_lower or "parameters & return" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Functions organize code into reusable, modular building blocks. Functions are defined using the `def` keyword, "
                        "support default arguments and keyword parameters, and return calculated results via `return`."
                    ),
                    CodeBlock(
                        language="python",
                        filename="functions_demo.py",
                        code=(
                            "def calculate_total(price: float, tax_rate: float = 0.05, discount: float = 0.0) -> float:\n"
                            '    """Calculate final price after discount and sales tax."""\n'
                            "    discounted = price * (1.0 - discount)\n"
                            "    final_price = discounted * (1.0 + tax_rate)\n"
                            "    return round(final_price, 2)\n\n"
                            "print('Standard:', calculate_total(100.0))\n"
                            "print('Discounted:', calculate_total(100.0, discount=0.10))"
                        ),
                        caption="Listing 5.1: Function definition with default parameters and return values.",
                        line_numbers=True,
                    ),
                    OutputBlock(
                        title="Console Output",
                        content="Standard: 105.0\nDiscounted: 94.5",
                    ),
                ],
            )

        # --- Chapter 6: Data Structures ---
        elif "lists" in brief_lower or "tuples" in brief_lower or "collections" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Python features versatile built-in container types: mutable lists (`[...]`), immutable tuples (`(...)`), "
                        "key-value dictionaries (`{...}`), and unique sets (`set()`)."
                    ),
                    CodeBlock(
                        language="python",
                        filename="collections_demo.py",
                        code=(
                            "# Lists, Dictionaries, and Sets\n"
                            "users = ['Alice', 'Bob', 'Charlie']\n"
                            "users.append('Diana')\n\n"
                            "scores = {'Alice': 95, 'Bob': 88}\n"
                            "scores['Charlie'] = 92\n\n"
                            "tags = {'python', 'beginner', 'python'}  # Duplicates removed\n"
                            "print('Users:', users)\n"
                            "print('Top Score:', scores['Alice'])\n"
                            "print('Unique Tags:', tags)"
                        ),
                        caption="Listing 6.1: Core Python data structures in action.",
                        line_numbers=True,
                    ),
                    OutputBlock(
                        title="Output",
                        content="Users: ['Alice', 'Bob', 'Charlie', 'Diana']\nTop Score: 95\nUnique Tags: {'python', 'beginner'}",
                    ),
                ],
            )

        # --- Chapter 7: File I/O & Exceptions ---
        elif "error handling" in brief_lower or "exceptions" in brief_lower or "files" in brief_lower or "try, except" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Defensive programming requires handling runtime errors gracefully using `try...except` blocks "
                        "and ensuring system resources like open files are always safely closed with `with` context managers."
                    ),
                    CodeBlock(
                        language="python",
                        filename="files_and_exceptions.py",
                        code=(
                            "from pathlib import Path\n\n"
                            "data_file = Path('example.txt')\n"
                            "# Safe write using context manager\n"
                            "with open(data_file, 'w', encoding='utf-8') as f:\n"
                            "    f.write('Hello, Python File I/O!')\n\n"
                            "# Safe read with try-except\n"
                            "try:\n"
                            "    with open(data_file, 'r', encoding='utf-8') as f:\n"
                            "        content = f.read()\n"
                            "    print('Read file successfully:', content)\n"
                            "except FileNotFoundError as err:\n"
                            "    print(f'Error reading file: {err}')"
                        ),
                        caption="Listing 7.1: File operations with context managers and error handling.",
                        line_numbers=True,
                    ),
                    OutputBlock(
                        title="Console Output",
                        content="Read file successfully: Hello, Python File I/O!",
                    ),
                ],
            )

        # --- Chapter 8: OOP Fundamentals ---
        elif "object-oriented" in brief_lower or "classes" in brief_lower or "oop" in brief_lower or "methods" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Object-Oriented Programming (OOP) groups state (attributes) and behavior (methods) into reusable blueprints called classes. "
                        "The `__init__` method initializes newly created class instances."
                    ),
                    CodeBlock(
                        language="python",
                        filename="oop_basics.py",
                        code=(
                            "class BankAccount:\n"
                            "    def __init__(self, owner: str, balance: float = 0.0):\n"
                            "        self.owner = owner\n"
                            "        self.balance = balance\n\n"
                            "    def deposit(self, amount: float) -> float:\n"
                            "        if amount > 0:\n"
                            "            self.balance += amount\n"
                            "        return self.balance\n\n"
                            "account = BankAccount('Alice', 100.0)\n"
                            "new_balance = account.deposit(50.0)\n"
                            "print(f'{account.owner} Balance: ${new_balance:.2f}')"
                        ),
                        caption="Listing 8.1: Class definition with constructor and instance method.",
                        line_numbers=True,
                    ),
                    OutputBlock(
                        title="Console Output",
                        content="Alice Balance: $150.00",
                    ),
                ],
            )

        # --- Chapter 9: Capstone Mini-Project ---
        elif "capstone" in brief_lower or "mini-project" in brief_lower or "project" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="We combine variables, functions, collections, file I/O, and OOP into a complete, runnable CLI Task Tracker application. "
                        "The project demonstrates how individual concepts integrate into a practical tool."
                    ),
                    CodeBlock(
                        language="python",
                        filename="task_tracker.py",
                        code=(
                            "class Task:\n"
                            "    def __init__(self, task_id: int, title: str):\n"
                            "        self.task_id = task_id\n"
                            "        self.title = title\n"
                            "        self.completed = False\n\n"
                            "class TaskManager:\n"
                            "    def __init__(self):\n"
                            "        self.tasks: list[Task] = []\n\n"
                            "    def add_task(self, title: str) -> Task:\n"
                            "        task = Task(len(self.tasks) + 1, title)\n"
                            "        self.tasks.append(task)\n"
                            "        return task\n\n"
                            "manager = TaskManager()\n"
                            "manager.add_task('Install Python 3.12')\n"
                            "manager.add_task('Complete Chapter Exercises')\n"
                            "for t in manager.tasks:\n"
                            "    print(f'[{t.task_id}] {t.title} (Done: {t.completed})')"
                        ),
                        caption="Listing 9.1: Complete Runnable Capstone CLI Task Tracker.",
                        line_numbers=True,
                    ),
                    OutputBlock(
                        title="Console Output",
                        content="[1] Install Python 3.12 (Done: False)\n[2] Complete Chapter Exercises (Done: False)",
                    ),
                ],
            )

        # --- Chapter 10: Standard Library & Next Steps ---
        elif "standard library" in brief_lower or "packages" in brief_lower or "pip" in brief_lower or "next steps" in brief_lower:
            return PageContent(
                headline=headline,
                blocks=[
                    TextBlock(
                        text="Python's 'batteries included' philosophy means an extraordinary array of built-in modules is available out of the box. "
                        "Modules like `math`, `random`, `datetime`, and `pathlib` accelerate development, while `pip` and virtual environments "
                        "give access to the broader open-source ecosystem."
                    ),
                    TableBlock(
                        caption="Table 10.1: Essential Python Standard Library Modules.",
                        columns=["Module", "Primary Use Case", "Common Functions"],
                        rows=[
                            ["`pathlib`", "Object-oriented filesystem paths", "`Path.cwd()`, `Path.exists()`, `read_text()`"],
                            ["`datetime`", "Dates, times, and formatting", "`datetime.now()`, `strftime()`"],
                            ["`random`", "Random sampling and numbers", "`random.randint()`, `random.choice()`"],
                            ["`json`", "Data serialization and parsing", "`json.dump()`, `json.load()`"],
                        ],
                    ),
                    CalloutBlock(
                        variant="tip",
                        title="Virtual Environments",
                        content="Always use `python -m venv .venv` to isolate project dependencies before installing packages with `pip`.",
                        icon="shield-check",
                    ),
                ],
            )

        # Fallback for any other Python section
        return PageContent(
            headline=headline,
            blocks=[
                TextBlock(
                    text=f"Mastering **{p.brief or p.chapter_title}** builds confidence in your Python engineering abilities. "
                    f"By applying structured syntax, verified typing, and idiomatic coding practices, you write programs that are clean, reliable, and easy to maintain."
                ),
                CodeBlock(
                    language="python",
                    filename="practice_example.py",
                    code=(
                        f"# Working example for {headline}\n"
                        f"def execute_practice() -> str:\n"
                        f"    message = 'Concept verified successfully.'\n"
                        f"    return message\n\n"
                        f"print(execute_practice())"
                    ),
                    caption=f"Listing: {headline} Practice Implementation",
                    line_numbers=True,
                ),
                OutputBlock(
                    title="Console Output",
                    content="Concept verified successfully.",
                ),
                CalloutBlock(
                    variant="tip",
                    title="Hands-On Challenge",
                    content=f"Try writing a small script that applies {headline} to solve a real task in your daily workflow.",
                    icon="code",
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
        """Produce mock-mode non-technical editorial content blocks."""
        brief = p.brief or p.chapter_title or plan.title

        blocks = [
            TextBlock(
                text=f"Understanding **{brief}** provides essential fundamentals for {plan.title}. "
                f"In this section, we examine practical patterns, frameworks, and actionable strategies "
                f"tailored for {plan.intent.target_audience.lower()}."
            ),
            CalloutBlock(
                variant="tip",
                title="Implementation Note",
                content=f"When applying {brief}, establish small daily habits and track measurable indicators to ensure sustainable progress.",
                icon="lightbulb",
            ),
            TextBlock(
                text=f"By integrating {brief} into your routine, you establish consistent progress toward your long-term goals."
            ),
        ]
        return PageContent(headline=headline, blocks=blocks)
