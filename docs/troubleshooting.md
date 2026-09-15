# Troubleshooting Guide

This guide details common installation, environment, provider, and rendering issues along with their exact causes and solutions.

---

## 1. Installation & Environment Issues

### Symptom: `ModuleNotFoundError: No module named 'vasukisquare'`
- **Cause**: The package was not installed in editable mode within the active virtual environment.
- **Fix**: Activate your virtual environment and run:
  ```bash
  pip install -e .
  ```

### Symptom: PowerShell Script Execution Policy Error
- **Cause**: Windows PowerShell restricts running activation scripts by default.
- **Fix**: Open PowerShell as current user and run:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

### Symptom: Python Version Incompatibility
- **Cause**: Running on Python 3.10 or older.
- **Fix**: VasukiSquare requires Python 3.11+. Check your version with `python --version` and install a supported Python release (3.11, 3.12, or 3.13).

---

## 2. Configuration & `config.json` Errors

### Symptom: `[CONFIG ERROR] Field: branding.author_name Problem: Required field is missing`
- **Cause**: The `config.json` file is missing required fields or has malformed JSON syntax.
- **Fix**: VasukiSquare prints exact line and field hints. Check `config.json` against the schema in `docs/configuration.md` or delete `config.json` so VasukiSquare can recreate default values automatically.

---

## 3. LLM Provider Issues

### Symptom: `Cannot initialize Groq LLM: GROQ_API_KEY is missing or empty`
- **Cause**: `LLM_PROVIDER` is set to `groq` (or `auto`), but no valid `GROQ_API_KEY` was found in `.env`.
- **Fix**: Add your API key to `.env`:
  ```env
  GROQ_API_KEY=gsk_your_key_here
  ```
  Or switch to local Ollama execution by setting `LLM_PROVIDER=ollama`.

### Symptom: `Ollama server at http://localhost:11434 returned status code ... / connection refused`
- **Cause**: Ollama is not running locally.
- **Fix**: Start the Ollama server:
  ```bash
  ollama serve
  ```

### Symptom: `Configured Ollama model 'qwen2.5:7b-instruct' is not installed`
- **Cause**: The model has not been downloaded to your local Ollama library.
- **Fix**: Pull the model:
  ```bash
  ollama pull qwen2.5:7b-instruct
  ```

### Symptom: Groq HTTP 429 Rate Limit
- **Cause**: Reached Groq token-per-minute (TPM) or request-per-minute (RPM) limits.
- **Fix**:
  1. Configure multiple API keys in `GROQ_API_KEY=gsk_key1,gsk_key2` to enable automatic key pooling.
  2. Configure a multi-model pool in `GROQ_MODELS=openai/gpt-oss-120b,llama-3.3-70b-versatile,llama-3.1-8b-instant`.
  3. Enable provider fallback in `.env`: `LLM_FALLBACK_ON_RATE_LIMIT=true`.

---

## 4. Search & Research Issues

### Symptom: `SearXNG was selected, but SearXNG is unavailable at http://localhost:8080`
- **Cause**: `SEARCH_PROVIDER=searxng` is set, but the local SearXNG Docker container is stopped.
- **Fix**: Start SearXNG:
  ```bash
  docker run -d -p 8080:8080 searxng/searxng
  ```
  Or change to DuckDuckGo in `.env`: `SEARCH_PROVIDER=duckduckgo`.

### Symptom: SearXNG JSON search format error
- **Cause**: SearXNG instance does not have JSON output enabled in `settings.yml`.
- **Fix**: In your SearXNG `settings.yml`, ensure `search.formats: [html, json]` is enabled, or switch `SEARCH_PROVIDER=duckduckgo`.

---

## 5. PDF & Playwright Rendering Issues

### Symptom: `Executable doesn't exist at C:\Users\...\AppData\Local\ms-playwright\chromium-...`
- **Cause**: Playwright Chromium browser binaries have not been downloaded.
- **Fix**: Run:
  ```bash
  playwright install chromium
  ```

### Symptom: Linux Headless Server Shared Library Errors
- **Cause**: Linux distribution is missing required graphics and font rendering libraries.
- **Fix**: Run:
  ```bash
  playwright install-deps chromium
  ```

### Symptom: PDF Output Missing or Skipped
- **Cause**: The `--no-pdf` flag was passed during generation.
- **Fix**: Remove `--no-pdf` from your CLI command.

---

## 6. Interrupted Generations

### Symptom: Generation halted mid-book due to power loss or network timeout
- **Cause**: Unfinished generation process.
- **Fix**: Add the `--resume` flag to your command with the same `--output-dir`. VasukiSquare will reload completed checkpoints and finish remaining pages:
  ```bash
  vasukisquare --topic "Your Topic" --output-dir "./output" --resume
  ```

