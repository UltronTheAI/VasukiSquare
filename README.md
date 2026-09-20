# VasukiSquare

**VasukiSquare** is an AI-powered ebook generation engine written in Python. It researches, plans, writes, designs, renders, and compiles complete, publication-ready physical A4 PDF ebooks from a topic or editorial brief.

VasukiSquare solves the problem of unstructured, repetitive, and poorly formatted AI-generated documents. Instead of dumping raw markdown into a single prompt, VasukiSquare uses a multi-stage reasoning pipeline that performs web research, enforces fact-checking and domain citation hierarchies, structures cohesive chapters, designs high-contrast cover art, applies mathematical visual design tokens, and renders pixel-perfect physical A4 PDFs with zero overflow.

---

## What VasukiSquare Does

1. **Infers Intent & Audience**: Determines whether the topic is technical or non-technical, identifies target reader depth, and extracts required themes and elements.
2. **Conducts Multi-Perspective Research**: Expands the topic into search queries across documentation, specifications, and real-world patterns using swappable search providers (DuckDuckGo, SearXNG, Tavily, Serper, Brave, or Wikipedia).
3. **Plans Editorial Structure & Page Budgets**: Outlines chapters, assigns section visual anchors (code blocks, comparison tables, callout tips, checklists), and budgets physical A4 page counts.
4. **Designs Custom Cover Artwork**: Generates 1600 × 2560 canvas cover art using one of 6 layout styles, procedural math patterns, and WCAG-compliant contrast validation.
5. **Authors Structured Page Content**: Writes structured component blocks without markdown artifacts, applying alternating dark/light chapter themes and 6 distinct chapter opener templates.
6. **Audits & Repairs Physical Layout**: Evaluates A4 content density, dynamically splits overflowing sections, and recalculates dynamic Table of Contents page numbers.
7. **Compiles Publication Artifacts**: Renders HTML/CSS templates and exports physical A4 PDFs using Playwright headless Chromium.

---

## Features

- **Topic & Brief Driven Generation**: Generate complete books from a single topic string (`--topic`) or a detailed editorial brief (`--prompt` / `--prompt-file`).
- **Physical A4 PDF Compilation**: Exact ISO A4 dimensions (210mm × 297mm) rendered via Playwright Chromium with zero vertical overflow.
- **Dual LLM Provider Architecture**:
  - **Groq Cloud**: High-speed inference (200–500+ tokens/sec) with multi-key rotation pools, model failover pools, and cooldown management.
  - **Ollama Local**: 100% private, offline generation with zero external cloud API fees.
- **Swappable Web Research Backends**: Integrated support for DuckDuckGo (free zero-key search), SearXNG (local metasearch), Tavily, Serper, Brave Search, and offline mock modes.
- **Visual Design System**: Strict mathematical color tokens, Lucide SVG icons, responsive typography stacks, and alternating chapter themes (odd = dark mode, even = light mode).
- **6 Distinct Chapter Opener Styles**: Unique opener templates (`minimal_centered`, `left_accent_banner`, `split_contrast`, `editorial_classic`, `technical_blueprint`, `icon_heroic`).
- **High-Resolution Cover Engine**: 1600 × 2560 source canvas generator supporting 6 cover styles (`editorial_minimal`, `split_hero`, `geometric_accent`, `technical_blueprint`, `swiss_bold`, `minimal_monochrome`) with automated contrast repair.
- **White-Label Publisher Branding**: Complete customization of author names, publishing imprints, copyright notices, edition names, and website URLs via `config.json`.
- **Checkpoint & Resume Support**: Granular JSON stage and page checkpointing allows interrupted runs to resume seamlessly with `--resume`.
- **15-Point Content Quality Audit**: Automated validation checks structure, density, semantic validity, and code formatting before final assembly.
- **Production MongoDB Architecture**: Canonical 4-collection publication store (`books`, `pages`, `covers`, `ads`) with deterministic URL-safe slugs, featured slots 1..5, native ad inventory, atomic counters, and headless Next.js query support.

---

## Example Output

Every generated publication produces a dedicated output folder containing:

