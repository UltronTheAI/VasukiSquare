# VasukiSquare Testing Contract

## Required Test Categories

### Unit
Test:
- schemas
- design token parsing
- page linking
- chapter theme selection
- page numbering
- layout selection
- source normalization
- citation parsing
- MongoDB serialization

### Integration
Test:
- Groq structured generation
- research tools
- Wikipedia retrieval
- web retrieval
- MongoDB persistence
- HTML generation
- PDF generation

### Rendering
Every render test must verify:

- page size is A4
- page count is correct
- no element crosses page boundaries
- no text is clipped
- page number exists
- chapter name exists where required
- chapter opener contains no body text
- dark/light chapter alternation works
- Lucide SVG loads successfully

### MongoDB
Verify:

book.starting_page_id → correct first page

page.book_id → correct book

page.previous_page_id → previous page

page.next_page_id → next page

cover.book_id → correct book

### Regression
Maintain snapshot fixtures for:

- cover
- copyright page
- TOC
- dark chapter opener
- light chapter opener
- text-heavy page
- code page
- comparison page
- references page
- thank-you page

## Required Commands

pytest tests/unit -q

pytest tests/integration -q

pytest tests/rendering -q

pytest -q

## Completion Rule

A task affecting rendering is incomplete unless rendering tests pass.

A task affecting MongoDB is incomplete unless relationship tests pass.

A task affecting research is incomplete unless citation/source tests pass.