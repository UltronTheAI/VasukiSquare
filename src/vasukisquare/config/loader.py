"""Configuration loading, validation, and default generation for VasukiSquare publications."""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union
from pydantic import ValidationError

from vasukisquare.config.defaults import DEFAULT_CONFIG_DICT, get_default_config
from vasukisquare.config.schema import AppConfig

logger = logging.getLogger("vasukisquare.config")

CONFIG_FILENAME = "config.json"


class ConfigValidationError(Exception):
    """Raised when ./config.json is missing required fields, malformed, or invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


def find_project_root() -> Path:
    """Locate project root directory containing pyproject.toml, config.json, or src/."""
    # Start with current working directory
    cwd = Path.cwd().resolve()
    candidates = [cwd] + list(cwd.parents)

    for p in candidates:
        if (p / CONFIG_FILENAME).exists() or (p / "pyproject.toml").exists() or (p / "src" / "vasukisquare").exists():
            return p

    return cwd


def resolve_config_path(config_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve absolute path to config.json."""
    if config_path:
        return Path(config_path).resolve()
    return find_project_root() / CONFIG_FILENAME


def format_validation_error(e: ValidationError, config_path: Path) -> str:
    """Format Pydantic ValidationError into a clear, user-actionable error message."""
    errors = e.errors()
    if not errors:
        return f"[CONFIG ERROR]\nFailed to load {config_path.name}: {e}"

    first_err = errors[0]
    loc = ".".join(str(elem) for elem in first_err.get("loc", []))
    err_type = first_err.get("type", "")
    msg = first_err.get("msg", "")
    input_val = first_err.get("input", None)

    lines = [
        "",
        "============================================================",
        " VasukiSquare Configuration Error",
        "============================================================",
        "File:",
        f"    {config_path}",
        "",
        "Field:",
        f"    {loc or 'root'}",
        "",
    ]

    if "missing" in err_type:
        lines.extend([
            "Problem:",
            f"    Required field \"{loc}\" is missing.",
            "",
            "Expected:",
            "    Valid non-empty value",
            "",
            "Received:",
            "    <missing>",
        ])
    else:
        lines.extend([
            "Problem:",
            f"    {msg}",
            "",
            "Received:",
            f"    {json.dumps(input_val) if input_val is not None else 'null'}",
        ])

    # Helpful example suggestions based on field
    example_hints = {
        "branding.author_name": '"author_name": "John Smith"',
        "branding.publication_name": '"publication_name": "Northstar Books"',
        "branding.company_name": '"company_name": "Northstar Media LLC"',
        "branding.engine_name": '"engine_name": "Northstar Publishing Engine"',
        "branding.website": '"website": "https://northstarbooks.com" (or "" to omit)',
        "edition.name": '"name": "FIRST EDITION"',
        "edition.year": '"year": 2026',
        "copyright.holder": '"holder": "Northstar Media LLC"',
        "book_defaults.language": '"language": "English"',
    }

    if loc in example_hints:
        lines.extend([
            "",
            "Expected example:",
            f"    {example_hints[loc]}",
        ])

    lines.extend([
        "",
        "Fix config.json and restart VasukiSquare.",
        "============================================================",
        "",
    ])

    return "\n".join(lines)


def format_json_syntax_error(e: json.JSONDecodeError, config_path: Path) -> str:
    """Format json.JSONDecodeError into clear, user-actionable message."""
    return f"""
============================================================
 VasukiSquare Configuration Error
============================================================
File:
    {config_path}

Problem:
    Malformed JSON syntax on line {e.lineno}, column {e.colno}:
    {e.msg}

Fix config.json and restart VasukiSquare.
============================================================
"""


def create_default_config_file(config_path: Path) -> AppConfig:
    """Create a new default config.json file formatted with indent=2, UTF-8, and newline at EOF."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(DEFAULT_CONFIG_DICT, indent=2) + "\n"
    config_path.write_text(content, encoding="utf-8")
    
    print("[Config] config.json not found")
    print(f"[Config] Created default VasukiSquare configuration at {config_path}")
    print("[Config] Loaded configuration successfully")
    return get_default_config()


def validate_config_dict(data: Dict[str, Any], config_path: Path) -> AppConfig:
    """Validate a loaded configuration dictionary against AppConfig schema."""
    if not isinstance(data, dict):
        msg = f"\n[CONFIG ERROR]\nFile: {config_path}\nProblem: Root JSON structure must be an object (dictionary), received {type(data).__name__}.\n"
        print(msg, file=sys.stderr)
        raise ConfigValidationError(msg)

    try:
        return AppConfig(**data)
    except ValidationError as e:
        err_msg = format_validation_error(e, config_path)
        print(err_msg, file=sys.stderr)
        raise ConfigValidationError(err_msg, details={"validation_error": e}) from e


def load_config(
    config_path: Optional[Union[str, Path]] = None,
    create_if_missing: bool = True,
) -> AppConfig:
    """Load, validate, and return the application configuration.
    
    - If config.json does not exist and create_if_missing=True, creates default config.json and returns it.
    - If config.json exists but is invalid/malformed, raises ConfigValidationError without modifying file.
    - If config.json exists and is valid, returns validated AppConfig.
    """
    target_path = resolve_config_path(config_path)

    if not target_path.exists():
        if create_if_missing:
            return create_default_config_file(target_path)
        raise ConfigValidationError(f"[Config] Configuration file not found at: {target_path}")

    # Read existing file (DO NOT OVERWRITE ON ERROR)
    try:
        raw_text = target_path.read_text(encoding="utf-8")
    except Exception as e:
        msg = f"\n[CONFIG ERROR]\nFailed to read {target_path}: {e}\n"
        print(msg, file=sys.stderr)
        raise ConfigValidationError(msg) from e

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        err_msg = format_json_syntax_error(e, target_path)
        print(err_msg, file=sys.stderr)
        raise ConfigValidationError(err_msg) from e

    return validate_config_dict(data, target_path)


_cached_config: Optional[AppConfig] = None


def get_app_config(config_path: Optional[Union[str, Path]] = None) -> AppConfig:
    """Return the singleton cached AppConfig instance, loading once on first access."""
    global _cached_config
    if _cached_config is None:
        _cached_config = load_config(config_path=config_path, create_if_missing=True)
    return _cached_config


def reset_app_config() -> None:
    """Reset cached AppConfig instance (used for testing and dynamic reloading)."""
    global _cached_config
    _cached_config = None

