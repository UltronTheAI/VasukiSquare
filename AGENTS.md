# VasukiSquare Agent Instructions

## Mission

VasukiSquare is an AI-powered research, editorial, HTML layout,
and PDF generation engine written in Python.

It generates professionally designed ebooks from a user topic or description.

## Core Architecture

Generation pipeline:

Prompt
→ Intent
→ Research
→ Editorial Plan
→ Chapter Plan
→ Page Plan
→ Page Content
→ HTML Rendering
→ Validation
→ MongoDB Persistence
→ PDF Rendering

Do not collapse these stages into one LLM request.

## Critical Rules

- Python only.
- LangChain/LangGraph orchestrates reasoning workflows.
- Groq is the primary LLM provider.
- HTML/CSS is the canonical rendered document format.
- Markdown must never be used as the final book representation.
- MongoDB stores books, pages, and covers.
- Every generated page must exist independently in MongoDB.
- Every page contains book_id.
- Every page contains previous_page_id and next_page_id where applicable.
- Every book contains starting_page_id.
- Every cover contains book_id.
- DESIGN.md is the visual source of truth.
- Do not invent design tokens outside DESIGN.md unless absolutely required.
- Lucide is the only default icon library.
- Icons use design token colors, not arbitrary colors.

## PDF Rules

- Physical page size: A4 (210mm × 297mm).
- Every normal page must fit exactly inside A4.
- No visible overflow is allowed.
- Each content page contains its page number.
- Chapter content pages contain chapter identification.
- Chapter opener pages contain only:
  - chapter number
  - chapter title
  - one Lucide icon
- Odd chapters use dark theme.
- Even chapters use light theme.
- Cover source artwork is 1600 × 2560.
- Cover artwork must be safely cropped/placed into A4 output.

## Design Rules

Follow DESIGN.md.

Page layouts may vary significantly but must remain within
the same design language.

Variation must come from composition, hierarchy and layout,
not random colors or unsupported fonts.

## Research Rules

- Research factual subjects before writing.
- Track every source.
- Prefer primary and authoritative sources.
- Wikipedia may be used for orientation but should not be the
  only source for important claims.
- Time-sensitive claims require current sources.
- Never fabricate citations.
- Deduplicate sources.

## Coding Rules

- Keep modules small.
- Use typed Python.
- Use Pydantic schemas for all LLM structured outputs.
- Keep business logic outside prompt strings.
- No giant all-in-one agent.
- No global mutable state.
- No hidden fallback that silently drops citations.
- External integrations must be behind interfaces.

## Testing

Read TESTS.md before modifying production code.

Relevant tests must pass before task completion.

## Documentation

Any meaningful behavior change must update the relevant file in docs/.