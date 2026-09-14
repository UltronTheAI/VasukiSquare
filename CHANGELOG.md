# Changelog

All notable changes to the VasukiSquare ebook generation engine are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-15

### Added
- **Multi-Stage Generation Pipeline**: 7-stage orchestrator covering Intent Inference, Deep Research, Editorial Planning, Cover Artwork Design, Page Authoring, Database Persistence, and HTML/PDF Assembly.
- **Dual LLM Provider Architecture**: Native support for Groq (cloud high-speed inference with model pool rotation, API key pools, and cooldown management) and Ollama (local private inference).
- **Multi-Provider Web Search & Grounding**: Swappable search backends supporting DuckDuckGo (free zero-key search), SearXNG (local metasearch), Tavily, Serper, Brave Search, and offline mock mode.
- **Physical A4 Layout & PDF Compilation**: Playwright Chromium headless engine enforcing exact physical A4 dimensions (210mm × 297mm) with zero-overflow page repair.
- **Visual Design System**: Mathematical token color resolver, Lucide icon integration, 6 distinct chapter opener templates, and dynamic dark/light alternating chapter themes.
- **High-Resolution Cover Generation**: 1600 × 2560 canvas cover generator with contrast validation, geometric patterns, and auto-cropping into A4 output.
- **White-Label Branding System**: Strict Pydantic-validated `config.json` system for author, imprint, company, and copyright configuration.
- **CLI & Packaging**: Unified `vasukisquare` and `vasuki` console entry points, `scripts/generate_book.py`, `setup.py` compatibility shim, and full `pyproject.toml` packaging.
- **Checkpoint & Resume**: Granular stage and page checkpointing in JSON format allowing interrupted generations to resume without repeating completed work.
- **Optional MongoDB Persistence**: 3-collection navigable document graph (`books`, `pages`, `covers`) with doubly-linked page traversal and non-blocking failure tolerance.
- **Content Quality Audit**: 15-point automated structural, semantic, and density verification suite ensuring consistent output formatting.

