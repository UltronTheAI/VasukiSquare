# Contributing to VasukiSquare

Thank you for contributing to VasukiSquare! This guide explains how to set up your development environment, run tests, and adhere to project standards.

---

## 1. Development Setup

### Prerequisites
- Python 3.11, 3.12, or 3.13
- Git

### Virtual Environment Setup

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
```

---

## 2. Coding Standards & Architecture Rules

- **Typed Python**: All production code must include type annotations.
- **Pydantic Validation**: All LLM structured outputs and configuration files must use Pydantic models.
- **Modular Pipeline**: Keep stage logic separated across `agents/`, `book/`, `design/`, `llm/`, `pipeline/`, `renderer/`, `research/`, and `tools/`. Do not collapse pipeline stages into single LLM prompts.
- **Visual Source of Truth**: Follow [DESIGN.md](DESIGN.md). All visual styling must use design tokens and Lucide icons.
- **Offline / Mock Mode**: All new features must maintain compatibility with `VASUKISQUARE_MOCK_MODE=true` so unit tests execute deterministically without live API calls.
- **No Hardcoded Secrets**: Never commit API keys, credentials, or personal connection strings.

---

## 3. Running the Test Suite

Before submitting changes, run the test suite:

```bash
# Run all tests
pytest -q

# Run specific suites
pytest tests/unit -q
pytest tests/integration -q
pytest tests/rendering -q
```

All existing tests must pass before pull requests can be merged.

---

## 4. Documentation Updates

When modifying architecture, CLI arguments, environment variables, or config schema:
1. Update relevant documents under `docs/`.
2. Update `.env.example` if new environment variables were added.
3. Update [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]`.

---

## 5. Submitting Pull Requests

1. Create a feature branch from `main`: `git checkout -b feature/my-feature-name`.
2. Make targeted, well-documented commits.
3. Verify test pass rate: `pytest -q`.
4. Open a pull request against the `main` branch with a clear description of the problem and implementation approach.

