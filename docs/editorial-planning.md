# Editorial Planning & Page Budgeting

The `EditorialPlannerAgent` (`src/vasukisquare/agents/editorial.py`) translates user topics into cohesive, mathematically budgeted publication structures.

---

## 1. Intent Analysis & Classification

Before outlining chapters, the engine infers a `BookIntent`:

```python
class BookIntent(BaseModel):
    topic: str
    title: str
    subtitle: Optional[str]
    book_type: str                  # "practical_guide", "reference_manual", "deep_dive", etc.
    is_technical: bool              # Technical vs non-technical subject classification
    primary_programming_language: Optional[str]
    target_audience: str            # "Beginner", "Intermediate", "Systems Architects"
    tone: str                       # "practical", "rigorous", "conversational"
    technical_depth: str            # "introductory", "in_depth", "advanced"
    required_topics: List[str]
    desired_elements: List[str]     # ["code", "checklists", "exercises", "diagrams"]
    code_requirements: bool
    target_pages: int
```

### Technical vs. Non-Technical Detection
- **Technical Subjects** (`is_technical=True`): Triggers syntax-highlighted code blocks, terminal execution sessions, language-specific best practices, and code visual anchors.
- **Non-Technical Subjects** (`is_technical=False`): Suppresses code blocks completely, replacing them with takeaway cards, step-by-step checklists, reflection prompts, and concept comparison tables.

---

## 2. Title Constraints & Sanitation

VasukiSquare strictly validates titles (`validate_book_title` in `src/vasukisquare/book/models.py`):
- **Length Constraint**: Maximum 50 characters.
- **No LLM Preamble**: Rejects commentary such as `"Here is the title of the book"`, `"Book Title: ..."`.
- **Single-Line**: Rejects multiline titles.
- If an explicit `--title` exceeds 50 characters, `clean_and_resolve_title` intelligently trims and applies an ellipsis to guarantee visual balance on cover artwork and running headers.

---

## 3. Page Budgeting Architecture

Physical books require predictable physical page budgets. The engine distributes pages across three primary zones:

```
Total Page Budget (e.g. 40 Pages)
├── 1. Frontmatter (Pages 1 to 4)
│   ├── Page 1: Cover Artwork
│   ├── Page 2: Imprint, Copyright & Metadata
│   ├── Page 3: Preface / Executive Summary
│   └── Page 4: Dynamic Table of Contents
│
├── 2. Core Chapters (Pages 5 to 38)
│   ├── Chapter 1: 8 Pages (Opener + 7 Section Pages)
│   ├── Chapter 2: 9 Pages (Opener + 8 Section Pages)
│   ├── Chapter 3: 9 Pages (Opener + 8 Section Pages)
│   └── Chapter 4: 8 Pages (Opener + 7 Section Pages)
│
└── 3. Backmatter (Pages 39 to 40)
    ├── Page 39: References & Cited Bibliography
    └── Page 40: Acknowledgments & Next Steps
```

### Exact vs. Target Page Count
The `--pages` argument specifies the **target budget**. While the editorial planner designs the chapter structure around this target, dynamic page-splitting and zero-overflow repairs may adjust the actual page count by ±1–2 pages to guarantee that no content overflows physical A4 boundaries.

---

## 4. Visual Anchor Selection

Every planned section is assigned a primary `VisualAnchorType`:
- `VisualAnchorType.CODE`: Code snippet with filename badge and language styling.
- `VisualAnchorType.CALLOUT`: Tip, warning, or best-practice callout box.
- `VisualAnchorType.TABLE`: Side-by-side comparison matrix.
- `VisualAnchorType.LIST`: Structured key points or checklists.
- `VisualAnchorType.HERO`: Section headline with Lucide topic icon.
- `VisualAnchorType.TERMINAL`: Command-line interface block.
