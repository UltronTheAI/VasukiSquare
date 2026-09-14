# Configuration Guide

VasukiSquare provides a dual-layer configuration architecture:
1. **Environment Configuration (`.env` / `.env.local` / OS Environment Variables)**: Manages infrastructure settings, API keys, endpoints, model pools, search backends, and performance limits.
2. **Publication & Branding Configuration (`config.json`)**: Manages public author names, publisher imprints, corporate entity metadata, copyright notices, and language defaults.

---

## 1. Configuration Precedence

When multiple configuration sources exist, settings are resolved in the following order of precedence (highest to lowest):

```
1. Explicit CLI Arguments (--llm-provider, --ollama-model, --output-dir, etc.)
       ▲
2. OS Environment Variables / .env.local / .env
       ▲
3. config.json (Publication and Branding metadata)
       ▲
4. Built-in Code Defaults
```

---

## 2. Environment Variables (`.env`)

VasukiSquare uses Pydantic Settings to validate environment settings.

### Complete Environment Variables Reference

| Variable Name | Type | Required? | Default | Description | Example |
|---|---|---|---|---|---|
| `APP_ENV` | `str` | Optional | `development` | Runtime environment (`development`, `production`, `test`) | `APP_ENV=production` |
| `LOG_LEVEL` | `str` | Optional | `INFO` | Console logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `LOG_LEVEL=INFO` |
| `VASUKISQUARE_MOCK_MODE` | `bool` | Optional | `false` | Enable deterministic offline mock execution without live APIs | `VASUKISQUARE_MOCK_MODE=false` |
| `LLM_PROVIDER` | `str` | Optional | `auto` | Active provider (`auto`, `groq`, `ollama`) | `LLM_PROVIDER=auto` |
| `LLM_TEMPERATURE` | `float` | Optional | `0.25` | Generation sampling temperature (0.0 to 1.0) | `LLM_TEMPERATURE=0.25` |
| `LLM_FALLBACK_ON_RATE_LIMIT` | `bool` | Optional | `false` | Fall back to Ollama if entire Groq pool is rate-limited | `LLM_FALLBACK_ON_RATE_LIMIT=true` |
| `SMALL_MODEL_MODE` | `str` | Optional | `auto` | Optimize prompts for small (<7B) local models (`auto`, `true`, `false`) | `SMALL_MODEL_MODE=auto` |
| `GROQ_API_KEY` | `str` | Conditional | `None` | Groq API Key (single key or comma-separated list of keys) | `GROQ_API_KEY=gsk_key1,gsk_key2` |
| `GROQ_KEY_STRATEGY` | `str` | Optional | `preferred` | Groq key rotation strategy (`preferred`, `round_robin`, `rotate`) | `GROQ_KEY_STRATEGY=preferred` |
| `GROQ_KEY_COOLDOWN_SECONDS` | `float` | Optional | `60.0` | Cooldown duration for a rate-limited API key | `GROQ_KEY_COOLDOWN_SECONDS=60.0` |
| `GROQ_MODEL` | `str` | Optional | `openai/gpt-oss-120b` | Default primary Groq model name | `GROQ_MODEL=openai/gpt-oss-120b` |
| `GROQ_MODELS` | `str` | Optional | `None` | Comma-separated pool of Groq models for automatic failover | `GROQ_MODELS=openai/gpt-oss-120b,llama-3.3-70b-versatile,llama-3.1-8b-instant` |
| `GROQ_MODEL_STRATEGY` | `str` | Optional | `ordered` | Model pool selection strategy (`ordered`, `random`, `rotate`) | `GROQ_MODEL_STRATEGY=ordered` |
| `GROQ_MODEL_FALLBACK` | `bool` | Optional | `true` | Enable automatic failover across models in pool on error | `GROQ_MODEL_FALLBACK=true` |
| `GROQ_RETRIES_PER_MODEL` | `int` | Optional | `1` | Retries per model before failing over to next model | `GROQ_RETRIES_PER_MODEL=1` |
| `GROQ_MAX_MODEL_ATTEMPTS` | `int` | Optional | `0` | Max candidate models to attempt per request (`0` = all) | `GROQ_MAX_MODEL_ATTEMPTS=0` |
| `GROQ_MODEL_COOLDOWN_SECONDS` | `float` | Optional | `60.0` | Cooldown duration for a failed or rate-limited model | `GROQ_MODEL_COOLDOWN_SECONDS=60.0` |
| `GROQ_WAIT_FOR_RATE_LIMIT` | `bool` | Optional | `true` | Smart wait when all candidates are temporarily rate-limited | `GROQ_WAIT_FOR_RATE_LIMIT=true` |
| `GROQ_MAX_RATE_LIMIT_WAIT_SECONDS` | `float` | Optional | `60.0` | Max seconds to wait for a rate-limited model/key | `GROQ_MAX_RATE_LIMIT_WAIT_SECONDS=60.0` |
| `GROQ_RATE_LIMIT_BUFFER_SECONDS` | `float` | Optional | `1.0` | Safety buffer added to retry-after wait duration | `GROQ_RATE_LIMIT_BUFFER_SECONDS=1.0` |
| `GROQ_MODELS_WRITING` | `str` | Optional | `None` | Task-specific model pool for page writing stage | `GROQ_MODELS_WRITING=openai/gpt-oss-120b` |
| `GROQ_MODELS_RESEARCH` | `str` | Optional | `None` | Task-specific model pool for research stage | `GROQ_MODELS_RESEARCH=llama-3.3-70b-versatile` |
| `GROQ_MODELS_PLANNING` | `str` | Optional | `None` | Task-specific model pool for editorial planning stage | `GROQ_MODELS_PLANNING=openai/gpt-oss-120b` |
| `OLLAMA_BASE_URL` | `str` | Optional | `http://localhost:11434` | Ollama local API base URL | `OLLAMA_BASE_URL=http://localhost:11434` |
| `OLLAMA_MODEL` | `str` | Optional | `qwen2.5:7b-instruct` | Ollama model name | `OLLAMA_MODEL=qwen2.5:7b-instruct` |
| `OLLAMA_NUM_CTX` | `int` | Optional | `8192` | Ollama context window size | `OLLAMA_NUM_CTX=8192` |
| `SEARCH_PROVIDER` | `str` | Optional | `auto` | Active search backend (`auto`, `duckduckgo`, `searxng`, `tavily`, `serper`, `brave`, `mock`) | `SEARCH_PROVIDER=auto` |
| `SEARXNG_URL` | `str` | Optional | `http://localhost:8080` | Local SearXNG instance endpoint | `SEARXNG_URL=http://localhost:8080` |
| `SEARXNG_ENABLED` | `bool` | Optional | `true` | Whether SearXNG is enabled | `SEARXNG_ENABLED=true` |
| `SEARXNG_TIMEOUT` | `float` | Optional | `20.0` | SearXNG query timeout in seconds | `SEARXNG_TIMEOUT=20.0` |
| `SEARXNG_MAX_RESULTS` | `int` | Optional | `10` | Max search results to fetch per query | `SEARXNG_MAX_RESULTS=10` |
| `TAVILY_API_KEY` | `str` | Optional | `None` | Tavily search API key | `TAVILY_API_KEY=tvly-...` |
| `SERPER_API_KEY` | `str` | Optional | `None` | Serper Google search API key | `SERPER_API_KEY=...` |
| `BRAVE_SEARCH_API_KEY` | `str` | Optional | `None` | Brave Search API key | `BRAVE_SEARCH_API_KEY=...` |
| `RESEARCH_MAX_SOURCES` | `int` | Optional | `30` | Max unique research sources ingested per book | `RESEARCH_MAX_SOURCES=30` |
| `RESEARCH_MAX_PAGES_PER_SOURCE` | `int` | Optional | `5` | Max sub-pages scraped per source domain | `RESEARCH_MAX_PAGES_PER_SOURCE=5` |
| `MIN_RESEARCH_SOURCES` | `int` | Optional | `3` | Minimum sources required for production book | `MIN_RESEARCH_SOURCES=3` |
| `DEFAULT_LANGUAGE` | `str` | Optional | `en` | Default language code for generation | `DEFAULT_LANGUAGE=en` |
| `DEFAULT_TARGET_PAGES` | `int` | Optional | `60` | Default page count if `--pages` omitted | `DEFAULT_TARGET_PAGES=60` |
| `DEFAULT_MAX_CHAPTERS` | `int` | Optional | `12` | Maximum chapters in editorial plan | `DEFAULT_MAX_CHAPTERS=12` |
| `PDF_OUTPUT_DIR` | `str` | Optional | `./output` | Default directory for rendered artifacts | `PDF_OUTPUT_DIR=./output` |
| `TEMP_RENDER_DIR` | `str` | Optional | `./.tmp` | Intermediate render cache directory | `TEMP_RENDER_DIR=./.tmp` |
| `CHROMIUM_HEADLESS` | `bool` | Optional | `true` | Launch Playwright Chromium in headless mode | `CHROMIUM_HEADLESS=true` |
| `COVER_WIDTH` | `int` | Optional | `1600` | Cover artwork source canvas width in pixels | `COVER_WIDTH=1600` |
| `COVER_HEIGHT` | `int` | Optional | `2560` | Cover artwork source canvas height in pixels | `COVER_HEIGHT=2560` |
| `COVER_TEMPERATURE` | `float` | Optional | `0.8` | Sampling temperature for cover creative concepts | `COVER_TEMPERATURE=0.8` |
| `COVER_VARIATION_ENABLED` | `bool` | Optional | `true` | Enable procedural geometric pattern variation | `COVER_VARIATION_ENABLED=true` |
| `COVER_MAX_RETRIES` | `int` | Optional | `1` | Max retries for cover contrast repairs | `COVER_MAX_RETRIES=1` |
| `MONGODB_URI` | `str` | Optional | `mongodb://localhost:27017` | MongoDB connection URI | `MONGODB_URI=mongodb://localhost:27017` |
| `MONGODB_DATABASE` | `str` | Optional | `vasukisquare` | Target MongoDB database name | `MONGODB_DATABASE=vasukisquare` |

