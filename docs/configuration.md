# Configuration Guide

VasukiSquare uses `pydantic-settings` to load and validate configuration from environment variables or a `.env` file.

## Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_ENV` | `str` | `development` | Application runtime environment (`development`, `production`, `test`) |
| `LOG_LEVEL` | `str` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `GROQ_API_KEY` | `str` | None | Single API key or comma-separated list of keys (`"key1,key2,key3"`) for Groq key rotation |
| `GROQ_KEY_STRATEGY` | `str` | `preferred` | Groq API key selection strategy (`preferred`, `round_robin`) |
| `GROQ_KEY_COOLDOWN_SECONDS` | `float` | `60.0` | Cooldown duration for a rate-limited Groq API key |
| `GROQ_MODEL` | `str` | `openai/gpt-oss-120b` | Single default model or fallback model name |
| `GROQ_MODELS` | `str` | None | Comma-separated list of Groq models for automatic failover pool |
| `GROQ_MODEL_STRATEGY` | `str` | `ordered` | Model selection strategy (`ordered`, `random`, `rotate`) |
| `GROQ_MODEL_FALLBACK` | `bool` | `true` | Enable automatic failover between pool models on rate limit/server errors |
| `GROQ_RETRIES_PER_MODEL` | `int` | `1` | Retries on an individual model before failing over |
| `GROQ_MAX_MODEL_ATTEMPTS` | `int` | `0` | Max candidate models to attempt per request (`0` = all) |
| `GROQ_MODEL_COOLDOWN_SECONDS` | `float` | `60.0` | Cooldown duration for a failed model |
| `GROQ_MODELS_WRITING` | `str` | None | Optional task-specific model pool for content writing |
| `GROQ_MODELS_RESEARCH` | `str` | None | Optional task-specific model pool for research curation |
| `GROQ_MODELS_PLANNING` | `str` | None | Optional task-specific model pool for editorial planning |
| `LLM_PROVIDER` | `str` | `auto` | Provider mode (`auto`, `groq`, `ollama`) |
| `LLM_FALLBACK_ON_RATE_LIMIT` | `bool` | `false` | Fall back from Groq to Ollama if entire Groq pool is exhausted |
| `OLLAMA_BASE_URL` | `str` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `str` | `qwen2.5:7b-instruct` | Ollama local model tag |
| `MONGODB_URI` | `str` | `mongodb://localhost:27017` | MongoDB connection URI string |
| `MONGODB_DATABASE` | `str` | `vasukisquare` | Database name for book storage |
| `TAVILY_API_KEY` | `str` | None | Search API key for Tavily |
| `SERPER_API_KEY` | `str` | None | Search API key for Serper (optional) |
| `BRAVE_SEARCH_API_KEY` | `str` | None | Search API key for Brave Search (optional) |
| `RESEARCH_MAX_SOURCES` | `int` | `30` | Maximum distinct sources to ingest per topic |
| `RESEARCH_MAX_PAGES_PER_SOURCE` | `int` | `5` | Maximum pages traversed per domain |
| `DEFAULT_LANGUAGE` | `str` | `en` | Default generation language |
| `DEFAULT_TARGET_PAGES` | `int` | `60` | Target page count for full ebooks |
| `DEFAULT_MAX_CHAPTERS` | `int` | `12` | Maximum chapters allowed in editorial plan |
| `PDF_OUTPUT_DIR` | `str` | `./output` | Target folder for rendered PDF documents |
| `TEMP_RENDER_DIR` | `str` | `./.tmp` | Intermediate folder for HTML snapshots |
| `CHROMIUM_HEADLESS` | `bool` | `true` | Launch Chromium in headless mode for PDF export |
| `COVER_WIDTH` | `int` | `1600` | Cover canvas width in pixels |
| `COVER_HEIGHT` | `int` | `2560` | Cover canvas height in pixels |

## Usage Example

```python
from vasukisquare.config import get_settings

settings = get_settings()
print(f"Connecting to MongoDB at {settings.mongodb_uri}")
```

