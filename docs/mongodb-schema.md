# VasukiSquare MongoDB Schema Specification

VasukiSquare persists ebooks across exactly three collections in MongoDB:
1. `books`
2. `pages`
3. `covers`

Together, these collections form a navigable linked document graph allowing forward and backward page traversal and end-to-end book tracing.

---

## 1. Collections & Document Schemas

### `books` Collection

Represents the root book document.

```json
{
  "_id": "uuid-string",
  "slug": "introduction-to-modern-ai",
  "title": "Introduction to Modern AI",
  "subtitle": "Architecture and Practical Applications",
  "prompt": "Write a complete guide on modern AI architectures...",
  "description": "An exhaustive technical breakdown of transformers and agentic systems.",
  "status": "draft",
  "chapter_count": 5,
  "page_count": 60,
  "starting_page_id": "page-uuid-1",
  "cover_id": "cover-uuid-1",
  "chapters": [
    {
      "chapter_number": 1,
      "title": "The Genesis of Neural Networks",
      "summary": "Historical perspective and foundation.",
      "icon": "sparkles",
      "page_count": 12,
      "theme": "dark"
    }
  ],
  "created_at": "2026-09-11T12:00:00Z",
  "updated_at": "2026-09-11T12:00:00Z"
}
```

### `pages` Collection

Represents individual A4 pages. Every page exists as an independent document forming a doubly-linked list.

```json
{
  "_id": "page-uuid-2",
  "book_id": "uuid-string",
  "page_number": 2,
  "page_type": "chapter_opener",
  "chapter_number": 1,
  "chapter_name": "The Genesis of Neural Networks",
  "theme": "dark",
  "layout": "chapter_opener",
  "previous_page_id": "page-uuid-1",
  "next_page_id": "page-uuid-3",
  "icon": "sparkles",
  "content": {
    "headline": "The Genesis of Neural Networks",
    "body": null,
    "key_points": [],
    "code_snippets": [],
    "callouts": [],
    "metadata": {}
  },
  "style": {
    "theme": "dark",
    "font_family": "Euclid Circular A",
    "accent_color": "#00ed64",
    "layout_variant": null,
    "custom_css": null
  },
  "sources": [
    {
      "url": "https://arxiv.org/abs/1706.03762",
      "title": "Attention Is All You Need",
      "claim": "Transformers introduce self-attention mechanisms.",
      "quote": "We propose the Transformer, a model architecture...",
      "page_number": 1
    }
  ],
  "html": "<div class=\"page theme-dark layout-chapter_opener\">...</div>",
  "validation": {
    "overflow_detected": false,
    "citations_valid": true
  }
}
```

### `covers` Collection

Represents the book's high-resolution cover artwork and layout.

```json
{
  "_id": "cover-uuid-1",
  "book_id": "uuid-string",
  "width": 1600,
  "height": 2560,
  "title": "Introduction to Modern AI",
  "design": {
    "subtitle": "Architecture and Practical Applications",
    "palette": "brand-dark",
    "hero_icon": "sparkles"
  },
  "html": "<div class=\"cover-wrapper\">...</div>",
  "image_path": "output/covers/cover-uuid-1.png",
  "created_at": "2026-09-11T12:00:00Z"
}
```

---

## 2. MongoDB Indexes

The following indexes guarantee unique constraints, relationship integrity, and fast lookup performance:

| Collection | Key(s) | Options | Purpose |
|---|---|---|---|
| `books` | `{ "slug": 1 }` | `unique: true` | Enforce human-readable unique URL slugs |
| `pages` | `{ "book_id": 1, "page_number": 1 }` | `unique: true` | Prevent duplicate page numbering within any book |
| `pages` | `{ "book_id": 1 }` | `unique: false` | Fast lookup of all pages belonging to a book |
| `covers` | `{ "book_id": 1 }` | `unique: true` | Enforce 1-to-1 relationship between book and cover |

---

## 3. Linked Graph & Page Navigation

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

### Linking Invariants
1. `page 1.previous_page_id == null`
2. `page N.next_page_id == null`
3. For every page `i` where `1 < i < N`:
   - `page[i].previous_page_id == page[i-1]._id`
   - `page[i].next_page_id == page[i+1]._id`
4. `book.starting_page_id == page 1._id`
5. `cover.book_id == book._id`

