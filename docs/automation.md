# Automated Publishing & Research Infrastructure

This document details the automated scheduling, GitHub Actions workflows, MongoDB queue lifecycle, and production operations for VasukiSquare.

---

## 1. High-Level Architecture

VasukiSquare implements a decoupled **Producer-Consumer** publishing loop where:
1. **GitHub Actions** handles **WHEN** (cron schedule and workflow dispatch triggers).
2. **VasukiSquare Engine** handles **WHAT** (deep research, editorial planning, layout, and rendering).
3. **MongoDB** handles **STATE** (persistent queue of researched ideas, published books, and linked pages).

```mermaid
flowchart TD
    subgraph Sunday Schedule [Weekly Research: Sunday 02:00 UTC]
        R1[GitHub Actions: research-ideas.yml] --> R2[scripts/research_ideas.py]
        R2 --> R3[Discover Trends & Search Web]
        R3 --> R4[Deduplicate against Mongo History]
        R4 --> R5[Rank & Validate 40-100 Page Fit]
        R5 --> R6[("MongoDB 'book_ideas' (Status: READY)")]
    end

    subgraph Tuesday Schedule [Weekly Generation 1: Tuesday 04:00 UTC]
        G1[GitHub Actions: generate-book.yml] --> G2[scripts/generate_book.py --from-queue]
        G2 --> G3["Atomic Claim (Status: PROCESSING)"]
        G3 --> G4[Full 7-Stage Pipeline Execution]
        G4 --> G5[("Persist Book & Pages to MongoDB")]
        G5 --> G6["Mark Idea COMPLETED (Link book_id)"]
        G4 -. Failure .-> G7["Mark Idea FAILED (Record Trace)"]
    end

    subgraph Friday Schedule [Weekly Generation 2: Friday 04:00 UTC]
        F1[GitHub Actions: generate-book.yml] --> F2[scripts/generate_book.py --from-queue]
        F2 --> F3["Atomic Claim Next Idea (Status: PROCESSING)"]
        F3 --> F4[Full 7-Stage Pipeline Execution]
        F4 --> F5[("Persist Book & Pages to MongoDB")]
        F5 --> F6["Mark Idea COMPLETED (Link book_id)"]
        F4 -. Failure .-> F7["Mark Idea FAILED (Record Trace)"]
    end
```

---

## 2. Schedule & Timezone Reference

| Workflow | Day(s) | UTC Cron | UTC Time | IST (UTC+5:30) | EST (UTC-5) | PST (UTC-8) |
|---|---|---|---|---|---|---|
| **Research Ideas** | Sunday | `0 2 * * 0` | 02:00 UTC | 07:30 AM Sun | 09:00 PM Sat | 06:00 PM Sat |
| **Book Generation #1** | Tuesday | `0 4 * * 2,5` | 04:00 UTC | 09:30 AM Tue | 11:00 PM Mon | 08:00 PM Mon |
| **Book Generation #2** | Friday | `0 4 * * 2,5` | 04:00 UTC | 09:30 AM Fri | 11:00 PM Thu | 08:00 PM Thu |
| **Daily Promotion** | Daily | `37 4 * * *` | 04:37 UTC | 10:07 AM Daily | 11:37 PM Prev | 08:37 PM Prev |

> [!NOTE]
> - Research runs early Sunday morning to replenish the idea pool with at least 5 vetted ideas.
> - Book Generation runs Tuesdays and Fridays to produce complete A4 ebooks from the queue.
> - Daily Promotion runs every day at a non-round minute (`04:37 UTC` / `10:07 IST`) to fairly select and publish up to 3 technical articles to DEV Community.

---

## 3. GitHub Actions Workflows

### A. Research Workflow (`.github/workflows/research-ideas.yml`)
- **Purpose**: Autonomous trending topic discovery, multi-perspective search validation, 4-stage deduplication, and MongoDB persistence.
- **Concurrency Group**: `vasuki-research-ideas` (`cancel-in-progress: false`).
- **Timeout**: 30 minutes.
- **Workflow Dispatch Inputs**:
  - `count`: Target number of ready ideas to research (default: `5`).
  - `min_score`: Minimum composite bookworthiness threshold (default: `0.70`).
  - `category`: Optional topic category filter (e.g., `Technology`, `Leadership`).
  - `dry_run`: Simulate research without database writes (default: `false`).
  - `verbose`: Enable debug logging (default: `false`).
- **Artifacts**: Uploads `artifacts/research_ideas.json` (retention: 14 days).

### B. Generation Workflow (`.github/workflows/generate-book.yml`)
- **Purpose**: Atomically claims the next highest-scoring idea from MongoDB, installs native Playwright Chromium dependencies, compiles physical A4 HTML/PDF books, and updates state.
- **Concurrency Group**: `vasuki-generate-book` (`cancel-in-progress: false`).
- **Timeout**: 90 minutes.
- **Native PDF Dependencies**: Automatically installs Playwright Chromium and OS-level shared libraries via `playwright install --with-deps chromium`.
- **Workflow Dispatch Inputs**:
  - `idea_id`: Target a specific idea by MongoDB document ID.
  - `category`: Optional category filter when claiming from queue.
  - `dry_run`: Claim and validate parameters, then revert status to `ready`.
  - `no_pdf`: Skip PDF compilation (HTML and JSON manifest only).
- **Artifacts**: Uploads generated PDF, HTML, manifest, and metrics from `./output/` (retention: 14 days).