---

## 3. Publication & Branding Configuration (`config.json`)

VasukiSquare uses `config.json` at the root of the project to define white-label branding, copyright claims, publisher imprints, and edition metadata.

### Full Schema Reference

```json
{
  "branding": {
    "author_name": "Vasuki",
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

### Field Definitions

| Section | Key | Type | Required? | Default | Description |
|---|---|---|---|---|---|
| `branding` | `author_name` | `str` | **Yes** | `"Vasuki"` | Public author or editorial team identity on covers and imprints |
| `branding` | `publication_name` | `str` | **Yes** | `"Vasuki Publishing"` | Publisher imprint displayed on headers, imprints, and copyright blocks |
| `branding` | `company_name` | `str` | **Yes** | `"VasukiSquare"` | Corporate entity name |
| `branding` | `engine_name` | `str` | **Yes** | `"VasukiSquare AI Publishing Engine"` | Publishing engine acknowledgment text |
| `branding` | `website` | `str` | No | `"https://vasukisquare.cc"` | Publisher URL. Set to `""` to omit website completely without blank lines |
| `edition` | `name` | `str` | **Yes** | `"FIRST EDITION"` | Edition designation (e.g. `FIRST EDITION`, `REVISED EDITION`) |
| `edition` | `year` | `int` | **Yes** | `2026` | 4-digit publication copyright year |
| `copyright` | `holder` | `str` | **Yes** | `"Vasuki Publishing"` | Legal copyright entity name |
| `copyright` | `all_rights_reserved` | `bool` | No | `true` | Append "All rights reserved." to copyright statement |
| `book_defaults` | `language` | `str` | No | `"English"` | Default language for generated content |
