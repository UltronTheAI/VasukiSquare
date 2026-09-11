# Getting Started with VasukiSquare

VasukiSquare is an AI-powered research, editorial, HTML layout, and PDF generation engine written in Python.

## Prerequisites

- **Python**: 3.11 or higher
- **MongoDB**: A running instance (local or MongoDB Atlas)
- **Groq API Key**: For LLM-based reasoning and structured outputs
- **Playwright**: For Chromium-based PDF rendering

## Installation

1. Clone the repository and enter the directory:
   ```bash
   git clone <repository-url>
   cd VasukiSquare
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Install the package in editable mode with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Install Playwright browser binaries (for PDF rendering):
   ```bash
   playwright install chromium
   ```

5. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to provide your `GROQ_API_KEY`, `MONGODB_URI`, and search API keys.

## Running Tests

VasukiSquare enforces testing contracts across unit, integration, and rendering suites:

```bash
# Run unit tests
pytest tests/unit -q

# Run integration tests
pytest tests/integration -q

# Run rendering validation tests
pytest tests/rendering -q

# Run all tests
pytest -q
```