### C. Daily Promotion Workflow (`.github/workflows/promote.yml`)
- **Purpose**: Selects 3 eligible published ebooks from MongoDB using a fair weighted algorithm, generates high-value technical articles with canonical backlinks via Groq LLMs, and publishes to DEV Community (`dev.to`).
- **Concurrency Group**: `vasuki-daily-promotion` (`cancel-in-progress: false`).
- **Timeout**: 30 minutes.
- **Workflow Dispatch Inputs**:
  - `dry_run`: Generate campaign and persist to MongoDB without calling external DEV API (default: `true` for safe manual execution).
  - `count`: Number of ebooks to select and promote (default: `3`).
  - `book`: Optional specific book ID or slug to target.
  - `verbose`: Enable verbose debug logging (default: `false`).
- **Artifacts**: Uploads `artifacts/promotion_summary.json` and automatically renders detailed status in `$GITHUB_STEP_SUMMARY`.

---

## 4. Required Secrets & Configuration

Configure these secrets in your GitHub repository settings under **Settings > Secrets and variables > Actions**:

| Name | Type | Required? | Description |
|---|---|---|---|
| `MONGODB_URI` | Secret | **Yes** | MongoDB Atlas or remote instance connection URI (e.g., `mongodb+srv://user:pass@cluster.mongodb.net`). |
| `GROQ_API_KEY` | Secret | **Yes** | Groq API Key (or comma-separated keys for automatic rotation). |
| `DEVTO_API_KEY` | Secret | **Yes** | DEV Community API key (from https://dev.to/settings/account) for daily automated publishing. |
| `MONGODB_DATABASE` | Secret / Var | Optional | MongoDB database name (default: `vasukisquare`). |
| `PUBLICATION_BASE_URL` | Variable | Optional | Public reader base URL (default: `https://vasukisquare.cc`). |
| `TAVILY_API_KEY` | Secret | Optional | Tavily AI search key for augmented research. |
| `SERPER_API_KEY` | Secret | Optional | Serper Google Search API key. |
| `BRAVE_SEARCH_API_KEY` | Secret | Optional | Brave Search API key. |

### Configurable Environment Variables

| Variable | Default | Description |
|---|---|---|
| `RESEARCH_IDEA_COUNT` | `5` | Target number of production ideas researched per run. |
| `RESEARCH_MIN_SCORE` | `0.70` | Minimum composite bookworthiness score for acceptance. |
| `IDEA_PROCESSING_TIMEOUT_MINUTES` | `180` | Duration (3 hours) after which an incomplete processing claim is considered stale and eligible for recovery. |
| `IDEA_MAX_ATTEMPTS` | `3` | Maximum generation attempts before an idea is locked against re-processing. |
| `IDEA_COLLECTION` | `book_ideas` | MongoDB collection storing idea queue documents. |
| `BOOK_COLLECTION` | `books` | MongoDB collection storing canonical book publications. |

---

## 5. MongoDB Idea Lifecycle & Safety Controls

```
                      ┌───────────────┐
                      │  DISCOVERED   │
                      └───────┬───────┘
                              │ Passed dedup & score >= 0.70
                              ▼
                      ┌───────────────┐
      ┌──────────────>│     READY     │
      │ (Revert)      └───────┬───────┘
      │                       │
      │                       │ Atomic claim (find_one_and_update)
      │                       ▼
      │               ┌───────────────┐
      │               │  PROCESSING   │◄──── Stale claim recovery
      │               └───────┬───────┘      (if claimed_at > 180m & attempts < 3)
      │                       │
      ├───────────────────────┼───────────────────────┐
      │ (Dry run)             │ (Success)             │ (Exception)
      ▼                       ▼                       ▼
┌───────────┐         ┌───────────────┐       ┌───────────────┐
│   READY   │         │   COMPLETED   │       │    FAILED     │
└───────────┘         │ (links book)  │       │ (stores error)│
                      └───────────────┘       └───────┬───────┘
                                                      │
                                                      │ If attempt_count < 3
                                                      └───────► (Eligible for retry)
```

### Safety Guarantees
1. **Atomic Lock**: Idea claims use MongoDB `find_one_and_update` with `$set: {status: "processing"}` and `$inc: {attempt_count: 1}`. Even with multiple runners, no two workers can claim the same idea.
2. **Stale Claim Recovery**: If a runner crashes or times out, jobs older than 180 minutes are automatically recovered on subsequent runs.
3. **Attempt Capping**: If an idea fails 3 times, it is permanently locked to prevent poison-pill execution loops.
4. **Empty Queue Graceful Exit**: If the queue has no `ready` ideas, the generation script prints a clean message and exits with status `0`, ensuring scheduled workflows succeed cleanly without false alarms.
5. **Strict Page Bounds**: Queue-claimed ideas enforce physical A4 40–100 page bounds; out-of-bound ideas are automatically marked `rejected`.

---

## 6. Local Equivalent Commands

Run the exact automation commands locally:

### 1. Research Ideas
```bash
# Research 5 trending ideas and persist to MongoDB
python scripts/research_ideas.py --count 5

# Dry-run without database persistence
python scripts/research_ideas.py --count 3 --dry-run --export-json artifacts/test_ideas.json
```

### 2. Generate Book from Queue
```bash
# Claim and generate next ready idea from queue
python scripts/generate_book.py --from-queue

# Dry-run claim and validate parameters
python scripts/generate_book.py --from-queue --dry-run

# Target specific idea ID
python scripts/generate_book.py --idea-id "idea_tech_deep_learning_2026"
```

