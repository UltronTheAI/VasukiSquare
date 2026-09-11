# VasukiSquare HTML Rendering & A4 PDF Pagination Subsystem

The rendering subsystem converts structured `Page` models into canonical HTML and deterministic physical A4 PDF documents.

---

## 1. Physical A4 Pagination Model

Every rendered page conforms strictly to the physical A4 print specification:
- **Dimensions**: `210mm × 297mm`
- **Page Rules**:
  ```css
  @page {
    size: A4;
    margin: 0;
  }
  ```
- **Page Container**: Each logical `Page` entity maps to exactly one `.page` HTML container with `box-sizing: border-box`, `padding: 24mm 20mm`, and `overflow: hidden`.
- **Page Breaking**: `page-break-after: always; break-after: page;` guarantees clean document assembly without inter-page spillover.

---

## 2. Page Chrome & Header/Footer Placement

- **Normal Content Pages**:
  - **Header**: Chapter number, chapter title, and book topic.
  - **Footer**: Book title and 1-indexed page number.
- **Chapter Opener Pages**:
  - Intentionally minimal: Omits header chrome and contains **ONLY** the chapter number, chapter title, and one Lucide SVG icon.
- **Cover & Thank-You Pages**:
  - Hero formatting with full-bleed canvas styling and dark background tokens.

---

## 3. Overflow Detection & Controlled Repair

Instead of applying arbitrary CSS scaling or font-size shrinking when content exceeds page capacity, VasukiSquare uses a **Controlled Repair Engine**:

1. **Detection (`OverflowDetector`)**:
   - Analyzes total character counts, paragraph density, and code line lengths against calibrated A4 page thresholds (`MAX_PAGE_CHARACTERS = 2800`).
2. **Controlled Splitting (`ContentSplitter`)**:
   - Splits overflowing paragraphs at sentence or natural paragraph boundaries.
3. **Graph Repair (`PageRepairEngine`)**:
   - Creates a continuation page (e.g. `Section (Cont.)`), inserts it into the page sequence, re-links `previous_page_id` and `next_page_id` bidirectional pointers, and re-indexes downstream page numbers.

---

## 4. Playwright Chromium PDF Generation

PDF export runs headless Chromium via Playwright:
```python
await page.pdf(
    path=output_path,
    format="A4",
    print_background=True,
    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
)
```

---

## 5. Regression Snapshot Fixtures

The subsystem maintains 10 canonical layout fixtures verified across every test run:
1. `cover`
2. `copyright`
3. `toc`
4. `dark_chapter_opener`
5. `light_chapter_opener`
6. `text_heavy` (editorial)
7. `code` (code-focus)
8. `comparison`
9. `references`
10. `thank_you`

