# Cover Design & Artwork Engine

The VasukiSquare Cover subsystem (`src/vasukisquare/cover/`) generates publication covers that combine typography, geometric patterns, and contrast validation.

---

## 1. Canvas Dimensions & Physical Sizing

- **Source Canvas Resolution**: `1600 × 2560` pixels (high-resolution raster/SVG ratio).
- **Physical Output Format**: Scaled, cropped, and positioned onto physical A4 (210mm × 297mm) as Page 1 of the ebook.
- **Standalone Artwork Output**: Rendered as a standalone HTML file (`output/cover.html`) and optional high-res PNG (`output/cover.png`).

---

## 2. Six Distinct Cover Layout Styles

The cover generator selects one of 6 layout styles (`src/vasukisquare/cover/styles.py`):

1. **`editorial_minimal`**: Clean centered title typography with publisher imprint footer and minimalist border.
2. **`split_hero`**: Contrasting two-tone split background pairing a dark header zone with a light content zone.
3. **`geometric_accent`**: Procedural math-driven SVG geometric pattern grids.
4. **`technical_blueprint`**: Monospace engineering typography, circuit patterns, and technical badge metadata.
5. **`swiss_bold`**: Stark asymmetric typography with bold accent color blocks.
6. **`minimal_monochrome`**: High-contrast black and white typography with sharp geometric framing.

---

## 3. WCAG Contrast Validation & Repair

Every planned cover undergoes automated contrast validation (`src/vasukisquare/cover/validator.py` and `contrast.py`):

- **Relative Luminance Calculation**: Evaluates the contrast ratio between title text, background canvas, and accent badges.
- **Threshold Enforcement**: Enforces a minimum WCAG AA contrast ratio of 4.5:1 (and 7:1 for headers).
- **Automatic Contrast Repair**: If a chosen color combination fails contrast checks, the repair engine automatically darkens or brightens the background/text tokens to guarantee legibility.

---

## 4. Procedural Pattern Generation

Geometric patterns are generated using procedural math functions (`src/vasukisquare/design/cover_patterns.py`):
- Isometric grid lines
- Concentric circle matrices
- Dot grid arrays
- Architectural cross-hatching

All patterns are seeded deterministically from the book topic and title to ensure reproducible cover art.
