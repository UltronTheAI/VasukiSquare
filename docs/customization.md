# Customization & Developer Guide

VasukiSquare is architected with modular, decoupled subsystems designed for developer extension. This guide explains where to customize prompts, design tokens, page layout components, visual themes, cover art generation, and database schemas.

---

## 1. Directory & Subsystem Map

| Subsystem | Source Path | Description |
|---|---|---|
| **Agents & Prompts** | `src/vasukisquare/agents/` | Editorial planning, page writing, cover art planning, and content validation prompts. |
| **Book Models & Schemas** | `src/vasukisquare/book/` | Pydantic schemas for `Book`, `Page`, `BookPlan`, `BookIntent`, and component blocks. |
| **Design System & Tokens** | `src/vasukisquare/design/` | Mathematical color tokens, themes, Lucide icons, and visual layout constraints. |
| **Cover Art Engine** | `src/vasukisquare/cover/` | Procedural geometric cover patterns, contrast calculations, and cover styles. |
| **Renderer & Preflight** | `src/vasukisquare/renderer/` | HTML/CSS templates, Playwright PDF rendering, overflow repair, and preflight audit. |
| **Research Pipeline** | `src/vasukisquare/research/` | Multi-perspective query planning, ranking, deduplication, and URL normalization. |
| **Search Tools** | `src/vasukisquare/tools/` | Search backends (SearXNG, DuckDuckGo, Tavily, Serper, Brave, Wikipedia). |
| **Templates & CSS** | `src/vasukisquare/templates/` | Jinja2 templates (`base.html`, `book.html`, `cover.html`, `styles.css`). |
| **Database Repositories** | `src/vasukisquare/database/` | PyMongo connection management and collections (`books`, `pages`, `covers`). |

---

## 2. Customizing Agent Prompts

All system prompts and structured output schemas reside in `src/vasukisquare/agents/`:

### Editorial Planner Agent (`agents/editorial.py`)
- `infer_intent(topic, prompt, title, target_pages)`: Informs target audience, technical classification (`is_technical`), programming language detection, and required sections.
- `generate_book_plan(topic, intent, corpus, target_pages)`: Generates chapter breakdown, section visual anchors, and page count budgets.

### Page Writer Agent (`agents/writer.py`)
- `write_page(page_spec, book_plan, research_corpus)`: Generates page content, rich text spans, code examples, callout cards, comparison tables, and terminal blocks.

### Cover Planner Agent (`agents/cover.py` & `cover/planner.py`)
- `plan_cover(title, subtitle, category, tone, audience, ...)`: Chooses cover geometry, color accents, and headline layout.

---

## 3. Customizing Visual Tokens & Themes

### Design Tokens (`design/tokens.py`)
Color tokens are validated against strict contracts to ensure optimal contrast:
- Core dark backgrounds: `#001e2b`, `#00141e`
- Core light backgrounds: `#faf8f5`, `#f6f4ee`
- Text tokens: `#ffffff`, `#e8f1f5`, `#111827`, `#374151`
- Accent tokens: `#00ed64`, `#00684a`, `#0062d2`, `#e3441a`, `#9444d0`

### Chapter Themes (`design/theme.py` & `design/themes.py`)
- **Alternating Chapters Contract**: Odd chapters render in dark theme mode; even chapters render in light theme mode.
- Modify `generate_book_theme()` in `src/vasukisquare/design/themes.py` to customize palette rotation rules.

---

## 4. Customizing Page Layout Components

Structured component definitions reside in `src/vasukisquare/book/components.py` and are rendered by `src/vasukisquare/renderer/components.py`:

- `HeroHeaderBlock`: Prominent chapter section header with Lucide icon.
- `ParagraphBlock`: Body text supporting bold, inline code, links, and italic spans.
- `CodeSnippetBlock`: Syntax-highlighted code block with language badge and file path.
- `TerminalBlock`: Command-line execution block.
- `CalloutBlock`: Distinctive tip, warning, caution, or info card.
- `KeyPointsBlock`: Bulleted takeaways and checklist items.
- `ComparisonTableBlock`: Side-by-side architectural or concept comparisons.
- `TocBlock`: Dynamic Table of Contents with page numbering.
- `SourceBlock`: Formatted reference citations.

To introduce a new component:
1. Define the Pydantic schema in `src/vasukisquare/book/components.py`.
2. Add its HTML rendering method in `src/vasukisquare/renderer/components.py`.
3. Add component styles to `src/vasukisquare/templates/styles.css`.

---

## 5. Customizing Cover Layouts & Geometric Patterns

Cover layout styles reside in `src/vasukisquare/cover/styles.py` and patterns in `src/vasukisquare/design/cover_patterns.py`:

Available cover styles:
- `editorial_minimal`: Centered title typography, clean metadata footer, subtle border frame.
- `split_hero`: Two-tone contrasting background split with hero icon and badge.
- `geometric_accent`: Procedural math-driven geometric SVG grid patterns.
- `technical_blueprint`: Circuit / grid overlay with monospace tech metadata.
- `swiss_bold`: Heavy asymmetric Swiss typography with stark accent bar.
- `minimal_monochrome`: Ultra-clean high-contrast typography.

---

## 6. Customizing CSS & Jinja2 Templates

Core layout templates reside in `src/vasukisquare/templates/`:
- `styles.css`: Canonical physical A4 styling, responsive resets, font rules, component styles.
- `book.html`: Assembled book wrapper combining all individual page DOM trees.
- `cover.html`: Standalone high-res cover SVG/HTML canvas.
- `base.html`: Base page frame including running header, footer, page numbering, and margin boxes.

