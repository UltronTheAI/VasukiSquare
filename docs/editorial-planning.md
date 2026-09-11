# VasukiSquare Editorial Book Planning

The Editorial Planning Agent translates a user's prompt and research corpus into a complete, budget-balanced `BookPlan` before any chapter prose is written.

---

## 1. Intent Inference (`BookIntent`)

The planner analyzes the prompt and research corpus to infer 9 key editorial parameters:

- **`book_type`**: Architectural guide, handbook, technical deep dive, tutorial manual, or executive briefing.
- **`target_audience`**: Technical background and persona.
- **`technical_depth`**: Introductory, intermediate, advanced, or expert.
- **`tone`**: Authoritative, practical, analytical, or educational.
- **`approximate_length`**: Target page range (`short`, `standard`, `comprehensive`).
- **`chapter_count`**: Number of structured chapters (typically 4–10).
- **`research_intensity`**: `standard`, `deep`, or `academic`.
- **`code_requirements`**: Whether code snippets and implementation guides are required.
- **`diagram_requirements`**: Whether system architecture diagrams and topologies are required.

---

## 2. Canonical Book Structure

Every generated book plan guarantees a complete book sequence:

```
[Frontmatter]
  ├── Page 1: Cover (Dark theme, 1600x2560 canvas mapping)
  ├── Page 2: Title / Half-Title Imprint
  ├── Page 3: Copyright & Publishing Notice
  └── Page 4: Table of Contents (TOC)

[Body: Chapters 1 .. N]
  ├── Chapter Opener (Dark for odd chapters, Light for even chapters)
  │     ├── EXACTLY 1 Lucide Icon
  │     ├── Chapter Number
  │     └── Chapter Title
  │     (No body text or overview paragraphs)
  └── Chapter Content Pages (Count = Chapter Budget - 1)
        ├── Code Snippets
        ├── Architectural Diagrams & Tables
        ├── Comparative Matrices
        └── Technical Narratives

[Backmatter]
  ├── References & Primary Source Citations
  └── Thank-You / Acknowledgments Page
```

---

## 3. Visual Layout Anchors

The planner annotates sections and pages with explicit visual anchors to guarantee visual diversity while remaining within `DESIGN.md` tokens:

- **`code`**: Formatted syntax-highlighted code listings (`layout: "code"`).
- **`table`**: Structured data tables, parameter grids, and API summaries.
- **`diagram`**: System topology, sequence flows, and component diagrams.
- **`timeline`**: Historical evolution and release milestones.
- **`quote`**: Authoritative industry or academic callout quotations.
- **`comparison`**: Side-by-side trade-off matrices (`layout: "comparison"`).
- **`statistic`**: Big-number KPI cards and quantitative benchmark highlights.
- **`text`**: Structured technical prose and concept explanations.

---

## 4. Core Invariants

1. **Deterministic Page Budgeting**: Every chapter has a fixed page budget (e.g. 6–10 pages). The chapter opener consumes 1 page of this budget.
2. **Theme Alternation**: Odd chapters (1, 3, 5, ...) are assigned `Theme.DARK`. Even chapters (2, 4, 6, ...) are assigned `Theme.LIGHT`.
3. **Sequential Pre-allocation**: Every page in `all_planned_pages` is assigned a unique, contiguous 1-indexed `page_number`.
4. **No Premature Generation**: The editorial planner defines structure, budgets, and visual anchors without generating final chapter prose.

