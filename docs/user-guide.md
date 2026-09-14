# VasukiSquare User Guide

This guide is designed for developers, creators, technical writers, and publishers who want to generate complete, professionally styled ebooks using VasukiSquare.

---

## 1. Core Workflow Overview

Generating an ebook with VasukiSquare follows a clean 3-step lifecycle:

```
1. Define Topic & Options ──► 2. Run CLI Command ──► 3. Open Generated PDF / HTML
```

The engine automatically handles background research, fact verification, chapter outlining, page budgeting, visual theming, layout rendering, and PDF compilation.

---

## 2. Choosing Your Generation Mode

### Mode A: Quick Generation from a Topic
If you have a clear topic, provide it directly using `--topic`:

```bash
vasukisquare --topic "Containerization Fundamentals with Docker and Podman"
```

### Mode B: Providing an Explicit Title
By default, the engine infers a concise, professional title (≤ 50 characters). You can override this using `--title`:

```bash
vasukisquare \
  --topic "Building Scalable Microservices with Go and gRPC" \
  --title "Production Microservices in Go"
```

### Mode C: Providing an Editorial Brief (`--prompt`)
To guide the tone, audience, specific case studies, or chapter focus, provide a prompt:

```bash
vasukisquare \
  --topic "Machine Learning Operations (MLOps)" \
  --title "Applied MLOps in Production" \
  --prompt "Focus on CI/CD pipelines for ML models, feature stores, drift detection with Evidently, model registry patterns with MLflow, and Kubernetes inference serving." \
  --pages 45
```

### Mode D: Using an Editorial Brief File (`--prompt-file`)
For extensive requirements, save your brief into a markdown or text file (e.g. `brief.txt`):

```bash
vasukisquare \
  --topic "Modern Data Engineering" \
  --prompt-file ./brief.txt \
  --pages 50
```

---

## 3. Adjusting Book Length & Page Count

The `--pages` argument specifies the target physical A4 page budget:

```bash
vasukisquare --topic "Mastering Regular Expressions" --pages 25
```

### How Page Budgeting Works
- **Cover Page**: Page 1 (Light minimalist cover canvas).
- **Frontmatter**: Imprint/copyright page, preface/introduction, and dynamic Table of Contents.
- **Chapters**: Distributed across chapter openers and content pages.
- **Backmatter**: Authoritative references / bibliography page and concluding thank-you page.
- **Dynamic Overflow Repair**: The engine automatically balances and formats content blocks to fit physical A4 pages without vertical overflow.

---

## 4. Selecting Output Locations

Specify `--output-dir` to save each publication into its own folder:

```bash
vasukisquare \
  --topic "Rust Systems Programming" \
  --output-dir "./output/rust-systems-book"
```

Each generation directory contains:
- `book.pdf`: Ready-to-read physical A4 document.
- `book.html`: Standalone responsive HTML version.
- `cover.html`: Standalone cover artwork.
- `book_manifest.json`: Publication summary metadata.
- `research.json`: Extracted and ranked research citations.
- `pages/`: Individual page HTML files.

---

## 5. Resuming Interrupted Generations

VasukiSquare automatically writes stage and page checkpoints to the output directory. If a generation is interrupted by a network issue or rate limit, add the `--resume` flag to continue from the latest checkpoint:

```bash
vasukisquare \
  --topic "Modern Data Engineering" \
  --output-dir "./output/data-eng" \
  --resume
```

The engine reloads completed intent, research, editorial plans, and authored pages from disk, only generating the remaining pages.

---

## 6. Customizing Publisher Branding

To change the author name, publisher imprint, website, or edition displayed on your books, edit `config.json` in the root directory:

```json
{
  "branding": {
    "author_name": "Sarah Jenkins",
    "publication_name": "Apex Technical Press",
    "company_name": "Apex Media Group",
    "engine_name": "VasukiSquare AI Publishing Engine",
    "website": "https://apexpress.example.com"
  },
  "edition": {
    "name": "FIRST EDITION",
    "year": 2026
  },
  "copyright": {
    "holder": "Apex Media Group LLC",
    "all_rights_reserved": true
  },
  "book_defaults": {
    "language": "English"
  }
}
```

---

## 7. Useful Generation Flags

| Scenario | Command Flag |
|---|---|
| Generate HTML only (skip PDF compilation) | `--no-pdf` |
| Skip MongoDB database persistence | `--no-db` |
| Select local Ollama model | `--ollama-model qwen2.5:7b-instruct` |
| Force specific LLM provider | `--llm-provider groq` or `--llm-provider ollama` |
| Resume from checkpoint | `--resume` |

