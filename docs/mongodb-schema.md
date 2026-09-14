# MongoDB Persistence & Document Schema

VasukiSquare includes an optional persistence layer for storing books, individual pages, and cover artwork in MongoDB as a navigable linked document graph.

> [!NOTE]
> **MongoDB is 100% Optional**:
> VasukiSquare saves all generated HTML, PDF, manifest, and checkpoint files directly to your output directory. If MongoDB is not running, or if you pass the `--no-db` CLI flag, the generation pipeline catches connection errors non-blockingly and completes PDF export without interruption.

---

## 1. Enabling MongoDB Persistence

To enable MongoDB storage:
1. Ensure a MongoDB instance is running locally or provide a connection URI in `.env`:
   ```env
   MONGODB_URI=mongodb://localhost:27017
   MONGODB_DATABASE=vasukisquare
   ```
2. Run your generation command without `--no-db`:
   ```bash
   vasukisquare --topic "Cloud Architecture Patterns"
   ```

---

## 2. Collections & Document Schemas

VasukiSquare organizes persistence across three collections:
1. `books`
2. `pages`
3. `covers`

Together, these collections form a navigable doubly-linked list of pages connected to root book and cover records.

### `books` Collection

Represents the root publication record.

```json
{
  "_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Modern Distributed Systems",
  "subtitle": "Consensus, Raft, and Gossip Protocols",
  "running_title": "Modern Distributed Systems",
  "prompt": "Modern Distributed Systems: Consensus, Raft, and Gossip Protocols",
  "description": "An in-depth technical exploration of consensus and distributed algorithms.",
  "status": "draft",
  "chapter_count": 4,
  "page_count": 32,
  "starting_page_id": "page-uuid-001",
  "cover_id": "cover-uuid-001",
  "chapters": [
    {
      "chapter_number": 1,
      "title": "Foundations of Consensus",
      "summary": "Core definitions and historical context.",
      "icon": "layers",
      "page_count": 8
    }
  ],
  "created_at": "2026-09-15T12:00:00Z",
  "updated_at": "2026-09-15T12:00:00Z"
}
```

### `pages` Collection

Represents individual A4 pages stored as independent documents forming a doubly-linked list.

```json
{
  "_id": "page-uuid-002",
  "book_id": "550e8400-e29b-41d4-a716-446655440000",
  "page_number": 2,
  "page_type": "chapter_opener",
  "chapter_number": 1,
  "chapter_title": "Foundations of Consensus",
  "theme": "dark",
  "layout": "chapter_opener",
  "previous_page_id": "page-uuid-001",
  "next_page_id": "page-uuid-003",
  "icon": "layers",
  "content": {
    "headline": "Foundations of Consensus",
    "blocks": []
  },
  "style": {
    "theme": "dark",
    "background_color": "#001e2b",
    "text_color": "#ffffff",
    "accent_color": "#00ed64",
    "opener_template": "minimal_centered"
  },
  "html": "<div class=\"page theme-dark layout-chapter_opener\">...</div>"
}
```

### `covers` Collection

Represents high-resolution cover artwork and style parameters.

```json
{
  "_id": "cover-uuid-001",
  "book_id": "550e8400-e29b-41d4-a716-446655440000",
  "width": 1600,
  "height": 2560,
  "title": "Modern Distributed Systems",
  "design": {
    "subtitle": "Consensus, Raft, and Gossip Protocols",
    "cover_style": "editorial_minimal",
    "accent_color": "#00ed64",
    "background_color": "#faf8f5"
  },
  "html": "<div class=\"cover-container\">...</div>",
  "created_at": "2026-09-15T12:00:00Z"
}
```

---

## 3. Database Indexes

When initialized via `DatabaseManager.init_all_indexes()`, the following indexes are created:

| Collection | Key(s) | Unique? | Purpose |
|---|---|---|---|
| `pages` | `{ "book_id": 1, "page_number": 1 }` | `unique: true` | Prevents duplicate page numbering within a book |
| `pages` | `{ "book_id": 1 }` | `unique: false` | Fast querying of all pages belonging to a specific book |
| `covers` | `{ "book_id": 1 }` | `unique: true` | Enforces 1-to-1 relationship between book and cover |

---

## 4. Linked Graph Traversal Invariants

```
Book [ starting_page_id: Page 1, cover_id: Cover ]
  │
  ├───► Cover [ book_id: Book ]
  │
  └───► Page 1 (prev: null, next: Page 2)
          ▲ │
          │ ▼
        Page 2 (prev: Page 1, next: Page 3)
          ▲ │
          │ ▼
        ...
          ▲ │
          │ ▼
        Page N (prev: Page N-1, next: null)
```

1. `page[0].previous_page_id == null`
2. `page[-1].next_page_id == null`
3. For every page `i` where `0 < i < N-1`:
   - `page[i].previous_page_id == page[i-1].id`
   - `page[i].next_page_id == page[i+1].id`
4. `book.starting_page_id == page[0].id`
5. `cover.book_id == book.id`
