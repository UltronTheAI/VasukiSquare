import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
import re

async def check():
    html_path = Path("output/demo/book.html").resolve()
    assert html_path.exists(), "book.html missing"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 794, "height": 1123})
        await page.goto(f"file:///{html_path}")

        # 1. Check DOM bounding boxes & overflow
        pages = await page.query_selector_all(".page")
        print(f"Total rendered pages in DOM: {len(pages)}")
        assert len(pages) >= 40


        overflow_count = 0
        for idx, p_el in enumerate(pages):
            p_num = idx + 1
            metrics = await p_el.evaluate("""el => {
                return {
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth,
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight
                };
            }""")
            if metrics["scrollWidth"] > metrics["clientWidth"] + 1:
                print(f"Warning: Page {p_num} has horizontal scroll overflow: {metrics}")
                overflow_count += 1

        print(f"Total pages with horizontal overflow: {overflow_count}")
        assert overflow_count == 0, "Horizontal overflow detected!"

        # 2. Check for search query/encoding leaks
        content_text = await page.evaluate("() => document.body.innerText")
        leaks = []
        for pat in ["q=", "utm_source=", "%20", "%3A", "%2C"]:
            matches = re.findall(rf".{{0,20}}{re.escape(pat)}.{{0,20}}", content_text, re.IGNORECASE)
            if matches:
                leaks.extend(matches)

        if leaks:
            print(f"Artifact leaks found: {leaks[:5]}")
        else:
            print("No search query or percent-encoding leaks found in visible text!")
        assert len(leaks) == 0, f"Found text artifact leaks: {leaks}"

        # 3. Check rich text & Lucide icons & components
        strong_count = await page.locator("strong").count()
        em_count = await page.locator("em").count()
        code_count = await page.locator("code.rich-code").count()
        svg_count = await page.locator("svg").count()
        hl_count = await page.locator(".hl-k, .hl-nc, .hl-nf").count()
        term_count = await page.locator(".is-command, .is-success").count()

        print(f"<strong> elements: {strong_count}")
        print(f"<em> elements: {em_count}")
        print(f"<code class='rich-code'> elements: {code_count}")
        print(f"<svg> (Lucide icons): {svg_count}")
        print(f"Syntax highlight tokens: {hl_count}")
        print(f"Terminal semantic lines: {term_count}")

        assert strong_count > 0
        assert code_count > 0
        assert svg_count > 0
        assert hl_count > 0

        await browser.close()
        print("All Playwright DOM validations PASSED!")

if __name__ == "__main__":
    asyncio.run(check())
