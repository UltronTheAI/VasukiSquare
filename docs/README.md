# VasukiSquare Documentation Hub

Welcome to the central documentation index for **VasukiSquare**, an AI-powered technical and practical ebook publishing engine in Python.

---

## 1. Getting Started & User Guides
- [**Getting Started Guide**](getting-started.md): Installation prerequisites, virtual environment setup, configuration, and first book generation.
- [**User Guide**](user-guide.md): Practical guide covering prompt creation, title constraints, page counts, output paths, and common workflows.
- [**CLI Reference**](cli-reference.md): Full reference for all command-line arguments, options, types, and flags.
- [**Automation & GitHub Actions**](automation.md): Production scheduling, GitHub Actions workflows, MongoDB queue lifecycle, and automated publishing cadence.
- [**FAQ**](faq.md): Frequently asked commercial, technical, and licensing questions.

---

## 2. Configuration & Providers
- [**Configuration Guide**](configuration.md): Complete reference for `.env` infrastructure variables, `config.json` white-label branding, and settings precedence.
- [**LLM & Search Providers**](providers.md): Guide to configuring Groq cloud model pools, Ollama local backends, DuckDuckGo, SearXNG, and commercial search APIs.

---

## 3. Architecture & Engine Internals
- [**System Architecture**](architecture.md): Package architecture, Mermaid data-flow diagrams, logic layer boundaries, and module directory map.
- [**Generation Pipeline**](pipeline.md): Step-by-step breakdown of the 7 pipeline stages, stage checkpoints, and error handling.
- [**Research & Retrieval**](research.md): Multi-perspective search query expansion, domain authority ranking, deduplication, and citation synthesis.
- [**Editorial Planning**](editorial-planning.md): Book intent inference, technical vs non-technical classification, and physical page budgeting.
- [**Design System**](design-system.md): Physical A4 layout contracts, mathematical color tokens, dark/light theme alternation, and 6 chapter opener styles.
- [**Cover Design Engine**](cover-design.md): 1600 × 2560 canvas specs, 6 cover styles, procedural math patterns, and WCAG contrast validation.
- [**Rendering Engine & PDF Compilation**](rendering-and-pdf.md): Jinja2 template rendering, Playwright headless Chromium PDF export, and zero-overflow page repair.
- [**MongoDB Schema & Persistence**](mongodb-schema.md): Navigable 3-collection document graph, indexes, and optional persistence setup.

---

## 4. Developer & Commercial Resources
- [**Customization Guide**](customization.md): Guide to extending agent prompts, custom components, color tokens, and layout templates.
- [**Troubleshooting Guide**](troubleshooting.md): Diagnosis and solutions for common setup, model, search, and PDF rendering issues.
- [**Commercial Distribution**](commercial-distribution.md): Customer infrastructure expectations, third-party API keys, and commercial rights.
- [**Release Checklist**](release-checklist.md): Step-by-step verification checklist for distributing builds.

