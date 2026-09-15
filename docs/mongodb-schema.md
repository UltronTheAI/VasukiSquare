# MongoDB Persistence & Publishing Architecture

VasukiSquare implements an enterprise-grade, production-ready MongoDB persistence layer. MongoDB serves as the **canonical publication data store**, allowing any external consumer (such as a separate Next.js web application) to ingest, render, index, and distribute books without ever parsing, uploading, or depending on the compiled PDF.

> [!NOTE]
> **MongoDB is Optional for Local Generation**:
> VasukiSquare saves all generated HTML, PDF, manifest, and checkpoint files directly to your local output directory. If MongoDB is not configured or if you supply the `--no-db` CLI flag, the pipeline logs an informational notice and completes PDF compilation without interruption.

---

## 1. Headless Publishing Architecture

In VasukiSquare's publishing architecture:
- **MongoDB is Canonical**: All book metadata, structured JSON content blocks, styling tokens, chapter hierarchies, and cover art exist as typed documents in MongoDB.
- **Pre-rendered HTML is Cached**: Every page document stores canonical pre-rendered HTML (`page.html`) for ultra-fast server-side rendering (SSR), alongside structured JSON (`page.content`) for custom client components.
- **PDF is an Export Artifact**: Physical A4 PDF files (`book.pdf`) are exported print artifacts generated in Stage 6, while Stage 7 publishes the final repaired pages, cover, and status to MongoDB.
- **Next.js Consumes Directly**: An external Next.js website queries MongoDB collections directly for homepage curation, dynamic reader views, search indexing, sitemap generation, and native ad placement.

```
VasukiSquare Pipeline
  │
  ├── Stage 6: HTML Rendering, Dynamic Pagination, Preflight Audit, PDF Export
  │
  └── Stage 7: Canonical Database Persistence
                 │
                 ├── books   (Metadata, Slugs, Discovery, Featured Slots 1..5)
                 ├── pages   (Doubly-Linked Graph, Structured JSON, Cached HTML)
                 ├── covers  (1600x2560 Artwork, Layout Parameters, High-Res HTML)
                 └── ads     (Native Placements, Strict URLs, Weighted Priority)
                                  ▲
                                  │ Direct Queries (No PDF Dependency)
                             Next.js Website
```

---

## 2. Schema Versioning & Engine Tracking

All documents in `books`, `pages`, and `covers` track engine and schema versions for zero-downtime migrations:

- `CURRENT_SCHEMA_VERSION = 1`
- `CURRENT_RENDERER_VERSION = "0.1.0"`

When schemas evolve or renderers update, future consumers can identify legacy documents and run automated migrations.

---

## 3. Collections & Document Schemas

VasukiSquare manages four collections:
1. `books`: Root publication documents, slugs, discovery metadata, SEO, and statistics.
2. `pages`: Physical A4 pages arranged as a navigable doubly-linked list.
3. `covers`: High-resolution 1600 × 2560 source cover artwork and design parameters.
4. `ads`: Native advertisement inventory with weighted priority selection and click tracking.

---

### 3.1 `books` Collection

Represents the root publication record.

```json
{
  "_id": "550e8400-e29b-41d4-a716-446655440000",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "slug": "high-performance-distributed-systems",
  "title": "High-Performance Distributed Systems",
  "subtitle": "Architecture, Consensus, and Resilient Storage",
  "running_title": "High-Performance Distributed Systems",
  "prompt": "Building High-Performance Distributed Systems in Rust",
  "description": "An exhaustive guide to consensus protocols, Raft invariants, and LSM storage.",
  "status": "published",
  "visibility": "public",
  "publication": {
    "author_name": "Vasuki",
    "publisher_name": "Vasuki Publishing",
    "edition_name": "FIRST EDITION",
    "edition_year": 2026,
    "language": "English"
  },
  "featured": {
    "is_featured": true,
    "position": 1,
    "featured_at": "2026-09-15T12:00:00Z"
  },
  "discovery": {
    "primary_category": "Distributed Systems",
    "subcategories": ["Consensus", "Storage Engines", "Rust"],
    "tags": ["raft", "consensus", "storage", "performance"],
    "keywords": ["distributed systems", "raft algorithm", "lsm trees"],
    "reading_time_minutes": 45,
    "target_audience": "Systems Engineers",
    "difficulty_level": "advanced",
    "search_title": "high performance distributed systems architecture consensus"
  },
  "seo": {
    "meta_title": "High-Performance Distributed Systems | VasukiSquare",
    "meta_description": "An exhaustive guide to consensus protocols, Raft invariants, and LSM storage.",
    "canonical_slug": "high-performance-distributed-systems",
    "og_image_url": "https://vasukisquare.cc/covers/high-performance-distributed-systems.png"
  },
  "stats": {
    "views": 1420,
    "opens": 385,
    "rating": 4.9,
    "rating_count": 28
  },
  "chapter_count": 4,
  "page_count": 18,
  "starting_page_id": "page-550e8400-0001",
  "cover_id": "cover-550e8400-0001",
  "chapters": [
    {
      "chapter_number": 1,
      "title": "Foundations of Consensus",
      "summary": "Core definitions, Paxos dilemmas, and Raft consensus invariants.",
      "icon": "layers",
      "page_count": 6
    }
  ],
  "schema_version": 1,
  "renderer_version": "0.1.0",
  "created_at": "2026-09-15T11:45:00Z",
  "updated_at": "2026-09-15T12:00:00Z",
  "published_at": "2026-09-15T12:00:00Z"
}
```

