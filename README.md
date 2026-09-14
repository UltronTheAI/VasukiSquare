# VasukiSquare

VasukiSquare is an AI-powered research, editorial planning, HTML layout, and PDF generation engine written in Python.

It generates professionally designed technical ebooks from a user prompt or topic description, enforcing strict visual design guidelines, verified source attribution, MongoDB linked-list persistence, and deterministic physical A4 PDF rendering.

---

## Core Generation Pipeline

VasukiSquare decomposes book creation into distinct, verifiable reasoning and rendering stages:

```
User Prompt
  ├── 1. Intent Analysis (Category, Audience, Tone, Depth, Budgets)
  ├── 2. Multi-Perspective Deep Research (Search, Wiki, Docs, Feeds with Deduplication)
  ├── 3. Editorial & Structural Planning (Frontmatter, Chapters, Backmatter)
  ├── 4. Cover Planning & Artwork Design (1600x2560 Source Artwork + A4 Safe Crop)
  ├── 5. Page Writing & Layout Assembly (14 Editorial Layouts + Controlled Overflow Repair)
  ├── 6. MongoDB Persistence (3-Collection Linked Graph: Books, Pages, Covers)
  └── 7. Canonical HTML & A4 PDF Compilation (Chromium Rendering, Zero Margins)
```

---

## Key Principles & Architecture

- **Strictly Typed Python**: Structured Pydantic v2 schemas across all domain models, planner outputs, and database documents.
- **Visual Source of Truth**: Layouts, typography, and color tokens strictly conform to [`DESIGN.md`](DESIGN.md).
- **Three-Collection MongoDB Model**: Persistent storage across `books`, `pages`, and `covers` with bi-directionally linked page graphs.
- **Physical A4 Standard**: Every page renders to exact physical A4 dimensions (`210mm × 297mm`, `@page { size: A4; margin: 0; }`).
- **Targeted Repair & Retry**: If a page overflows or fails validation, only that page is split or adjusted without re-running expensive web research or regenerating the entire book.
- **Dynamic Theming**: Odd chapters use dark theme; even chapters use light theme.
- **Minimal Chapter Openers**: Opener pages feature only the chapter number, chapter title, and one Lucide icon.

---

## Installation & Setup

### 1. Clone & Install Dependencies
```bash
# Clone repository
git clone https://github.com/UltronTheAI/VasukiSquare.git
cd VasukiSquare

# Install Python package in editable mode with dependencies
pip install -e .

# Install Playwright browser binary for PDF generation
playwright install chromium
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and set your credentials:
```bash
cp .env.example .env
```

```ini
APP_ENV=development
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=vasukisquare
PDF_OUTPUT_DIR=./output
```

### 3. Customize Publication Branding (`config.json`)
VasukiSquare reads white-label branding from `./config.json` in the root directory (auto-created with defaults if absent):
```json
{
  "branding": {
    "author_name": "Vasuki",
    "publication_name": "Vasuki Publishing",
    "company_name": "VasukiSquare",
    "engine_name": "VasukiSquare AI Publishing Engine",
    "website": "https://vasukisquare.cc"
  },
  "edition": {
    "name": "FIRST EDITION",
    "year": 2026
  },
  "copyright": {
    "holder": "Vasuki Publishing",
    "all_rights_reserved": true
  },
  "book_defaults": {
    "language": "English"
  }
}
```
See [Configuration Guide](docs/configuration.md) for full details.

---

## CLI & Demo Usage

### Generate an Ebook via CLI
```bash
python scripts/generate_book.py \
  --topic "Designing Scalable Distributed Systems with Raft and LSM-Trees" \
  --target-pages 50 \
  --output-dir output/distributed_systems \
  --pdf \
  --cover
```

### Generate the End-to-End Demo
To produce a complete 40+ page demo book verifying all artifacts and database linking invariants:
```bash
python scripts/generate_demo.py
```

### Output Directory Structure
```
output/demo/
├── book.pdf             # Physical A4 printable PDF document
├── book.html            # Complete compiled HTML book
├── cover.html           # 1600x2560 source artwork HTML
├── cover.png            # High-resolution raster cover artwork
├── research.json        # Normalized, ranked research corpus & citations
├── book_plan.json       # Structural intent, chapter outline, and page budgets
└── pages/               # Individual standalone page HTML files
    ├── page_001.html
    ├── page_002.html
    └── ...
```

---

## Verification & Testing

VasukiSquare includes a comprehensive test suite across unit, integration, and rendering contracts:

```bash
# Run all unit tests
pytest tests/unit -q

# Run MongoDB and pipeline integration tests
pytest tests/integration -q

# Run A4 layout contract and snapshot rendering tests
pytest tests/rendering -q

# Run entire test suite
pytest -q
```

---

## Detailed Documentation

Comprehensive subsystem documentation is available in [`docs/`](docs/):

- [Architecture & Pipeline](docs/architecture.md)
- [Getting Started Guide](docs/getting-started.md)
- [Configuration Reference](docs/configuration.md)
- [MongoDB Schema & Page Graph](docs/mongodb-schema.md)
- [Deep Research Subsystem](docs/research.md)
- [Editorial Planning Agent](docs/editorial-planning.md)
- [Design System & Layout Engine](docs/design-system.md)
- [Rendering & PDF Compilation](docs/rendering-and-pdf.md)
- [End-to-End Pipeline](docs/pipeline.md)
- [Visual Design Specification](DESIGN.md)
- [Testing Specification & Layout Fixtures](TESTS.md)