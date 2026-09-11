# Configuration Guide

VasukiSquare uses `pydantic-settings` to load and validate configuration from environment variables or a `.env` file.

## Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_ENV` | `str` | `development` | Application runtime environment (`development`, `production`, `test`) |
| `LOG_LEVEL` | `str` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `GROQ_API_KEY` | `str` | None | API key for Groq LLM services |
| `GROQ_MODEL` | `str` | `llama-3.3-70b-versatile` | Model name on Groq |
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

