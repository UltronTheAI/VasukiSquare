# Generation Pipeline

VasukiSquare executes an explicit 7-stage generation lifecycle coordinated by `EbookGenerationPipeline` in `src/vasukisquare/pipeline/orchestrator.py`.

The stages are executed sequentially with intermediate state caching, allowing any interrupted run to be resumed using `--resume`.

---

## Stage-by-Stage Breakdown

```
Stage 1: Intent Inference
    │
    ▼
Stage 2: Deep Research & Retrieval
    │
    ▼
Stage 3: Editorial & Chapter Planning
    │
    ▼
Stage 4: Cover Planning & Design
    │
    ▼
Stage 5: Page Authoring & Overflow Repair
    │
    ▼
Stage 6: HTML Assembly, Preflight Audit & PDF Export
    │
    ▼
Stage 7: Canonical Database Persistence (Optional MongoDB)
```

---

### Stage 1: Intent Inference (`EditorialPlannerAgent.infer_intent`)
- **Input**: User topic, optional public title, optional editorial prompt/brief, target page count.
- **Processing**:
  - Classifies whether the subject is technical or non-technical (`is_technical`).
  - Identifies target audience (e.g. beginner, intermediate, systems engineer).
  - Determines tone (e.g. practical, academic, concise).
  - Extracts required topics, desired elements (exercises, checklists, code), and programming language.
  - Enforces title length constraint (≤ 50 characters).
- **Output**: `BookIntent` model.
- **Artifact**: `checkpoints/intent.json`.
- **Failure Handling**: Falls back to deterministic intent extraction rules if LLM parsing encounters errors.

---

### Stage 2: Deep Research (`ResearchService.research_topic`)
- **Input**: Topic and `BookIntent`.
- **Processing**:
  - `ResearchPlanner` expands topic into multi-perspective search queries (conceptual, architectural, pitfalls, standards).
  - Dispatches queries across configured search providers (SearXNG, DuckDuckGo, Tavily, Serper, Brave) and Wikipedia API.
  - Normalizes URLs, deduplicates sources, and ranks documents by domain authority.
  - Ingests and extracts clean markdown/text content from high-ranking pages.
- **Output**: `ResearchCorpus` model containing ranked `SourceDocument` records.
- **Artifacts**: `research.json`, `research_queries.json`, `checkpoints/research.json`.
- **Failure Handling**: If live web search is unavailable or times out, seamlessly falls back to DuckDuckGo, Wikipedia, or built-in offline technical corpora.

---

### Stage 3: Editorial Planning (`EditorialPlannerAgent.generate_book_plan`)
- **Input**: Topic, `BookIntent`, and `ResearchCorpus`.
- **Processing**:
  - Outlines 4–12 chapters mapped across the target page budget.
  - Assigns visual anchor types (code blocks, comparison tables, diagrams, callouts, lists) to every section.
  - Creates exact page-by-page specifications (`PlannedPageSpec`) for frontmatter, chapters, and backmatter.
  - Generates cohesive `BookThemeMap` with alternating dark/light chapter themes and harmonious color accents.
- **Output**: `BookPlan` model.
- **Artifacts**: `book_plan.json`, `checkpoints/book_plan.json`.
- **Failure Handling**: Structured retry loops with exponential backoff on model failure.

---

### Stage 4: Cover Planning & Design (`CoverPlannerAgent.plan_cover`)
- **Input**: Book title, subtitle, category, audience, tone, and theme seed.
- **Processing**:
  - Selects 1 of 6 cover styles (`editorial_minimal`, `split_hero`, `geometric_accent`, `technical_blueprint`, `swiss_bold`, `minimal_monochrome`).
  - Computes high-contrast color palettes meeting WCAG contrast thresholds.
  - Renders 1600 × 2560 source canvas artwork and physical A4 cover layout.
- **Output**: `CoverPlan` model and rendered A4 cover `Page`.
- **Artifacts**: `cover_plan.json`, `cover.html`, `checkpoints/cover_plan.json`.
- **Failure Handling**: Contrast repair engine automatically adjusts text/background luminance if contrast ratio falls below 4.5:1.

---

### Stage 5: Page Authoring & Repair (`PageWriterAgent.write_page`)
- **Input**: `PlannedPageSpec`, `BookPlan`, and `ResearchCorpus`.
- **Processing**:
  - Authors structured component blocks (`HeroHeaderBlock`, `ParagraphBlock`, `CodeBlock`, `CalloutBlock`, `ComparisonBlock`, etc.) with zero raw markdown leakage.
  - Enforces universal language alias normalization (`c++` -> `cpp`, `rs` -> `rust`, `js` -> `javascript`, `ts` -> `typescript`, `py` -> `python`, etc.).
  - Runs language-aware syntax completeness validation (`validate_code_completeness`) checking delimiter balance (`()`, `{}`, `[]`), quote/string closure, Rust lifetime handling, and language AST/statement rules.
  - Automatically triggers targeted LLM repair (`repair_incomplete_code`) if a generated code block is cut mid-statement or incomplete.
  - Formats 1 of 6 chapter opener templates on chapter boundary pages.
  - Runs `PageRepairEngine`, `split_code_block`, and `OverflowDetector` to calculate content density and perform lossless line-boundary code splitting with continuation captions (`Listing X.Y: ... (Cont.)`).
  - Pass 2 resolves dynamic Table of Contents starting page numbers and cited bibliography blocks.
  - Executes 16-point Content Quality Audit (`ContentValidator.audit_book`).
- **Output**: List of typed, validated `Page` models.
- **Artifacts**: `pages/page_*.html`, `checkpoints/pages/page_*.json`.
- **Failure Handling**: Individual page retry on schema validation error; checkpointing preserves all completed pages.

---

### Stage 6: HTML Assembly, Preflight Audit & PDF Export (`HtmlPageRenderer` & `PdfRenderer`)
- **Input**: Repaired, re-linked, and validated `Page` list, `BookPlan`, and `AppConfig`.
- **Processing**:
  - Runs `preflight_book` to check geometry and visual token integrity.
  - Combines individual page DOMs into canonical `book.html`.
  - Launches Playwright headless Chromium, waits for web fonts and assets to settle, and prints physical A4 `book.pdf`.
  - Writes canonical `book_manifest.json`, `preflight_report.json`, and `generation_metrics.json`.
- **Output**: `book.html`, `book.pdf`, `book_manifest.json`, `preflight_report.json`, `generation_metrics.json`.
- **Failure Handling**: Clear diagnostics if Playwright browser binaries are missing (`playwright install chromium`).

---

### Stage 7: Canonical Database Persistence (`DatabaseManager` & Repositories)
- **Input**: Final preflight-validated `Book`, final repaired `Page` list, and `Cover`.
- **Processing**:
  - Persists `Book` root document in `books` collection (resolving deterministic slug collision and SEO canonicals).
  - Persists the final repaired, renumbered, and re-linked physical pages into `pages` collection.
  - Links `starting_page_id` and persists cover artwork in `covers` collection.
  - Transitions publication lifecycle status from `"draft"` to `"published"` (`published_at = datetime.now()`).
- **Output**: Navigable, complete MongoDB document graph ready for external Next.js consumption.
- **Failure Handling**: **Non-blocking**. If MongoDB is not running or `--no-db` is specified, the pipeline logs an informational notice and completes PDF export without interruption.
