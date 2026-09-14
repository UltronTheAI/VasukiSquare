# Example: Basic Ebook Generation

This example demonstrates how to generate a publication-ready ebook using the default settings with either the `vasukisquare` CLI entry point or the Python script.

## 1. Simplest Generation Command

Generate an ebook from a single topic prompt:

### Using the `vasukisquare` CLI:
```bash
vasukisquare --topic "Modern System Design: Microservices, Event Sourcing, and CQRS"
```

### Using Python directly:
```bash
python scripts/generate_book.py --topic "Modern System Design: Microservices, Event Sourcing, and CQRS"
```

## 2. Using an Editorial Brief (`--prompt`)

You can provide a specific brief to steer tone, target audience, and required topics:

```bash
vasukisquare \
  --topic "Building Scalable Web APIs in FastAPI" \
  --title "FastAPI in Production" \
  --prompt "A hands-on guide for backend engineers covering async routing, Pydantic v2 schemas, JWT authentication, background workers with Celery, and Docker deployment." \
  --pages 40 \
  --output-dir "./output/fastapi-book"
```

## 3. Using a Brief File (`--prompt-file`)

For extensive briefs, save the text in a file (e.g. `brief.txt`) and pass `--prompt-file`:

```bash
vasukisquare \
  --topic "Cloud Native Kubernetes Operations" \
  --prompt-file ./brief.txt \
  --pages 50
```

## 4. Generated Artifacts

Upon completion, the target directory (e.g. `./output/fastapi-book/`) contains:

| File | Description |
|---|---|
| `book.pdf` | Physical A4 compiled PDF document ready for reading or distribution |
| `book.html` | Assembled, standalone HTML document of the complete book |
| `cover.html` | High-resolution SVG/HTML source artwork of the cover |
| `book_manifest.json` | Canonical metadata, chapter structure, theme tokens, and page counts |
| `book_plan.json` | Editorial structure, page budgeting, and section outlines |
| `research.json` | Deduplicated and ranked research sources and extracted knowledge |
| `preflight_report.json` | Geometry and visual layout preflight checks |
| `generation_metrics.json` | Telemetry including token usage, latency, and search queries |
| `pages/page_*.html` | Standalone HTML files for each individual A4 page |
| `checkpoints/` | Stage checkpoints enabling interrupted runs to resume seamlessly |

