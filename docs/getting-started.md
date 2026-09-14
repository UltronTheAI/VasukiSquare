# Getting Started with VasukiSquare

Welcome to **VasukiSquare**, an AI-powered ebook generation engine in Python that researches, plans, authors, designs, renders, and exports professionally styled physical A4 PDF ebooks.

This guide provides a complete, step-by-step onboarding walkthrough for setting up your environment, configuring API providers, and generating your first publication.

---

## 1. Prerequisites & System Requirements

Before installing VasukiSquare, ensure your system meets the following requirements:

- **Operating System**: Windows 10/11, macOS 12+, or modern Linux (Ubuntu 20.04+, Debian 11+, Fedora 38+)
- **Python**: Python **3.11**, **3.12**, or **3.13** (64-bit recommended)
- **Git**: Installed and available on your system path
- **Disk Space**: At least 1 GB free space (for Playwright Chromium binaries and generated PDFs)
- **AI / LLM Provider**:
  - **Option A (Recommended for High Speed)**: A [Groq Cloud API Key](https://console.groq.com/) (Free tier available).
  - **Option B (Recommended for 100% Private / Offline)**: [Ollama](https://ollama.com/) running locally with `qwen2.5:7b-instruct` or `llama3.1:8b`.

---

## 2. Downloading & Extracting the Project

If you purchased or cloned the repository:

```bash
git clone https://github.com/UltronTheAI/VasukiSquare.git
cd VasukiSquare
```

If you downloaded a ZIP archive from Gumroad:
1. Extract the ZIP archive into a dedicated directory (e.g. `C:\Projects\VasukiSquare` or `~/projects/VasukiSquare`).
2. Open a terminal (PowerShell on Windows, or Bash/Zsh on Linux/macOS) and navigate into the extracted folder:
   ```bash
   cd VasukiSquare
   ```

---

## 3. Creating a Virtual Environment

Always run VasukiSquare inside an isolated Python virtual environment.

### Linux / macOS (Bash / Zsh)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> [!TIP]
> If PowerShell displays an `Execution_Policies` script restriction error, run:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

## 4. Installing Dependencies

Install VasukiSquare and its required dependencies in editable development mode:

### Standard Package Installation

```bash
pip install --upgrade pip
pip install -e .
```

### With Developer / Testing Dependencies

```bash
pip install -e ".[dev]"
```

### Alternative: Using `requirements.txt`

If you prefer installing via `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## 5. Installing the PDF Rendering Runtime (Playwright)

VasukiSquare uses Playwright with headless Chromium to compile pixel-perfect physical A4 PDFs. Install the Chromium browser binary:

```bash
playwright install chromium
```

*(On Linux headless servers, you can also run `playwright install-deps chromium` if system graphic libraries are missing).*

---

## 6. Configuring Environment Variables (`.env`)

Copy the provided environment template to create your local `.env` file:

### Linux / macOS:
```bash
cp .env.example .env
```

### Windows (PowerShell):
```powershell
Copy-Item .env.example .env
```

Open `.env` in your text editor and configure your chosen provider:

### Quick Setup: Groq Cloud (Recommended)
```env
LLM_PROVIDER=auto
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
SEARCH_PROVIDER=auto
```

### Quick Setup: Ollama Local (Free & Offline)
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
SEARCH_PROVIDER=duckduckgo
```

> [!IMPORTANT]
> Never commit your `.env` or `.env.local` file to version control. The repository's `.gitignore` excludes these files automatically.

---

## 7. Configuring Publisher Branding (`config.json`)

VasukiSquare reads publisher metadata from `config.json` at the root of the project. If `config.json` is missing, a default configuration is created automatically on your first run.

You can customize `config.json` directly:

```json
{
  "branding": {
    "author_name": "Vasuki Editorial Team",
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

---

## 8. Verifying Your Installation

Verify that the CLI entry points are registered and working:

```bash
vasukisquare --help
```

You can also run the test suite in mock mode (which requires zero API keys or external services):

```bash
pytest -q
```

---

## 9. Generating Your First Ebook

Run your first ebook generation command. You can use either the `vasukisquare` command or `python scripts/generate_book.py`:

### Using `vasukisquare` CLI:

```bash
vasukisquare --topic "Modern Distributed Systems: Consensus, Raft, and Gossip Protocols" --pages 30
```

### Using Python Script Directly:

```bash
python scripts/generate_book.py --topic "Modern Distributed Systems: Consensus, Raft, and Gossip Protocols" --pages 30
```

### Windows PowerShell Example:

```powershell
vasukisquare `
  --topic "Python Concurrency and AsyncIO in Practice" `
  --title "Modern Python Concurrency" `
  --pages 40 `
  --output-dir "./output/python-concurrency"
```

---

## 10. Inspecting Generated Output

When generation completes, your output folder (defaults to `./output/`) will contain:

| File | Purpose |
|---|---|
| `book.pdf` | Physical A4 compiled PDF document ready for reading or distribution |
| `book.html` | Complete standalone HTML document with embedded CSS |
| `cover.html` | Standalone high-res cover artwork |
| `book_manifest.json` | Detailed manifest of themes, chapters, authors, and page metrics |
| `book_plan.json` | Editorial structure, page budgets, and chapter section outlines |
| `research.json` | Deduplicated and ranked research sources |
| `preflight_report.json` | Layout and page geometry preflight validation |
| `generation_metrics.json` | Execution telemetry (token counts, latency, search stats) |
| `pages/page_*.html` | Standalone HTML files for each individual A4 page |
| `checkpoints/` | Stage checkpoints allowing interrupted jobs to resume with `--resume` |

---

## 11. Next Steps

- Explore the [User Guide](user-guide.md) for practical generation workflows and tips.
- Read the [CLI Reference](cli-reference.md) for all available command-line flags.
- Learn about [LLM & Search Providers](providers.md) to optimize model selection and search backends.
- Review [Customization](customization.md) to adapt layouts, color tokens, and schemas.
