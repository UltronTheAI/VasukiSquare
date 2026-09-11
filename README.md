# VasukiSquare

VasukiSquare is an AI-powered research, editorial, HTML layout, and PDF generation engine written in Python.

It generates professionally designed ebooks from a user topic or description, enforcing strict visual design guidelines, source attribution, and deterministic A4 PDF page rendering.

## Core Generation Pipeline

```
Prompt
  └── Intent
        └── Research
              └── Editorial Plan
                    └── Chapter Plan
                          └── Page Plan
                                └── Page Content
                                      └── HTML Rendering
                                            └── Validation
                                                  └── MongoDB Persistence
                                                        └── PDF Rendering
```

## Key Principles & Architecture

- **Python Only & Typed**: Strict Pydantic models for all structured generation and data models.
- **Design System as Source of Truth**: Layouts, typography, and color tokens strictly follow `DESIGN.md`.
- **Lucide Icons**: Semantic SVG icon handling using design token colors.
- **MongoDB Persistence**: Books, pages, and covers are persisted with explicit page linking (`starting_page_id`, `book_id`, `previous_page_id`, `next_page_id`).
- **A4 Physical Page Layout**: Canonical HTML/CSS rendering formatted specifically for A4 printing via Playwright/Chromium.

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -e .
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env` and configure your API keys and MongoDB connection:
   ```bash
   cp .env.example .env
   ```

3. **Run Tests**:
   ```bash
   pytest tests/unit -q
   pytest tests/integration -q
   pytest tests/rendering -q
   pytest -q
   ```

## Documentation

- [Getting Started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Design Specification](DESIGN.md)
- [Testing Contract](TESTS.md)