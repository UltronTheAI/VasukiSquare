# Rendering Engine & PDF Compilation

VasukiSquare converts structured data models into physical A4 HTML pages and compiles them into publication-ready PDF documents.

---

## 1. HTML Rendering & Template Architecture

The HTML rendering pipeline (`src/vasukisquare/renderer/html.py`):
1. **Jinja2 Template Processing**: Loads templates from `src/vasukisquare/templates/` (`base.html`, `book.html`, `cover.html`, `styles.css`).
2. **Component Block Rendering**: Maps Pydantic component objects (`HeroHeaderBlock`, `ParagraphBlock`, `CodeSnippetBlock`, `CalloutBlock`, etc.) into semantic, styled HTML.
3. **Rich Text Formatting**: Formats `RichSpan` models into inline bold, italic, code, and external link tags without raw markdown syntax.
4. **Header & Footer Decoration**: Injects dynamic running headers with book/chapter titles, publisher imprints, and calculated page numbers.

---

## 2. Playwright Chromium PDF Compilation

PDF export (`src/vasukisquare/renderer/pdf.py`) uses Playwright with headless Chromium to guarantee print rendering fidelity:

```python
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page(viewport={"width": 794, "height": 1123})
    await page.set_content(html_content, wait_until="load")
    
    # Wait for all web fonts to load
    await page.evaluate("() => document.fonts.ready")
    
    # Compile physical A4 PDF
    await page.pdf(
        path=str(out_path),
        format="A4",
        print_background=True,
        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
    )
```

### Key PDF Invariants
- **Dimensions**: Exact ISO A4 format (210mm × 297mm).
- **Margins**: Zero page margin in Playwright; inner margins are handled by CSS (`@page { size: A4; margin: 0; }`).
- **Font Settlement**: Explicit JavaScript promise (`document.fonts.ready`) ensures typography never flashes or shifts during rendering.
- **Image Load Validation**: Waits for all SVG icons and raster graphics to complete loading before capturing the PDF snapshot.

---

## 3. Zero-Overflow & Canonical Safe-Area Architecture

In physical A4 printing, page content must never vertically overflow, enter, hide behind, or be clipped by the footer/bottom page boundary. VasukiSquare enforces a centralized geometric boundary model (`src/vasukisquare/renderer/geometry.py` and `src/vasukisquare/renderer/overflow.py`):

1. **Canonical Safe Area Geometry**:
   - `PAGE_HEIGHT_MM = 297.0mm`, `PAGE_WIDTH_MM = 210.0mm`.
   - `HEADER_RESERVED_HEIGHT_MM = 18.0mm` (12mm header + 6mm gap).
   - `FOOTER_RESERVED_HEIGHT_MM = 16.0mm` (10mm footer + 6mm gap).
   - `BOTTOM_SAFETY_GAP_MM = 8.0mm` mandatory breathing room strictly preserved before footer safe zone.
   - `CONTENT_TOP_MM = 42.0mm`, `CONTENT_BOTTOM_MM = 249.0mm`, `AVAILABLE_CONTENT_HEIGHT_MM = 207.0mm`.
   - `SAFE_BOTTOM_EPSILON_MM = 1.0mm` renderer rounding tolerance.

2. **Atomic Component Fit & Orphan Prevention**:
   - Atomic cards, callouts, comparison boxes, steps, and figure+caption blocks are never split mid-card when insufficient space remains; they move cleanly to the next page.
   - Orphaned headings at page bottoms are automatically prevented and moved with their succeeding section.

3. **Sub-splitting for Tall Multi-Item Components**:
   - Code snippets and terminal sessions are split strictly on exact newline boundaries with `(Cont.)` captions.
   - Tables repeat column headers across split fragments.
   - Checklists, steps, and comparisons partition at clean item boundaries.

4. **Table of Contents Re-indexing**:
   - When continuation pages are dynamically inserted, `regenerate_toc_pages` re-synchronizes chapter starting page numbers across the document.

---

## 4. Preflight Audit & DOM Geometry Inspection

Before final PDF generation, `preflight_book` (`src/vasukisquare/renderer/preflight.py`) and Playwright DOM layout inspection (`src/vasukisquare/renderer/pdf.py`) conduct comprehensive visual QA:
- **Playwright DOM Bounding Box Validation**: Inspects rendered DOM bounding boxes (`getBoundingClientRect()`) for `.page-content` vs `.page-footer` to guarantee zero visual collisions or overflow.
- Verifies physical A4 dimensions and safe margins across all pages.
- Verifies that chapter openers contain zero body text.
- Validates alternating theme colors and contrast.
- Ensures all page numbers are sequential and continuous.
- Writes findings to `output/preflight_report.json`.

---

## 5. Rendering Troubleshooting

| Problem | Cause | Solution |
|---|---|---|
| `Executable doesn't exist at ...` | Playwright Chromium binary not installed | Run `playwright install chromium` in your virtual environment. |
| Missing system libraries on Linux | Headless Linux missing dependencies | Run `playwright install-deps chromium` (requires sudo on Debian/Ubuntu). |
| Custom font not displaying | Network offline or font blocked | VasukiSquare uses robust fallback font stacks (`Inter`, `Plus Jakarta Sans`, system sans-serif). |
| Blank pages in output | Overflow margin or extra line break | Check `preflight_report.json` to inspect page height utilization. |
