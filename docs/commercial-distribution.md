# Commercial Source-Code Distribution Guide

This document outlines key considerations for customers and developers who have purchased or acquired the VasukiSquare source-code package.

---

## 1. What Is Included in the Package

When you purchase or download VasukiSquare, you receive the full Python source code for the publishing engine:

- **Complete Multi-Stage Pipeline**: Intent inference, deep research, editorial planning, cover design, page authoring, zero-overflow geometry repair, and physical A4 PDF compilation.
- **Dual LLM Provider Architecture**: Full integration with Groq (including key pooling, model pools, failover, and cooldowns) and local Ollama.
- **Search & Research Engine**: Integrations for DuckDuckGo, SearXNG, Tavily, Serper, Brave, and offline mock modes.
- **Design System & Visual Tokens**: Complete mathematical token library, 6 cover styles, 6 chapter opener templates, and dark/light alternating themes.
- **Packaging & CLI**: Modern `pyproject.toml`, `setup.py` compatibility shim, `vasukisquare` CLI entry point, and test suites.
- **Documentation Suite**: Comprehensive onboarding, architectural, configuration, and API reference guides.

---

## 2. Customer Infrastructure & API Key Responsibilities

- **Source Code Product**: This distribution consists exclusively of the Python source code and documentation. It does not include hosted cloud subscriptions or managed database services.
- **Bring Your Own Keys (BYOK)**: Customers provide their own API keys where applicable (e.g. Groq Cloud, Tavily, Serper) or run free local backends (Ollama, SearXNG, DuckDuckGo).
- **Third-Party API Costs**: Any consumption costs incurred from third-party cloud providers (such as Groq or commercial search APIs) are separate and billed directly by those providers to your respective accounts.

---

## 3. Licensing & Commercial Usage Boundaries

- **Software Source Code License**: The software source code is licensed under the terms of the repository's [LICENSE](../LICENSE) (Apache License 2.0).
- **Generated Book Content**: The copyright and commercial publication rights of ebooks produced by the engine depend on your applicable agreements with the underlying model providers (e.g., Meta Llama license terms, Groq terms of service) and appropriate attribution for any cited research sources.
- **Attribution & Branding**: You are free to white-label generated publications using `config.json` to present your own author names, publishing imprints, corporate identities, and copyright notices.

