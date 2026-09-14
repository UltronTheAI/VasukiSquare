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

## 3. Dynamic Page Insertion & Semantic Overflow Pagination

Instead of shrinking font sizes, compressing spacing, clipping components, or dropping content, VasukiSquare decouples logical pages from physical pages using **Dynamic Page Insertion**:

$$\text{Logical Content Page} \ne \text{Always One Physical Page}$$

1. **Vertical Geometry & Safe Content Limits**:
   - Usable safe content height: `CONTENT_SAFE_HEIGHT_MM = 215.0mm`
   - Content target ratio: $0.85 - 0.95$ of safe usable height.
   - Any content exceeding `CONTENT_SAFE_HEIGHT_MM` triggers dynamic page splitting.

2. **Component-Level Semantic Splitting (`find_safe_page_split`)**:
   - Partitions components at natural structural boundaries (between `TextBlock`, `CalloutBlock`, `ComparisonBlock`, `TableBlock`, `StepBlock`, etc.).
   - Multi-item components sub-split cleanly when needed:
     - `TableBlock`: splits rows with repeated column headers and `(Cont.)` caption.
     - `ChecklistBlock`: splits items with continuous numbering.
     - `StepBlock`: splits steps across pages with `(Cont.)` title.
     - `TextBlock`: splits paragraphs without orphan sentences.

3. **Recursive Continuation Page Generation (`create_continuation_page`)**:
   - Continuation pages inherit chapter number, chapter title, theme, and layout styling.
   - Headlines are cleanly suffixed: `"<Headline> (Cont.)"`, `"<Headline> (Cont. 2)"`, etc.
   - If an inserted continuation page itself contains excess content, the pagination engine recursively splits it until all physical pages satisfy safe A4 height constraints.

4. **Dynamic Table of Contents & Sequential Pointer Linking**:
   - All physical pages in the book are re-indexed $1 \dots M$ with bidirectional MongoDB linked list pointers (`previous_page_id`, `next_page_id`).
   - `regenerate_toc_pages` dynamically resolves the actual physical starting page numbers of all chapters and updates TOC entries automatically.

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

