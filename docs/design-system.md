# VasukiSquare Design System

The VasukiSquare design system establishes a high-craft editorial document aesthetic derived directly from `DESIGN.md`.

---

## 1. Design Token Categories

All tokens are defined in `vasukisquare.design.tokens` and converted to CSS custom properties dynamically:

### Colors
- **Brand & Primary**:
  - `primary`: `#00ed64`
  - `brand-green`: `#00ed64`
  - `brand-green-dark`: `#00684a`
  - `brand-green-mid`: `#00a35c`
  - `brand-green-soft`: `#c3f0d2`
  - `brand-teal-deep`: `#001e2b`
  - `brand-teal`: `#003d4f`
  - `brand-teal-mid`: `#00684a`
- **Category Accents**:
  - `accent-purple`: `#7b3ff2`
  - `accent-orange`: `#fa6e39`
  - `accent-pink`: `#f06bb8`
  - `accent-blue`: `#3d4f9f`
- **Surfaces & Borders**:
  - `canvas`: `#ffffff`
  - `canvas-dark`: `#001e2b`
  - `surface`: `#f9fbfa`
  - `surface-soft`: `#f4f7f6`
  - `surface-feature`: `#e3fcef`
  - `hairline`: `#e1e5e8`
  - `hairline-strong`: `#c1ccd6`
  - `hairline-dark`: `#1c2d38`
- **Text & Ink**:
  - `ink`: `#001e2b`
  - `charcoal`: `#1c2d38`
  - `slate`: `#3d4f5b`
  - `steel`: `#5c6c7a`
  - `stone`: `#7c8c9a`
  - `muted`: `#a8b3bc`
  - `on-dark`: `#ffffff`
  - `on-dark-muted`: `#a8b3bc`

### Open-Source Typography Stacks
Proprietary faces from the analysis are replaced with metric-compatible open-source stacks:
- **Display / Headers**: `'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif`
- **Body / Content**: `'Inter', 'Plus Jakarta Sans', -apple-system, sans-serif`
- **Code / Listings**: `'JetBrains Mono', 'Fira Code', 'Source Code Pro', monospace`

### Spacing & Radii Scale
- **Spacing**: `xxs` (4px), `xs` (8px), `sm` (12px), `md` (16px), `lg` (20px), `xl` (24px), `xxl` (32px), `xxxl` (40px), `section-sm` (48px), `section` (64px), `section-lg` (96px), `hero` (120px).
- **Radii**: `xs` (4px), `sm` (6px), `md` (8px), `lg` (12px), `xl` (16px), `xxl` (24px), `full` (9999px / pill).

---

## 2. 14 Controlled Editorial Page Layouts

VasukiSquare enforces 14 distinct layout types to guarantee page-to-page visual variety without sacrificing design harmony:

1. **`editorial`**: High-readability multi-column text layout with leading drop-caps and section summaries.
2. **`split-explainer`**: Two-column layout pairing a narrative explanation with a visual card.
3. **`large-number`**: Big KPI / metric callouts with descriptive captions.
4. **`quote`**: Large stylized callout quotations with author attributions.
5. **`timeline`**: Vertical stepped milestone and chronological sequence layout.
6. **`comparison`**: Side-by-side comparative matrices and trade-off tables.
7. **`diagram-focus`**: Prominent architectural frame for system diagrams and workflows.
8. **`code-focus`**: Syntax-highlighted code block with terminal headers.
9. **`concept-grid`**: 2x2 or 3-column card grid explaining related sub-concepts.
10. **`research-highlight`**: Key scientific finding or benchmark with highlighted border.
11. **`definition`**: Formal glossary/terminology breakdown.
12. **`case-study`**: Real-world incident or deployment case study with takeaway badges.
13. **`full-bleed-statement`**: Hero text banner for pivotal chapter insights.
14. **`summary`**: Key takeaways and bulleted chapter recap.

---

## 3. Anti-Repetition Constraints

The `LayoutConstraintEngine` ensures that adjacent content pages do not reuse the same layout, preventing monotonous sequences of identical page templates while maintaining the unified design language.

---

## 4. Semantic Lucide Icon Handling

- The LLM selects the **semantic icon name** (e.g. `sparkles`, `cpu`, `database`, `code`, `layers`).
- The renderer selects the **icon token color** via `IconColorResolver`:
  - Dark Theme $\rightarrow$ `ColorToken.BRAND_GREEN` (`#00ed64`) or `ColorToken.ON_DARK` (`#ffffff`)
  - Light Theme $\rightarrow$ `ColorToken.BRAND_GREEN_DARK` (`#00684a`) or `ColorToken.INK` (`#001e2b`)
- Arbitrary colors are rejected with validation errors.

