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

## 3. Zero-Overflow & Page Repair Engine

In physical A4 printing, page content must never vertically overflow its container. VasukiSquare incorporates an automated overflow detection and repair engine (`src/vasukisquare/renderer/overflow.py`):

1. **Content Density Estimation**: Calculates the physical vertical height of all component blocks on each page.
2. **Dynamic Splitting**: If a page's content density exceeds 100% of the printable A4 safe zone, the repair engine splits the content across consecutive pages while preserving heading hierarchies.
3. **Table of Contents Re-indexing**: When pages are dynamically split, Pass 2 updates chapter starting page numbers in the Table of Contents.

---

## 4. Preflight Audit

Before final PDF generation, `preflight_book` (`src/vasukisquare/renderer/preflight.py`) conducts automated preflight checks:
- Verifies physical A4 dimensions across all pages.
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
