# VasukiSquare CLI Reference

This document provides a comprehensive reference for all command-line arguments and flags supported by VasukiSquare.

---

## 1. Invocation Syntax

VasukiSquare provides two primary execution workflows:

### A. Manual Topic Generation
Generate a book from a manually specified topic and optional brief:
```bash
python scripts/generate_book.py --topic "Building Better Daily Habits" --title "Good Habits" --pages 60
```
*(or via installed console script `vasukisquare [OPTIONS]` / `vasuki [OPTIONS]`)*

### B. Automated Queue Generation
Claim and generate the highest-priority researched book idea from MongoDB:
```bash
python scripts/generate_book.py --from-queue
```

---

## 2. Argument Reference Table

| Flag | Type | Default | Required | Description |
|---|---|---|---|---|
| `--topic` | `str` | `None` | **Yes (Manual)** | The core subject or topic of the ebook to generate (required if not using `--from-queue` or `--idea-id`). |
| `--from-queue` | `flag` | `False` | No | Atomically claim and generate the next ready book idea from the MongoDB `book_ideas` queue. |
| `--idea-id` | `str` | `None` | No | Target a specific idea ID from the queue to claim and generate. |
| `--category` | `str` | `None` | No | Optional domain category filter when claiming an idea from the queue. |
| `--dry-run` | `flag` | `False` | No | In queue mode, claim and validate the idea parameters and revert status to READY without running generation. |
| `--title` | `str` | `None` | No | Explicit public-facing title. Must be ≤ 50 characters without commentary. |
| `--prompt` | `str` | `None` | No | Editorial instructions specifying target audience, tone, required elements, and themes. Mutually exclusive with `--prompt-file`. |
| `--prompt-file` | `str` | `None` | No | Path to a text file containing the editorial brief. Mutually exclusive with `--prompt`. |
| `--pages` | `int` | `60` (manual) | No | Target physical A4 page count for the complete book (strictly 40–100 pages for queue ideas). |
| `--output-dir` | `str` | `./output` | No | Directory where generated book files, assets, checkpoints, and PDF are saved. |
| `--no-pdf` | `flag` | `False` | No | Skip Playwright PDF compilation and only output HTML, manifest, and JSON artifacts. |
| `--no-db` | `flag` | `False` | No | Skip persisting book, page, and cover records to MongoDB. |
| `--ollama-model` | `str` | `None` | No | Override the configured Ollama model for local generation (e.g. `qwen2.5:7b-instruct`). |
| `--llm-provider` | `str` | `None` | No | Explicitly choose LLM provider (`groq`, `ollama`, or `auto`). |
| `--resume` | `flag` | `False` | No | Resume generation from existing stage and page checkpoints in the output directory. |
| `-h`, `--help` | `flag` | `False` | No | Display the CLI help message and exit. |

---

## 3. Detailed Flag Descriptions

### `--from-queue` (Optional)
Operates VasukiSquare in automated pipeline mode. It atomically queries MongoDB for the highest-ranked `ready` book idea (or recovers a stale `processing` claim), sets its status to `processing`, feeds its stored `topic`, `title`, `prompt`, and `pages` into the generation orchestrator, links the generated book record, and transitions the idea status to `completed` upon success (or `failed` if an error occurs).

If no ready ideas are found in the queue, the CLI prints a clean notification and exits with status 0.

**Example:**
```bash
python scripts/generate_book.py --from-queue
```

---

### `--idea-id IDEA_ID` (Optional)
Claims and generates a specific book idea by its MongoDB document ID. The idea must be in `ready` state or eligible for retry.

**Example:**
```bash
python scripts/generate_book.py --idea-id "idea_tech_deep_learning_2026"
```

---

### `--dry-run` (Optional)
When used with `--from-queue` or `--idea-id`, claims the idea, verifies that all parameters (including 40–100 page bounds) are valid, displays the resolved generation plan, and reverts the idea status back to `ready` in MongoDB without invoking LLMs or rendering pages.

**Example:**
```bash
python scripts/generate_book.py --from-queue --dry-run
```

---

### `--topic TOPIC` (Required in Manual Mode)
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
Target number of physical A4 pages. The editorial planner distributes this budget across frontmatter, chapter openers, deep-dive section pages, reference listings, and backmatter. Automated queue ideas strictly enforce the 40–100 page boundary.

**Example:**
```bash
vasukisquare --topic "Linux CLI Mastery" --pages 50
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
