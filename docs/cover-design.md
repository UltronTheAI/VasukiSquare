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

---

## 5. Solid Dark Title Container & Typography Hierarchy

To guarantee absolute readability and eliminate decorative artwork interference:
- **Layer Order Invariant**:
  ```
  canvas background
  ↓
  cover artwork / vector scenery (z-index: 1)
  ↓
  SOLID dark title container (z-index: 10, background: #001e2b)
  ↓
  title + subtitle
  ```
- **Solid Dark Title Container (`.cover-title-container`)**:
  - Uses a solid, opaque theme-derived dark color (`#001e2b`, charcoal navy) with zero transparency.
  - Comfortable internal padding (`48px 56px` on 1600x2560; `24px 28px` on A4).
  - Clean editorial proportions, subtle border (`1px solid rgba(255,255,255,0.12)`), and elevation.
  - Automatically sizes itself based on title/subtitle length across short, long, and multiline titles.
- **Typography Inside Container**:
  - **Title**: Pure/warm white (`#ffffff`), large editorial serif typography (`'Newsreader', 'Lora', 'Merriweather', 'Playfair Display', Georgia, serif`), dominant hierarchy.
  - **Divider**: Integrated theme-derived accent rule (`#00ed64`).
  - **Subtitle**: Soft light neutral (`#cbd5e1`, Slate 300), visually subordinate and highly readable.
- **Outer Cover Chrome**:
  - Author, edition (`FIRST EDITION`), and category badge adapt to outer background with contrast $\ge 4.5:1$.
- **Preflight Validation**:
  - `CoverValidator.validate_cover()` checks title container opacity, absence of artwork line collisions, WCAG contrast targets, and layout safety margins.

---

## 6. Solid Full-Width Cover Footer Strip & Bottom Branding

To ensure author and edition metadata are always legible regardless of background or artwork scenery complexity:
- **Full-Width Coverage**:
  - Spans 100% width (`width: 100%; left: 0; right: 0;`) and touches the physical bottom edge (`bottom: 0`).
  - Solid dark theme-derived color (`#001e2b`, `brand-teal-deep`) with zero transparency (`opacity: 1`).
- **Render Order Invariant**:
  ```
  cover background
  ↓
  cover artwork / vector scenery (z-index: 1)
  ↓
  bottom footer strip (z-index: 10, width: 100%, bottom: 0, bg: #001e2b)
  ↓
  author (left) + edition text (right)
  ```
- **Typography & Alignment Inside Strip**:
  - **Author**: Left-aligned, vertically centered, high-contrast light text (`#ffffff`, contrast $> 15:1$).
  - **Edition**: Right-aligned, vertically centered, tracked uppercase light/slate text (`#cbd5e1`, contrast $> 9:1$).
  - **Horizontal Padding**: `40px 180px` on 1600×2560; `20px 40px` on A4.
- **Automated Preflight Validation (`CoverValidator.validate_cover`)**:
  - `footer_strip_exists`: Verifies footer strip element is present.
  - `footer_strip_full_width`: Verifies footer strip spans 100% width.
  - `footer_strip_touches_bottom`: Verifies footer strip touches the bottom edge (`bottom: 0`).
  - `footer_metadata_inside_strip`: Verifies author and edition are contained within the footer strip.
  - `author_contrast_pass`: Verifies author text contrast $\ge 4.5:1$ against footer background.
  - `edition_contrast_pass`: Verifies edition text contrast $\ge 4.5:1$ against footer background.
  - `no_metadata_over_artwork`: Verifies footer strip is opaque and layered above artwork (`z-index: 10`).