```
output/
├── book.pdf                 # Physical A4 compiled PDF ready for reading or distribution
├── book.html                # Assembled standalone HTML document with embedded CSS
├── cover.html               # Standalone high-resolution cover artwork
├── book_manifest.json       # Metadata, chapter manifest, theme tokens, and page counts
├── book_plan.json           # Editorial plan, page budgeting, and section visual anchors
├── research.json            # Deduplicated and ranked research sources
├── preflight_report.json    # Layout geometry and preflight audit report
├── generation_metrics.json  # Telemetry (token counts, duration, latency, search queries)
├── pages/                   # Standalone HTML files for each individual A4 page
│   ├── page_001.html        # Cover page
│   ├── page_002.html        # Imprint & copyright page
│   ├── ...                  # Content pages & chapter openers
│   └── page_040.html        # Backmatter / References page
└── checkpoints/             # Stage checkpoints for crash recovery
```

For practical generation examples, see the [Examples Directory](examples/):
- [Basic Generation Example](examples/basic_generation.md)
- [Technical Programming Book Example](examples/python_book.md)
- [Non-Technical / Productivity Book Example](examples/nontechnical_book.md)

---

## Architecture Overview

```
User Topic / Prompt
        │
        ▼
Stage 1: Intent Inference (EditorialPlannerAgent)
        │
        ▼
Stage 2: Deep Research (ResearchService & WebSearchTool)
        │
        ▼
Stage 3: Editorial & Chapter Planning (BookPlan & Page Budget)
        │
        ▼
Stage 4: Cover Planning & Design (CoverPlanner & ContrastValidator)
        │
        ▼
Stage 5: Page Authoring & Repair (PageWriterAgent & PageRepairEngine)
        │
        ▼
Stage 6: HTML Assembly, Preflight Audit & PDF Export (HtmlPageRenderer & PdfRenderer)
        │
        ▼
Stage 7: Canonical Database Persistence (Optional MongoDB Linked Graph)
        │
        ▼
Physical A4 PDF (book.pdf) & Canonical Web Store (MongoDB)
```

For full details on boundaries between deterministic Python rules, LLM reasoning, and rendering, see [System Architecture](docs/architecture.md).

---

## Requirements