#### Field Specifications:
- `slug` (`str`): Unique, URL-safe slug. Deterministically generated with automatic collision suffixes (`-2`, `-3`).
- `status` (`str`): Publication lifecycle: `"draft"`, `"published"`, `"archived"`. Defaults to `"draft"` during generation and transitions to `"published"` upon successful completion.
- `visibility` (`str`): Access control: `"public"`, `"unlisted"`, `"private"`. Only `"public"` books appear in search and discovery feeds.
- `featured.position` (`int | null`): Pinned homepage position strictly restricted to `1`, `2`, `3`, `4`, or `5`. Only published public books can be featured.
- `stats.views` & `stats.opens` (`int`): Atomic counters updated via MongoDB `$inc`.

---

### 3.2 `pages` Collection

Stores individual physical A4 pages as independent documents linked in graph order.

```json
{
  "_id": "page-550e8400-0004",
  "id": "page-550e8400-0004",
  "book_id": "550e8400-e29b-41d4-a716-446655440000",
  "page_number": 4,
  "page_type": "content",
  "chapter_number": 1,
  "chapter_title": "Foundations of Consensus",
  "theme": "dark",
  "layout": "single_column_split",
  "previous_page_id": "page-550e8400-0003",
  "next_page_id": "page-550e8400-0005",
  "icon": "shield-check",
  "content": {
    "headline": "Raft Leader Election and Heartbeat Invariants",
    "blocks": [
      {
        "type": "paragraph",
        "text": "In a Raft cluster, a leader maintains its authority through periodic heartbeats..."
      },
      {
        "type": "code_snippet",
        "code": "async fn send_append_entries(...) -> Result<(), RaftError> { ... }",
        "language": "rust",
        "caption": "Listing 1.1: Raft AppendEntries RPC dispatch"
      }
    ]
  },
  "style": {
    "theme": "dark",
    "background_color": "#001e2b",
    "text_color": "#ffffff",
    "accent_color": "#00ed64"
  },
  "html": "<div class=\"page theme-dark layout-content\">...</div>",
  "schema_version": 1,
  "renderer_version": "0.1.0",
  "created_at": "2026-09-15T12:00:00Z",
  "updated_at": "2026-09-15T12:00:00Z"
}
```

#### Page Linked Graph Invariants:
1. `page[0].previous_page_id == null` (First page)
2. `page[-1].next_page_id == null` (Final backmatter page)
3. For every intermediate page `i`:
   - `page[i].previous_page_id == page[i-1].id`
   - `page[i].next_page_id == page[i+1].id`
4. `book.starting_page_id == page[0].id`
5. `book.page_count == len(pages)`

---

### 3.3 `covers` Collection

Stores 1600 × 2560 source canvas cover artwork and style parameters.

