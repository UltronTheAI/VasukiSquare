# Example: Technical Programming Ebook Generation

This example demonstrates how to generate a technical software engineering book complete with code examples, syntax highlighting, callout tips, and reference citations.

## Generation Command

```bash
vasukisquare \
  --topic "Python 3.12 Deep Dive: Concurrency, Type Annotations, and AsyncIO Internals" \
  --title "Modern Python Concurrency" \
  --prompt "A rigorous deep dive for intermediate to senior Python developers. Emphasize task groups, exception groups, async iterators, memory efficiency, GIL improvements in 3.12, and practical pitfalls in high-throughput network services." \
  --pages 45 \
  --output-dir "./output/python-concurrency"
```

## Linux / macOS Bash

```bash
vasukisquare \
  --topic "Python 3.12 Deep Dive: Concurrency, Type Annotations, and AsyncIO Internals" \
  --title "Modern Python Concurrency" \
  --pages 45 \
  --output-dir "./output/python-concurrency"
```

## Windows PowerShell

```powershell
vasukisquare `
  --topic "Python 3.12 Deep Dive: Concurrency, Type Annotations, and AsyncIO Internals" `
  --title "Modern Python Concurrency" `
  --pages 45 `
  --output-dir "./output/python-concurrency"
```

## Pipeline Behavior for Technical Subjects

1. **Intent Inference**: Automatically identifies the subject as technical (`is_technical=true`), detects `python` as the primary programming language, and schedules code blocks across chapter content pages.
2. **Research Grounding**: Plans search queries targeting official Python documentation (`docs.python.org`), PEP specifications (`peps.python.org`), and authoritative articles.
3. **Structured Components**: Emits terminal command blocks, syntax-highlighted code listings, architectural cards, and warning/tip callouts.
4. **Theme Assignment**: Alternates visual themes (dark theme for odd chapters, light theme for even chapters) using the mathematical `editorial_code` or `technical_blueprint` palette.

