# VasukiSquare Design System

The VasukiSquare design system establishes a high-craft editorial aesthetic derived directly from [DESIGN.md](../DESIGN.md).

---

## 1. Physical A4 Layout & Grid Contracts

- **Document Dimensions**: Physical A4 size (210mm × 297mm).
- **Zero Overflow Contract**: Every normal page must fit exactly inside A4 boundaries. No vertical scrolling or clipping is permitted.
- **Margins & Safe Zones**:
  - Top Margin: 18mm
  - Bottom Margin: 18mm
  - Left / Right Margins: 16mm
- **Header & Footer**:
  - Running header: Displays the publication title and current chapter name.
  - Running footer: Displays publisher imprint, copyright date, and dynamic page number.

---

## 2. Mathematical Color Tokens

All design colors are defined as strict tokens in `src/vasukisquare/design/tokens.py` and converted to CSS custom properties:

### Primary Brand Tokens
- `BRAND_GREEN`: `#00ed64`
- `BRAND_GREEN_DARK`: `#00684a`
- `BRAND_GREEN_MID`: `#00a35c`
- `BRAND_TEAL_DEEP`: `#001e2b`
- `BRAND_TEAL`: `#003d4f`

### Surface & Canvas Tokens
- `CANVAS` (Light): `#ffffff` / `#faf8f5`
- `CANVAS_DARK` (Dark): `#001e2b` / `#00141e`
- `SURFACE` (Light): `#f9fbfa`
- `SURFACE_DARK`: `#0a2635`

### Text & Ink Tokens
- `INK`: `#001e2b`
- `CHARCOAL`: `#1c2d38`
- `SLATE`: `#3d4f5b`
- `MUTED`: `#a8b3bc`
- `ON_DARK`: `#ffffff`
- `ON_DARK_MUTED`: `#a8b3bc`

---

## 3. Chapter Themes & Alternating Contract

VasukiSquare implements an alternating chapter theme contract:
- **Odd Chapters (1, 3, 5, ...)**: Render in **Dark Theme** (`Theme.DARK`), providing deep contrast, glowing code blocks, and crisp typography.
- **Even Chapters (2, 4, 6, ...)**: Render in **Light Theme** (`Theme.LIGHT`), providing clean, editorial reading clarity.
- **Frontmatter & Backmatter**: Render in coordinated neutral themes (`Theme.LIGHT`).

---

## 4. Chapter Opener Templates

Every chapter boundary begins with a dedicated, single-page chapter opener utilizing one of 6 layout templates:

1. **`minimal_centered`**: Centered chapter number, bold headline, and hero Lucide icon.
2. **`left_accent_banner`**: Vertical accent bar on the left margin with strong asymmetric typography.
3. **`split_contrast`**: Two-tone split card separating chapter metadata from title.
4. **`editorial_classic`**: Elegant serif/sans-serif header layout with subtle rule lines.
5. **`technical_blueprint`**: Monospace badge metadata and technical grid styling.
6. **`icon_heroic`**: Large decorative Lucide hero icon with subtitle banner.

**Rule**: Chapter opener pages contain only chapter identification, chapter title, subtitle, and one semantic icon. Body text is never placed on chapter opener pages.

---

## 5. Typography Stacks

VasukiSquare uses high-legibility, open-source typography stacks with system fallbacks:
- **Display & Section Headers**: `'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif`
- **Body & Content Text**: `'Inter', 'Plus Jakarta Sans', -apple-system, sans-serif`
- **Code & Terminal Listings**: `'JetBrains Mono', 'Fira Code', monospace`

---

## 6. Lucide Icon Integration

- Lucide is the exclusive icon system.
- Icons are rendered as inline SVGs using `src/vasukisquare/design/icons.py`.
- Icon colors are mathematically resolved via `IconColorResolver` to match the active page theme.
