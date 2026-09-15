# Frequently Asked Questions (FAQ)

---

### Does VasukiSquare require an active internet connection?
Not necessarily. VasukiSquare can run **100% offline** if you configure:
1. `LLM_PROVIDER=ollama` (using a local model like `qwen2.5:7b-instruct`).
2. `SEARCH_PROVIDER=mock` (using the built-in offline technical reference corpus).

When connected to the internet, you can use Groq Cloud LLMs for ultra-fast generation and DuckDuckGo/SearXNG/Tavily for live web research.

---

### Do I need to run MongoDB?
**No**. MongoDB is completely optional. All books, individual page HTML files, manifests, and compiled PDFs are written directly to your output directory. If MongoDB is not running (or if you use `--no-db`), the generation pipeline completes normally.

---

### What API keys do I need?
None are strictly required:
- If you use **Ollama** and **DuckDuckGo**, you need **0 paid API keys**.
- If you want the fastest cloud generation speeds (200–500+ tokens/sec), you can sign up for a **Groq API Key** (a free tier is available at console.groq.com).
- Commercial search providers (Tavily, Serper, Brave) are optional.

---

### Can I generate non-technical ebooks?
**Yes**. VasukiSquare automatically detects whether a topic is technical or non-technical. For non-technical topics (e.g. habits, leadership, productivity, history, business), the engine suppresses code blocks and terminal listings, replacing them with takeaway cards, step-by-step checklists, reflection prompts, and concept tables.

---

### Can I white-label and customize publisher branding?
**Yes**. All publisher metadata is controlled through `config.json` in the root directory. You can customize the author name, publication imprint, company name, engine acknowledgment, website, edition, and copyright notice.

---

### Can I sell the ebooks I generate?
The source code license governing the generator software is provided in the repository's [LICENSE](../LICENSE) (Apache 2.0). Rights and commercial usage of the generated text content depend on your use of underlying LLM providers (e.g., Groq / Meta Llama / Ollama license terms) and attribution requirements of any external research sources cited in the book. Review third-party provider terms for commercial publishing.

---

### Where are the generated output files saved?
By default, artifacts are saved in `./output/`. You can specify a custom folder using `--output-dir "./output/my-custom-book"`. The folder will contain `book.pdf`, `book.html`, `cover.html`, `book_manifest.json`, `research.json`, and the `pages/` directory.

---

### Why does generation take a few minutes?
VasukiSquare executes an explicit 7-stage pipeline: intent analysis, multi-query research, domain deduplication, editorial outline generation, cover design, page-by-page authoring, zero-overflow geometry repair, and Playwright Chromium PDF compilation. This rigorous multi-stage pipeline guarantees factual accuracy and clean A4 physical layout.

---

### Can I resume an interrupted generation?
**Yes**. VasukiSquare writes intermediate checkpoints to `output/checkpoints/`. Simply run the same command with the `--resume` flag to continue from where the job stopped.