```json
{
  "_id": "cover-550e8400-0001",
  "id": "cover-550e8400-0001",
  "book_id": "550e8400-e29b-41d4-a716-446655440000",
  "width": 1600,
  "height": 2560,
  "title": "High-Performance Distributed Systems",
  "subtitle": "Architecture, Consensus, and Resilient Storage",
  "author": "Vasuki",
  "category": "Distributed Systems",
  "layout_style": "geometric_accent",
  "design": {
    "accent_color": "#00ed64",
    "background_color": "#001e2b",
    "hero_icon": "cpu",
    "contrast_ratio": 9.4
  },
  "html": "<div class=\"cover-container\" style=\"width:1600px; height:2560px;\">...</div>",
  "image_path": "output/distributed-systems/cover.png",
  "image_base64": null,
  "schema_version": 1,
  "renderer_version": "0.1.0",
  "created_at": "2026-09-15T12:00:00Z",
  "updated_at": "2026-09-15T12:00:00Z"
}
```

---

### 3.4 `ads` Collection

Stores native advertisements served to external web readers.

```json
{
  "_id": "ad-infra-cloud-001",
  "id": "ad-infra-cloud-001",
  "title": "Scalable Cloud Hosting Built for AI",
  "description": "Deploy low-latency GPU and database clusters in seconds.",
  "cta_text": "Start Free Trial",
  "destination_url": "https://cloud.example.com/vasuki-special",
  "image_url": "https://cdn.example.com/creatives/cloud_banner_1200x628.png",
  "placement": "book_reader_sidebar",
  "status": "active",
  "priority": "high",
  "start_date": "2026-01-01T00:00:00Z",
  "end_date": "2026-12-31T23:59:59Z",
  "stats": {
    "impressions": 58200,
    "clicks": 1840
  },
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-09-15T12:00:00Z"
}
```

#### Ad Security & Validation Rules:
- `destination_url` and `image_url` strictly require standard HTTP/HTTPS schemes (`^https?://`).
- Embedded HTML, script tags, and javascript schemes (`javascript:`) are rejected.
- Priority levels: `"high"` (weight 10), `"medium"` (weight 5), `"low"` (weight 2).

---

## 4. Deterministic Slug Collision Handling

VasukiSquare guarantees URL safety and idempotency through deterministic slug resolution:
1. Generates URL-safe base slug from book title using `slugify` (e.g. `"Distributed Systems"` -> `"distributed-systems"`).
2. Inspects database for collisions matching `^{slug}(?:-([0-9]+))?$`.
3. If collision occurs, assigns the lowest available integer suffix:
   - 1st collision: `distributed-systems-2`
   - 2nd collision: `distributed-systems-3`
4. When updating an existing book, the book's current ID is excluded so updating metadata never increments its own slug.

---

## 5. Homepage Featured Books Management

The homepage features up to 5 pinned publications in positions `1..5`.

### Invariants:
- Only books with `status == "published"` and `visibility == "public"` can be pinned.
- Positions are strictly constrained to `1`, `2`, `3`, `4`, or `5`.
- **Automatic Displacment**: If book A is assigned position 1 while book B currently occupies position 1, book B is automatically unpinned (`position = null, is_featured = false`).
- **Atomic Pinning (`pin_book(book_id, position)`)**: Updates target book and clears old occupant in an atomic sequence.
- **Unpinning (`unpin_book(book_id)`)**: Clears `is_featured`, `position`, and `featured_at`.
- **Querying (`get_featured_books()`)**: Returns books sorted by `featured.position ASC`.

---

## 6. Database Indexes

When initialized via `DatabaseManager.init_all_indexes()`, the following optimized indexes are created:

### `books` Indexes
| Index Name | Keys | Type / Constraint | Purpose |
|---|---|---|---|
| `books_slug_idx` | `{"slug": 1}` | **Unique** | Canonical Next.js routing by book slug |
| `books_public_feed` | `{"status": 1, "visibility": 1, "created_at": -1}` | Compound | Discovery catalog and recent book queries |
| `books_featured_idx` | `{"featured.is_featured": 1, "featured.position": 1}` | Compound Sparse | High-speed homepage featured carousel |
| `books_text_search` | `discovery.search_title`, `title`, `description`, `discovery.keywords` | Text Index | Full-text keyword and topic search |

### `pages` Indexes
| Index Name | Keys | Type / Constraint | Purpose |
|---|---|---|---|
| `pages_book_num_unique` | `{"book_id": 1, "page_number": 1}` | **Unique** | Enforces sequential page order per book |
| `pages_book_id_idx` | `{"book_id": 1}` | Single Field | Bulk retrieval of all pages for a book |

### `covers` Indexes
| Index Name | Keys | Type / Constraint | Purpose |
|---|---|---|---|
| `covers_book_id_unique` | `{"book_id": 1}` | **Unique** | Strict 1-to-1 relationship between book and cover |

