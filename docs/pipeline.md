# VasukiSquare Generation Pipeline Architecture

VasukiSquare decomposes the generation of technical ebooks into an explicit, stateful multi-stage workflow to guarantee factual reliability, design consistency, and deterministic physical A4 pagination.

---

## 1. High-Level Lifecycle

```
[1. Prompt]
    │
    ▼
[2. Intent Inference] (Editorial Parameters, Audience, Depth, Tone)
    │
    ▼
[3. Deep Research] (Multi-Perspective Search, Deduplication, Ranking) ──► research.json
    │
    ▼
[4. Editorial Planning] (Chapter Outlines, Page Budgets, Layout Goals) ──► book_plan.json
    │
    ▼
[5. Cover Planning] (1600x2560 Canvas, Geometric Vectors, Token Colors) ──► cover.html & cover.png
    │
    ▼
[6. Page Writing & Rendering] (Structured PageContent, Code, Citations) ──► pages/*.html
    │
    ▼
[7. Validation & Controlled Repair] (A4 Capacity Limits, Automatic Page Splitting)
    │
    ▼
[8. MongoDB Persistence] (Books, Pages with Doubly-Linked IDs, Covers)
    │
    ▼
[9. Full Assembly & PDF Export] (Canonical book.html & Playwright A4 book.pdf)
```

---

## 2. Failure Recovery & Resiliency Invariants

1. **No Redundant Web Research**: Once research queries are executed, the resulting `ResearchCorpus` is serialized into `research.json` and reused throughout all downstream stages.
2. **Targeted Page Regeneration**: If a page fails capacity validation (e.g., text overflow > 2800 characters), the `PageRepairEngine` splits the overflowing body content cleanly across an inserted continuation page and re-links the graph pointers. The rest of the book and previous research are preserved without full-pipeline regeneration.
3. **Deterministic Page Numbering**: Every page in the book receives a contiguous 1-indexed page number from Page 1 (Cover) to Page N (Thank You).

---

## 3. CLI Commands

### Generate Ebook CLI
```bash
python scripts/generate_book.py --topic "How Modern Databases Work" --pages 60
```

### Run Full Demo
```bash
python scripts/generate_demo.py
```

### Outputs
- `output/demo/book.html`: Assembled canonical HTML document with embedded CSS variables.
- `output/demo/book.pdf`: Printable A4 PDF generated via Chromium.
- `output/demo/cover.png`: 1600×2560 high-resolution cover image.
- `output/demo/research.json`: Ingested and ranked research sources.
- `output/demo/book_plan.json`: Chapter structures, page budgets, and visual anchor assignments.
- `output/demo/pages/`: Individual standalone page HTML files.

