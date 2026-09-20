# Research & Fact Retrieval Pipeline

VasukiSquare grounds every generated ebook in verified facts, official specifications, and reputable domain sources.

---

## 1. Research Lifecycle Overview

```
1. Multi-Perspective Query Planning (ResearchPlanner)
       │
       ▼
2. Multi-Provider Search Execution (WebSearchTool & Wikipedia)
       │
       ▼
3. Normalization, Deduplication & Filtering (deduplication.py)
       │
       ▼
4. Domain Authority Scoring & Ranking (ranking.py)
       │
       ▼
5. Webpage Text Extraction & Synthesis (fetcher.py & service.py)
       │
       ▼
6. Chapter Research Bundling (extract_chapter_research)
```

---

## 2. Multi-Perspective Query Expansion

Rather than relying on a single vague search string, the `ResearchPlanner` decomposes the book topic and intent into targeted search perspectives:

- **Foundations & Architecture**: Core terminology, internal mechanics, and design philosophy.
- **Official Specifications**: Language manuals, RFCs, PEPs, standards documents, and API signatures.
- **Real-World Patterns**: Production use cases, industry case studies, and deployment strategies.
- **Pitfalls & Tradeoffs**: Common failure modes, anti-patterns, and concurrency/security traps.
- **Modern State of the Art**: Recent version features (e.g. Python 3.12/3.13, latest framework updates).

---

## 3. Source Quality, Hierarchy & Domain Authority

VasukiSquare implements a strict domain scoring model (`src/vasukisquare/research/ranking.py`) to categorize and prioritize sources:

### Tier 1: Primary & Official Documentation (Score: 0.90 – 1.0)
- Official language sites (`docs.python.org`, `go.dev`, `rust-lang.org`, `nodejs.org`, `ecma-international.org`)
- Official framework/database documentation (`postgresql.org`, `redis.io`, `mongodb.com`, `kubernetes.io`, `fastapi.tiangolo.com`)
- Standards organizations and PEPs (`w3.org`, `ietf.org`, `peps.python.org`, `rfc-editor.org`)
- Authoritative reference networks (`developer.mozilla.org`, `learn.microsoft.com`)

### Tier 2: Reputable Secondary & Educational Sources (Score: 0.70 – 0.89)
- High-quality technical publications (`realpython.com`, `martinfowler.com`, `highscalability.com`, `kdnuggets.com`)
- Wikipedia technical overview articles (`en.wikipedia.org` for foundational context and terminology)
- Verified engineering blogs and case studies

### Tier 3: General Web & Tertiary Sources (Score: 0.50 – 0.69)
- Community tutorials, blog posts, and forum summaries.

### Disqualified / Rejected Sources (Filtered Out)
- Low-quality content farms, spam redirects, expired domains, and paywalled link farms are rejected during deduplication and ranking.

---

## 4. URL Normalization & Deduplication

The deduplication engine (`src/vasukisquare/research/deduplication.py`):
1. **Normalizes URLs**: Strips tracking parameters (`utm_*`, `ref`, `fbclid`), normalizes protocols to HTTPS, removes trailing slashes, and downcases hostnames.
2. **Per-Domain Capping**: Enforces `RESEARCH_MAX_PAGES_PER_SOURCE` (default: 5) to prevent a single domain from monopolizing the research corpus.
3. **Corpus Budgeting**: Ingests up to `RESEARCH_MAX_SOURCES` (default: 30) ranked documents.

---

## 5. Bibliography & Citation Generation

During Stage 5, cited references from `research.json` are dynamically populated onto the book's **References & Authoritative Sources** page (`LayoutType.REFERENCES`).

Every reference entry displays:
- Document Title
- Publisher / Domain Imprint
- Clean Canonical URL
- Source Citation Badge

---

## 6. Automated Book-Idea Research & Lifecycle

VasukiSquare provides an autonomous trending topic research engine (`IdeaResearchService` and `scripts/research_ideas.py`):

1. **Trend Discovery**: Gathers real-time and evergreen market demand signals across tech, leadership, and lifestyle domains.
2. **Catalog Deduplication**: Compares candidate ideas against existing books and historical ideas stored in MongoDB across 4 levels:
   - Normalized exact title match
   - Normalized topic match
   - Token & 2-gram/3-gram shingle Jaccard overlap
   - Semantic angle differentiation (allowing genuinely distinct angles on broad subjects)
3. **Intentional Page Count Selection**: Strict 40–100 page budget mapped to subject complexity (40–50 beginner, 50–70 practical, 70–85 technical deep dive, 85–100 comprehensive).
4. **Production Prompt Synthesis**: Constructs full editorial briefs defining scope, audience, exclusions, structure, and factual standards.
5. **MongoDB Persistence & JSON Export**: Stores accepted ideas in `book_ideas` with status `ready` and supports `--export-json` for offline inspection.

### Running Idea Research
```bash
# Research 5 ready ideas and save to MongoDB
python scripts/research_ideas.py --count 5

# Dry-run research with custom score threshold and JSON export
python scripts/research_ideas.py --count 3 --min-score 0.75 --dry-run --export-json artifacts/ideas.json
```
