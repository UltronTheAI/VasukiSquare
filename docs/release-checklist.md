# Release & Distribution Checklist

Use this checklist before distributing a new release or uploading a package build of VasukiSquare.

---

## 1. Environment & Clean Clone Validation

- [ ] Clean repository clone or extraction on a fresh machine/environment.
- [ ] Python virtual environment activates cleanly on Windows PowerShell (`.venv\Scripts\Activate.ps1`) and Linux/macOS (`source .venv/bin/activate`).
- [ ] `pip install .` installs dependencies successfully.
- [ ] `pip install -e ".[dev]"` installs editable package and test dependencies.
- [ ] `setup.py` compatibility shim functions correctly.
- [ ] `playwright install chromium` downloads browser binaries without error.

---

## 2. Secrets & Security Audit

- [ ] No live API keys, tokens, or passwords exist in `.env.example`, documentation, or committed repository files (`grep_search` for `gsk_`, `sk-`, `tvly-`, `api_key=`).
- [ ] `.gitignore` properly excludes `.env`, `.env.local`, `output/`, `.tmp/`, `__pycache__/`, `*.egg-info/`, and build directories.
- [ ] Security reporting guidance in `SECURITY.md` is current.

---

## 3. Configuration & Metadata Verification

- [ ] `config.json` contains valid, safe default branding metadata matching `AppConfig` schema.
- [ ] `.env.example` documents every active environment variable with safe placeholder defaults.
- [ ] `pyproject.toml` version matches current release tag and dependencies are up to date.
- [ ] `requirements.txt` is aligned with `pyproject.toml` dependencies.

---

## 4. CLI & Execution Testing

- [ ] `vasukisquare --help` displays argument options.
- [ ] `vasuki --help` alias functions correctly.
- [ ] `python scripts/generate_book.py --help` functions correctly.
- [ ] Sample book generation completes in mock mode:
  ```bash
  vasukisquare --topic "Test Topic" --pages 8 --no-pdf --no-db
  ```
- [ ] Stage checkpoints (`intent.json`, `book_plan.json`, `pages/`) are written to output directory.
- [ ] `--resume` flag successfully reloads checkpoints.

---

## 5. Test Suite Verification

- [ ] All unit tests pass: `pytest tests/unit -q`
- [ ] All integration tests pass: `pytest tests/integration -q`
- [ ] All rendering tests pass: `pytest tests/rendering -q`
- [ ] Complete test suite passes with zero failures: `pytest -q`

---

## 6. Documentation & Link Audit

- [ ] All markdown links across `README.md` and `docs/*.md` resolve to valid existing files.
- [ ] No references to obsolete or removed modules exist.
- [ ] `CHANGELOG.md` reflects all recent additions and improvements.

