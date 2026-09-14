# VasukiSquare AI-Directed Cover Design System

The Cover Design System generates custom, subject-aware technical ebook covers while preserving the visual identity and design tokens of `DESIGN.md`.

---

## 1. Source Canvas & Physical A4 Geometry

Covers are designed on a master high-resolution digital artwork canvas:
- **Source Dimensions**: `1600 × 2560 pixels` (`aspect ratio: 1:1.6` / 10:16)
- **Physical Output**: `A4 (210mm × 297mm)` (`aspect ratio: 1:1.414`)
- **Safe Area Invariant**:
  - In the 1600×2560 source canvas, all essential elements (title, subtitle, category badge, central icon, and author credits) are contained within the **A4 Safe Zone** (`top: 200px`, `bottom: 200px`, `left: 180px`, `right: 180px`).
  - When cropped or placed into an A4 page, zero text or iconography is clipped.

```
+------------------------------------+ Y = 0 (1600 x 2560 Canvas)
|       Background SVG Pattern       |
|  +------------------------------+  | Y = 200px (A4 Safe Zone Top)
|  | [CATEGORY BADGE]             |  |
|  |                              |  |
|  |       [HERO LUCIDE ICON]     |  |
|  |                              |  |
|  | [TITLE]                      |  |
|  | [SUBTITLE]                   |  |
|  |                              |  |
|  | [AUTHOR]     [VASUKISQUARE]  |  |
|  +------------------------------+  | Y = 2360px (A4 Safe Zone Bottom)
|       Background SVG Pattern       |
+------------------------------------+ Y = 2560px
```

---

## 2. Geometric Abstract SVG Generators

`CoverPatternGenerator` procedurally synthesizes abstract technical backgrounds using token colors:

1. **`orbital_rings`**: Nested concentric orbital ellipses with dashed node vectors.
2. **`tech_matrix`**: Coordinate grid dots and geometric anchor points for low-level systems and database architectures.
3. **`abstract_mesh`**: Multi-point interconnected polygon meshes for AI, deep learning, and neural networks.
4. **`layered_bands`**: Sweeping parabolic wave contours for cloud infrastructure and networking topics.
5. **`minimal_geometric`**: Precision rotated frames and concentric focal rings.

---

## 3. Design Token & Color Rules

- **Zero Arbitrary Colors**: All accent, secondary, and canvas colors are validated against `ColorToken` (`#00ed64`, `#001e2b`, `#003d4f`, `#7b3ff2`, `#fa6e39`, etc.).
- **No Copyrighted Brand Logos**: Imagery relies strictly on geometric vectors and Lucide icons.
- **Semantic Icon Integration**: Central Lucide SVG icons are styled using design token colors with glowing drop-shadow backplates.

---

## 4. MongoDB Persistence & Book Linking

- Metadata and complete 1600×2560 HTML are persisted in MongoDB's `covers` collection.
- `Book.cover_id` is updated in the `books` collection to establish 1-to-1 traceability.
- Optional rasterization saves high-resolution PNGs at `output/covers/{cover_id}.png` via Playwright Chromium.

---

## 5. Automatic Contrast-Aware Typography & WCAG Validation

Every cover text color is automatically derived from the actual cover background:
- **`get_contrasting_text_palette(background_color)`**: Returns semantic tokens (`cover_title`, `cover_subtitle`, `cover_primary_text`, `cover_secondary_text`, `cover_metadata`, `cover_accent`, `cover_badge_bg`, `cover_badge_text`, `cover_border`, `cover_divider`).
- **WCAG Targets**:
  - `Title`: $\ge 7:1$ preferred (minimum $\ge 4.5:1$).
  - `Subtitle`: $\ge 4.5:1$.
  - `Author / Primary Text`: $\ge 4.5:1$.
  - `Edition / Metadata`: $\ge 4.5:1$.
  - `Category / Eyebrow`: $\ge 4.5:1$.
  - `Header Labels`: $\ge 4.5:1$.
- **Light & Cream Backgrounds**: Render very dark charcoal/near-black title (`#111827`), dark slate subtitle (`#374151`), and readable muted metadata (`#4b5563`).
- **Dark Backgrounds**: Render crisp white title (`#ffffff`), light neutral subtitle (`#e2e8f0`), and readable light metadata (`#cbd5e1`).
- **Preflight Validation & Auto-Correction**: `validate_cover_contrast()` inspects all text elements before export, automatically correcting any low-contrast color with its high-contrast semantic token.