- **Operating System**: Windows 10/11, macOS 12+, or modern Linux (Ubuntu 20.04+, Debian 11+, Fedora 38+).
- **Python**: Python **3.11**, **3.12**, or **3.13** (64-bit).
- **Browser Runtime**: Playwright Chromium (installed via `playwright install chromium`).
- **AI Provider (One of the following)**:
  - **Groq API Key** (for fast cloud generation; free tier available at [console.groq.com](https://console.groq.com/)), OR
  - **Ollama** running locally with `qwen2.5:7b-instruct` or `llama3.1:8b` (for 100% offline, zero-cost generation).
- **MongoDB** *(Optional)*: Only required if you wish to persist records to a MongoDB instance. Book generation and PDF export function completely without MongoDB.

---

## Installation

### 1. Standard Installation (Recommended)

1. Clone or extract the repository:
   ```bash
   git clone https://github.com/UltronTheAI/VasukiSquare.git
   cd VasukiSquare
   ```

2. Create and activate a virtual environment:

   **Linux / macOS (Bash / Zsh):**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   **Windows (PowerShell):**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. Install VasukiSquare in editable development mode:
   ```bash
   pip install --upgrade pip
   pip install -e .
   ```
   *(To include test and lint tooling: `pip install -e ".[dev]"`)*

4. Install the Playwright Chromium browser binary:
   ```bash
   playwright install chromium
   ```

### 2. Alternative: Installation via `requirements.txt`

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## Quick Start

1. Copy the environment configuration template:
   ```bash
   cp .env.example .env
   ```
   *(On Windows PowerShell: `Copy-Item .env.example .env`)*

2. Open `.env` and add your Groq API key:
   ```env
   GROQ_API_KEY=gsk_your_groq_api_key_here
   ```
   *(Or set `LLM_PROVIDER=ollama` to run with local Ollama)*

3. Generate your first ebook:
   ```bash
   vasukisquare --topic "Modern Distributed Systems: Consensus, Raft, and Gossip Protocols" --pages 30
   ```

4. Open `output/book.pdf` in your PDF reader or `output/book.html` in your web browser!

---

## Full CLI Usage

```
usage: vasukisquare [-h] --topic TOPIC [--title TITLE] [--prompt PROMPT]
                    [--prompt-file PROMPT_FILE] [--pages PAGES]
                    [--output-dir OUTPUT_DIR] [--no-pdf] [--no-db]
                    [--ollama-model OLLAMA_MODEL]
                    [--llm-provider {groq,ollama,auto}] [--resume]
```

### Argument Reference

| Flag | Type | Default | Description |
|---|---|---|---|
| `--topic TOPIC` | `str` | *Required* | The core topic or subject of the ebook to generate. |
| `--title TITLE` | `str` | `None` | Optional explicit public title (must be ≤ 50 characters). |
| `--prompt PROMPT` | `str` | `None` | Editorial brief specifying audience, tone, required concepts. |
| `--prompt-file FILE` | `str` | `None` | Path to text file containing editorial brief (mutually exclusive with `--prompt`). |
| `--pages PAGES` | `int` | `60` | Target physical A4 page count for the complete ebook. |
| `--output-dir DIR` | `str` | `./output` | Output directory for rendered PDF, HTML, and JSON artifacts. |
| `--no-pdf` | `flag` | `False` | Skip Playwright PDF compilation and only output HTML and JSON. |
| `--no-db` | `flag` | `False` | Skip persisting records to MongoDB. |
| `--ollama-model MODEL`| `str` | `None` | Specify local Ollama model (e.g. `qwen2.5:7b-instruct`). |
| `--llm-provider MODE` | `str` | `None` | Force LLM provider (`groq`, `ollama`, or `auto`). |
| `--resume` | `flag` | `False` | Resume generation from existing stage checkpoints in output directory. |
| `-h`, `--help` | `flag` | `False` | Show CLI help message and exit. |

*(You can also run `python scripts/generate_book.py [OPTIONS]` with identical arguments).*

---

## Example Commands

### 1. Beginner Programming Guide (Python)
```bash
vasukisquare \
  --topic "Python 3.12 Fundamentals: From Zero to Object-Oriented Programming" \
  --title "Python 3.12 Fundamentals" \
  --pages 40 \
  --output-dir "./output/python-basics"
```

### 2. Practical Non-Technical Guide (Habits & Productivity)
```bash
vasukisquare \
  --topic "Building Sustainable Daily Routines: The Psychology of Micro-Habits" \
  --title "Atomic Daily Routines" \
  --prompt "A practical self-improvement guide for knowledge workers. Focus on actionable exercises, reflection checklists, and a 30-day habit roadmap." \
  --pages 35 \
  --output-dir "./output/daily-routines"
```

### 3. Deep-Dive Systems Engineering Book (Distributed Databases)
```bash
vasukisquare \
  --topic "The Engineering Behind Modern Databases: B-Trees, WAL, MVCC and Distributed Storage" \
  --title "Modern Database Internals" \
  --pages 60 \
  --output-dir "./output/database-internals"
```

### 4. Offline Local Generation via Ollama
```bash
vasukisquare \
  --topic "Network Security and Penetration Testing Fundamentals" \
  --llm-provider ollama \
  --ollama-model qwen2.5:7b-instruct \
  --pages 25 \
  --output-dir "./output/network-security"
```

---

## Configuration

VasukiSquare separates infrastructure secrets from publisher branding:

1. **Environment Variables (`.env` / `.env.local`)**: Credentials, model pools, search providers, and performance limits.
2. **Publication Metadata (`config.json`)**: Author names, publisher imprints, corporate identities, edition names, and copyright notices.

### Key Environment Variables

| Variable | Required? | Default | Description | Example |
|---|---|---|---|---|
| `LLM_PROVIDER` | Optional | `auto` | Active provider (`auto`, `groq`, `ollama`) | `LLM_PROVIDER=auto` |
| `GROQ_API_KEY` | Conditional | `None` | Single or comma-separated list of Groq API keys | `GROQ_API_KEY=gsk_key1,gsk_key2` |
| `GROQ_MODEL` | Optional | `openai/gpt-oss-120b` | Primary Groq model | `GROQ_MODEL=openai/gpt-oss-120b` |
| `GROQ_MODELS` | Optional | `None` | Comma-separated Groq model pool for automatic failover | `GROQ_MODELS=openai/gpt-oss-120b,llama-3.3-70b-versatile` |
| `OLLAMA_BASE_URL` | Optional | `http://localhost:11434` | Ollama local endpoint | `OLLAMA_BASE_URL=http://localhost:11434` |
| `OLLAMA_MODEL` | Optional | `qwen2.5:7b-instruct` | Ollama model name | `OLLAMA_MODEL=qwen2.5:7b-instruct` |
| `SEARCH_PROVIDER` | Optional | `auto` | Active search backend (`auto`, `duckduckgo`, `searxng`, `tavily`, `serper`, `brave`, `mock`) | `SEARCH_PROVIDER=auto` |
| `SEARXNG_URL` | Optional | `http://localhost:8080` | Local SearXNG endpoint | `SEARXNG_URL=http://localhost:8080` |
| `TAVILY_API_KEY` | Optional | `None` | Tavily search API key | `TAVILY_API_KEY=tvly-...` |
| `PDF_OUTPUT_DIR` | Optional | `./output` | Default output folder | `PDF_OUTPUT_DIR=./output` |
| `MONGODB_URI` | Optional | `mongodb://localhost:27017` | Optional MongoDB connection URI | `MONGODB_URI=mongodb://localhost:27017` |

For the complete variable catalog, see [Configuration Guide](docs/configuration.md).

---

## Custom Publisher Branding (`config.json`)

To customize the author name, publisher imprint, website, and copyright notices on all generated publications, edit `config.json` at the root of the project:

```json
{
  "branding": {
    "author_name": "Jane Doe",
    "publication_name": "Northstar Books",
    "company_name": "Northstar Media LLC",
    "engine_name": "VasukiSquare AI Publishing Engine",
    "website": "https://northstarbooks.example.com"
  },
  "edition": {
    "name": "FIRST EDITION",
    "year": 2026
  },
  "copyright": {
    "holder": "Northstar Media LLC",
    "all_rights_reserved": true
  },
  "book_defaults": {
    "language": "English"
  }
}
```

---

## Project Structure

```
VasukiSquare/
├── README.md                # Primary product documentation
├── LICENSE                  # Apache 2.0 open-source software license
├── CHANGELOG.md             # Keep a Changelog release history
├── CONTRIBUTING.md          # Contributor and developer guidelines
├── SECURITY.md              # Security policy and secret safety rules
├── DESIGN.md                # Visual design system source of truth
├── TESTS.md                 # Testing contracts and verification rules
├── pyproject.toml           # Canonical packaging configuration and dependencies
├── setup.py                 # Setuptools compatibility shim
├── requirements.txt         # Runtime dependencies export
├── .env.example             # Complete environment configuration template
├── .gitignore               # Excludes secrets, caches, and build artifacts
├── config.json              # Validated publisher branding and copyright metadata
├── src/vasukisquare/        # Engine implementation
│   ├── cli.py               # Unified CLI parser and async execution runner
│   ├── agents/              # Reasoning agents (editorial, writer, cover, validator)
│   ├── book/                # Domain models, component blocks, layout enums
│   ├── config/              # Pydantic Settings and AppConfig loaders
│   ├── cover/               # 1600x2560 canvas cover generator & contrast validator
│   ├── database/            # PyMongo connection and document graph repositories
│   ├── design/              # Color tokens, themes, layout engine, Lucide icons
│   ├── llm/                 # LLMClient, Groq model/key pools, telemetry metrics
│   ├── pipeline/            # EbookGenerationPipeline orchestrator and state
│   ├── renderer/            # HTML assembler, zero-overflow repair, Playwright PDF exporter
│   ├── research/            # Query planner, source ranking, deduplication
│   ├── templates/           # Jinja2 templates (book.html, base.html, styles.css)
│   └── tools/               # Search tools (DuckDuckGo, SearXNG, Tavily, Wikipedia)
├── scripts/                 # Utility and standalone generation scripts
│   ├── generate_book.py     # Standalone book generation script
│   ├── generate_demo.py     # End-to-end demo verification script
│   └── verify_dom.py        # DOM structure inspector
├── tests/                   # 234+ automated tests
│   ├── unit/                # Unit tests (config, tokens, agents, pools, models)
│   ├── integration/         # Integration tests (pipeline, research, database)
│   └── rendering/           # Physical A4 rendering & snapshot contract tests
├── examples/                # Example commands and sample configuration files
└── docs/                    # Complete documentation suite
```

---

## Testing

VasukiSquare maintains an extensive automated test suite with 100% mock mode support (requiring zero live API keys or active database servers to run):

```bash
# Run all tests
pytest -q

# Run unit tests
pytest tests/unit -q

# Run integration tests
pytest tests/integration -q

# Run rendering validation tests
pytest tests/rendering -q
```

---

## Documentation Index

| Guide | Description |
|---|---|
| [**Documentation Hub**](docs/README.md) | Complete index of all technical and user guides |
| [**Getting Started**](docs/getting-started.md) | Step-by-step onboarding walkthrough for beginners |
| [**User Guide**](docs/user-guide.md) | Practical generation workflows and options |
| [**CLI Reference**](docs/cli-reference.md) | Exhaustive command-line arguments and flags |
| [**Automation & GitHub Actions**](docs/automation.md) | Production scheduling, GitHub Actions workflows, and MongoDB queue lifecycle |
| [**Configuration Guide**](docs/configuration.md) | Environment variables, `.env` options, and `config.json` |
| [**LLM & Search Providers**](docs/providers.md) | Groq, Ollama, DuckDuckGo, SearXNG, and commercial search setup |
| [**Customization Guide**](docs/customization.md) | Extending prompts, component blocks, color tokens, and themes |
| [**System Architecture**](docs/architecture.md) | Package architecture, Mermaid data-flows, and layer boundaries |
| [**Generation Pipeline**](docs/pipeline.md) | 7-stage generation lifecycle and checkpoint mechanics |
| [**Research Engine**](docs/research.md) | Multi-perspective search, ranking, and citation synthesis |
| [**Editorial Planning**](docs/editorial-planning.md) | Intent analysis, title rules, and page budgeting |
| [**Design System**](docs/design-system.md) | Physical A4 layout contracts, color tokens, and chapter openers |
| [**Cover Design Engine**](docs/cover-design.md) | 1600 × 2560 canvas, 6 cover styles, and contrast validation |
| [**Rendering & PDF Export**](docs/rendering-and-pdf.md) | Playwright Chromium PDF compilation and zero-overflow repair |
| [**MongoDB Schema**](docs/mongodb-schema.md) | Optional document graph persistence and collection models |
| [**Troubleshooting**](docs/troubleshooting.md) | Diagnosis and fixes for common installation and runtime errors |
| [**FAQ**](docs/faq.md) | Frequently asked technical and commercial questions |
| [**Commercial Distribution**](docs/commercial-distribution.md) | Source-code package details and API key guidance |
| [**Release Checklist**](docs/release-checklist.md) | Pre-distribution quality and packaging verification |

---

## Commercial Source-Code Distribution Note

When you purchase the VasukiSquare source code, you receive the full Python codebase to run, customize, and self-host the publishing engine. 

- **Infrastructure**: Customers run the engine on their own machines or cloud infrastructure.
- **API Keys**: Customers supply their own API keys where applicable (e.g. Groq Cloud, Tavily) or use free local backends (Ollama, DuckDuckGo, SearXNG).

---

## Security

- **Never commit `.env` or `.env.local` files.** The repository `.gitignore` excludes local environment files by default.
- If an API key is ever exposed, rotate it immediately in your provider dashboard.
- For vulnerability reporting guidelines, please see [SECURITY.md](SECURITY.md).

---

## License

VasukiSquare is licensed under the [Apache License 2.0](LICENSE).
Commercial rights for generated book text depend on your applicable model provider terms and citation attribution rules.

---

## Support & Issues

For bugs, questions, and feature discussions, please use the official repository issue tracker:
[GitHub Issues](https://github.com/UltronTheAI/VasukiSquare/issues)