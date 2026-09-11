# VasukiSquare Architecture

## High-Level Pipeline

VasukiSquare decomposes the generation of professional technical ebooks into explicit, verifiable reasoning and rendering stages:

```
User Prompt
    │
    ▼
[Intent Analysis]
    │
    ▼
[Research & Fact Verification] (Web / Wikipedia / Academic)
    │
    ▼
[Editorial Planning] (Title, target audience, tone, chapter outlines)
    │
    ▼
[Chapter Planning] (Structured sections, page allocations)
    │
    ▼
[Page Planning] (Layout assignments, hierarchy, visual anchors)
    │
    ▼
[Page Content Generation] (Writing, code samples, citations)
    │
    ▼
[HTML/CSS Rendering] (A4 canvas, typography, Lucide SVG tokens)
    │
    ▼
[Validation] (Layout boundaries, citation verification, page links)
    │
    ▼
[MongoDB Persistence] (Books, independent Page documents, Covers)
    │
    ▼
[PDF Rendering] (Playwright Chromium A4 output)
```

## Domain Structure

- **`vasukisquare.agents`**: Orchestrates reasoning stages with LangChain/LangGraph and Groq.
- **`vasukisquare.research`**: Manages source tracking, deduplication, citation parsing, and fact validation.
- **`vasukisquare.book`**: Encapsulates data models for Books, Pages, Covers, and Plans.
- **`vasukisquare.design`**: Implements the design tokens (`DESIGN.md`), Lucide SVG handling, and chapter dark/light theme alternation.
- **`vasukisquare.database`**: Handles PyMongo connection management and typed repositories (`BookRepository`, `PageRepository`, `CoverRepository`).
- **`vasukisquare.renderer`**: Jinja2 HTML page generation and Playwright A4 PDF export.
- **`vasukisquare.templates`**: Canonical HTML structures and CSS stylesheets adhering to the design tokens.
- **`vasukisquare.tools`**: Abstract and concrete tool wrappers for search providers and scraper utilities.

## Core Invariants

1. **Deterministic Page Model**: Every generated page exists as an independent document in MongoDB containing `book_id`, `page_number`, `previous_page_id`, and `next_page_id`.
2. **Book Root Linking**: The `Book` entity contains `starting_page_id` which points to the first rendered page.
3. **Design System Adherence**: Colors and typography strictly mirror `DESIGN.md`. Lucide icons only use design token colors.
4. **Theme Alternation**: Odd chapters (1, 3, 5, ...) are rendered in the dark theme; even chapters (2, 4, 6, ...) are rendered in the light theme.
5. **A4 Physical Constraints**: Physical page dimensions are fixed at 210mm × 297mm.