### `ads` Indexes
| Index Name | Keys | Type / Constraint | Purpose |
|---|---|---|---|
| `ads_active_placement_idx` | `{"status": 1, "placement": 1, "start_date": 1, "end_date": 1}` | Compound | High-performance active ad query filtering |

---

## 7. Atomic Counters & Interaction Tracking

External websites track reader interactions directly using atomic MongoDB `$inc` updates without read-modify-write races:

| Method | Target | Operation | Description |
|---|---|---|---|
| `BookRepository.increment_views(book_id)` | `books` | `{"$inc": {"stats.views": 1}}` | Increments book overview/catalog impressions |
| `BookRepository.increment_opens(book_id)` | `books` | `{"$inc": {"stats.opens": 1}}` | Increments reading session starts |
| `AdRepository.increment_impressions(ad_id)` | `ads` | `{"$inc": {"stats.impressions": 1}}` | Tracks ad rendering in reader viewport |
| `AdRepository.increment_clicks(ad_id)` | `ads` | `{"$inc": {"stats.clicks": 1}}` | Tracks reader clicks on CTA button |

---

## 8. Cascading Deletion & Rollback Semantics

To maintain linked graph integrity across collections:

### Cascading Deletion (`BookRepository.delete_cascade(book_id)`)
When a publication is removed:
1. Deletes all associated pages in `pages` (`delete_many({"book_id": book_id})`).
2. Deletes associated cover in `covers` (`delete_one({"book_id": book_id})`).
3. Deletes root book in `books` (`delete_one({"_id": book_id})`).
4. **Leaves `ads` completely untouched** (advertisement inventory and advertiser billing history are never altered).

### Batch Rollback Safety (`PageRepository.create_many(pages)`)
If page insertion fails mid-batch, any inserted pages for the `book_id` are purged immediately to prevent corrupt, disconnected page fragments.

---

## 9. Next.js Integration Guidelines

Next.js Server Components and Route Handlers can directly query MongoDB without any intermediary API layer:

### Reading Homepage Featured Books (Server Component)
```typescript
// app/page.tsx
import { MongoClient } from 'mongodb';

export async function getFeaturedBooks() {
  const client = await clientPromise;
  const db = client.db(process.env.MONGODB_DATABASE);
  
  return db.collection('books')
    .find({
      status: 'published',
      visibility: 'public',
      'featured.is_featured': true
    })
    .sort({ 'featured.position': 1 })
    .limit(5)
    .toArray();
}
```

### Reading a Book Page by Slug & Page Number
```typescript
// app/books/[slug]/page/[pageNum]/page.tsx
export async function getBookPage(slug: string, pageNum: number) {
  const client = await clientPromise;
  const db = client.db(process.env.MONGODB_DATABASE);

  const book = await db.collection('books').findOne({ slug });
  if (!book) return null;

  const page = await db.collection('pages').findOne({
    book_id: book._id,
    page_number: pageNum
  });

  return { book, page };
}
```

### Serving Native Ads with Weighted Priority
```typescript
// lib/ads.ts
export async function getWeightedAd(placement: string) {
  const client = await clientPromise;
  const db = client.db(process.env.MONGODB_DATABASE);
  const now = new Date();

  const candidates = await db.collection('ads').find({
    status: 'active',
    placement,
    $or: [{ start_date: null }, { start_date: { $lte: now } }],
    $or: [{ end_date: null }, { end_date: { $gte: now } }]
  }).toArray();

  if (!candidates.length) return null;

  const weights: Record<string, number> = { high: 10, medium: 5, low: 2 };
  const totalWeight = candidates.reduce((sum, ad) => sum + (weights[ad.priority] || 5), 0);
  let threshold = Math.random() * totalWeight;

  for (const ad of candidates) {
    threshold -= (weights[ad.priority] || 5);
    if (threshold <= 0) return ad;
  }
  return candidates[0];
}
```

---

## 10. Verification & Test Suite

The database persistence layer is verified through automated test suites covering all 30 production scenarios in `tests/integration/test_database.py`:
- Schema versioning and renderer tags
- Deterministic slug collision resolution
- Pinned book bounds (1..5) and conflict reassignment
- Pagination with `PaginatedResult`
- Text search and category filtering
- Weighted ad selection and URL sanitization
- Cascading deletion integrity
- Atomic counter increments
