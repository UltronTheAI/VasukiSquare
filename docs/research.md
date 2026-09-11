# VasukiSquare Deep-Research Subsystem

The deep-research subsystem gathers, extracts, deduplicates, and ranks technical information from multiple source classes to build a reliable research corpus before editorial planning or page generation begins.

---

## 1. Research Pipeline Overview

```
User Prompt
    │
    ▼
[Research Planner] (Multi-Perspective Query Decomposition via Groq/LangChain)
    │
    ├── Perspective: Foundations & Taxonomy (Wikipedia + Web)
    ├── Perspective: Architecture & Protocols (Official Docs + Academic)
    ├── Perspective: Implementation & Code (Docs + Technical Blogs)
    ├── Perspective: Benchmarks & Trade-offs (Blogs + Benchmarks)
    └── Perspective: Production Case Studies (News + Post-mortems)
    │
    ▼
[Provider Execution] (Concurrent Tool Dispatch)
    ├── WebSearchTool (Pluggable: Mock, Tavily, Serper, Brave)
    ├── WikipediaTool (Orientation and background overview)
    ├── WebpageFetcherTool (HTML clean text extraction)
    ├── DocScraperTool (Official technical docs & specs)
    └── RssNewsTool (Feed and announcements ingestion)
    │
    ▼
[URL Normalization & Deduplication]
    ├── Strip UTM tracking parameters and hash fragments
    ├── Exact URL deduplication
    └── Near-duplicate pruning (Jaccard token/shingle similarity)
    │
    ▼
[Source Authority & Ranking]
    ├── Primary Documentation: 1.0 multiplier
    ├── Academic / Specifications: 0.95 multiplier
    ├── Technical Blogs: 0.75 multiplier
    ├── Wikipedia Orientation: 0.50 multiplier (orientation damping)
    └── Domain Authority Bonus (.edu, .gov, docs.*, github.com, arxiv.org)
    │
    ▼
[ResearchCorpus] (Stored in Application State for Writing & Citation)
```

---

## 2. Unified Document Representation (`SourceDocument`)

Every ingested document conforms to the `SourceDocument` schema:

| Field | Type | Description |
|---|---|---|
| `id` | `str` (UUID) | Unique document identifier |
| `url` | `str` | Normalized clean URL |
| `title` | `str` | Extracted or reported title |
| `publisher` | `str` | Publishing entity or domain |
| `domain` | `str` | Extracted hostname (e.g. `docs.python.org`) |
| `retrieval_timestamp` | `datetime` | UTC timestamp of ingestion |
| `source_type` | `SourceType` | `web`, `wikipedia`, `webpage`, `news`, `documentation`, `blog`, `academic` |
| `extracted_text` | `str` | Clean body text without HTML/scripts |
| `summary` | `str` | Brief excerpt or snippet |
| `reliability_score` | `float` | Calculated quality & authority score (0.0 - 1.0) |
| `metadata` | `dict` | Extra provider headers and IDs |

---

## 3. Pluggable Search Providers

Search tools implement the `SearchProvider` interface, allowing backends to be switched via environment variables without altering agents:

```python
from vasukisquare.tools.search import WebSearchTool, TavilySearchProvider, SerperSearchProvider, MockSearchProvider

# Tavily
provider = TavilySearchProvider(api_key="tvly-...")
# or Serper
provider = SerperSearchProvider(api_key="...")
# or Offline Mock
provider = MockSearchProvider()

search_tool = WebSearchTool(provider=provider)
```

---

## 4. Deduplication & Near-Duplicate Detection

- **URL Normalization**: Lowercases hostnames, strips default ports, trailing slashes, and eliminates tracking query parameters (`utm_source`, `utm_medium`, `fbclid`, etc.).
- **Near-Duplicate Detection**: Evaluates 3-word shingles and word token Jaccard similarity. Documents with similarity $> 80\%$ are pruned, retaining the document with the highest reliability score.

---

## 5. Research Invariants & Citation Rules

1. **No Hallucinated Citations**: Downstream agents can only cite URLs present in the `ResearchCorpus`.
2. **Wikipedia as Orientation**: Wikipedia articles are tagged with `SourceType.WIKIPEDIA` and assigned a damped baseline score (0.50) so primary documentation is favored for technical claims.
3. **Automatic Retries & Timeouts**: All external network calls are wrapped with exponential backoff retries (`tenacity`) and strict timeout bounds.

