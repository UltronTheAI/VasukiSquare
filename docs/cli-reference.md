# VasukiSquare CLI Reference

This document provides a comprehensive reference for all command-line arguments and flags supported by VasukiSquare.

---

## 1. Invocation Syntax

VasukiSquare provides two equivalent entry points:

### 1. Unified Console Entry Point (Installed via `pip install -e .`):
```bash
vasukisquare [OPTIONS]
```
*(or short alias `vasuki [OPTIONS]`)*

### 2. Standalone Script:
```bash
python scripts/generate_book.py [OPTIONS]
```

---

## 2. Argument Reference Table

| Flag | Type | Default | Required | Description |
|---|---|---|---|---|
| `--topic` | `str` | None | **Yes** | The core subject or topic of the ebook to generate. |
| `--title` | `str` | `None` | No | Explicit public-facing title. Must be ≤ 50 characters without commentary. |
| `--prompt` | `str` | `None` | No | Editorial instructions specifying target audience, tone, required elements, and themes. Mutually exclusive with `--prompt-file`. |
| `--prompt-file` | `str` | `None` | No | Path to a text file containing the editorial brief. Mutually exclusive with `--prompt`. |
| `--pages` | `int` | `60` | No | Target physical A4 page count for the complete book. |
| `--output-dir` | `str` | `./output` | No | Directory where generated book files, assets, checkpoints, and PDF are saved. |
| `--no-pdf` | `flag` | `False` | No | Skip Playwright PDF compilation and only output HTML, manifest, and JSON artifacts. |
| `--no-db` | `flag` | `False` | No | Skip persisting book, page, and cover records to MongoDB. |
| `--ollama-model` | `str` | `None` | No | Override the configured Ollama model for local generation (e.g. `qwen2.5:7b-instruct`). |
| `--llm-provider` | `str` | `None` | No | Explicitly choose LLM provider (`groq`, `ollama`, or `auto`). |
| `--resume` | `flag` | `False` | No | Resume generation from existing stage and page checkpoints in the output directory. |
| `-h`, `--help` | `flag` | `False` | No | Display the CLI help message and exit. |

---

## 3. Detailed Flag Descriptions

### `--topic TOPIC` (Required)
The primary topic of the publication. The engine uses this string to classify whether the book is technical or non-technical, generate research queries, infer target audience, and outline chapters.

**Example:**
```bash
vasukisquare --topic "The Architecture of Modern Databases: B-Trees, LSM-Trees, and MVCC"
```

---

### `--title TITLE` (Optional)
Overrides automatic title generation. VasukiSquare enforces a maximum title length of 50 characters to guarantee clean typography on cover art and running headers.

**Example:**
```bash
vasukisquare --topic "Building Microservices in Go" --title "Production Microservices in Go"
```

---

### `--prompt PROMPT` / `--prompt-file FILE` (Optional)
Provides detailed editorial instructions. The planner extracts audience level, required chapter concepts, tone, and specific elements (e.g. checklists, exercises, code listings).

**Inline Example:**
```bash
vasukisquare \
  --topic "Fullstack Next.js and TypeScript" \
  --prompt "An intermediate guide focusing on App Router, Server Components, React Server Actions, Tailwind CSS v4, and Prisma ORM."
```

**File Example:**
```bash
vasukisquare \
  --topic "Fullstack Next.js and TypeScript" \
  --prompt-file ./editorial_brief.txt
```

---

### `--pages PAGES` (Optional, Default: `60`)
Target number of physical A4 pages. The editorial planner distributes this budget across frontmatter, chapter openers, deep-dive section pages, reference listings, and backmatter.

**Example:**
```bash
vasukisquare --topic "Linux CLI Mastery" --pages 30
```

---

### `--output-dir OUTPUT_DIR` (Optional, Default: `./output`)
Directory where all artifacts are written. Parent directories will be created automatically if they do not exist.

**Example:**
```bash
vasukisquare --topic "Deep Learning Foundations" --output-dir "./output/deep-learning-guide"
```

---

### `--no-pdf` (Optional)
Disables the Playwright PDF rendering stage. Use this for fast test runs or when you only require HTML / JSON assets.

**Example:**
```bash
vasukisquare --topic "SQL Optimization Guide" --no-pdf
```

---

### `--no-db` (Optional)
Disables MongoDB persistence. The engine skips all database connection attempts and writes all assets exclusively to disk.

**Example:**
```bash
vasukisquare --topic "Rust Web Development" --no-db
```

---

### `--llm-provider {groq,ollama,auto}` (Optional)
Overrides the `LLM_PROVIDER` environment variable for a single execution:
- `groq`: Forces Groq cloud inference.
- `ollama`: Forces Ollama local inference.
- `auto`: Uses Groq if `GROQ_API_KEY` is configured; otherwise uses Ollama.

**Example:**
```bash
vasukisquare --topic "API Security Testing" --llm-provider groq
```

---

### `--ollama-model MODEL` (Optional)
Overrides the `OLLAMA_MODEL` environment variable to test different local model checkpoints.

**Example:**
```bash
vasukisquare --topic "Prompt Engineering" --llm-provider ollama --ollama-model llama3.1:8b
```

---

### `--resume` (Optional)
Resumes an incomplete or interrupted generation job from stage checkpoints (`intent.json`, `research.json`, `book_plan.json`, `cover_plan.json`, and `pages/page_*.json`).

**Example:**
```bash
vasukisquare --topic "Cloud Architecture" --output-dir "./output/cloud" --resume
```

