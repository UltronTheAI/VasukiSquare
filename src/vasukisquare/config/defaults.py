"""Default VasukiSquare configuration data and factory functions."""

from typing import Any, Dict
from vasukisquare.config.schema import (
    AppConfig,
    BookDefaultsConfig,
    BrandingConfig,
    CopyrightConfig,
    EditionConfig,
)

DEFAULT_CONFIG_DICT: Dict[str, Any] = {
    "branding": {
        "author_name": "Vasuki",
        "publication_name": "Vasuki Publishing",
        "company_name": "VasukiSquare",
        "engine_name": "VasukiSquare AI Publishing Engine",
        "website": "https://vasukisquare.cc",
    },
    "edition": {
        "name": "FIRST EDITION",
        "year": 2026,
    },
    "copyright": {
        "holder": "Vasuki Publishing",
        "all_rights_reserved": True,
    },
    "book_defaults": {
        "language": "English",
    },
}


def get_default_config() -> AppConfig:
    """Create and return a new validated AppConfig with standard Vasuki defaults."""
    return AppConfig(
        branding=BrandingConfig(**DEFAULT_CONFIG_DICT["branding"]),
        edition=EditionConfig(**DEFAULT_CONFIG_DICT["edition"]),
        copyright=CopyrightConfig(**DEFAULT_CONFIG_DICT["copyright"]),
        book_defaults=BookDefaultsConfig(**DEFAULT_CONFIG_DICT["book_defaults"]),
    )

