"""VasukiSquare configuration package unifying publication branding (config.json) and environment settings (.env)."""

from vasukisquare.config.defaults import DEFAULT_CONFIG_DICT, get_default_config
from vasukisquare.config.loader import (
    ConfigValidationError,
    format_validation_error,
    format_json_syntax_error,
    get_app_config,
    load_config,
    reset_app_config,
    resolve_config_path,
)
from vasukisquare.config.schema import (
    AppConfig,
    BookDefaultsConfig,
    BrandingConfig,
    CopyrightConfig,
    EditionConfig,
)
from vasukisquare.config.settings import (
    EnvironmentConfigurationError,
    Settings,
    get_groq_models,
    get_settings,
)

# Semantic aliases
VasukiConfig = AppConfig

__all__ = [
    # Branding & Publication Configuration (config.json)
    "AppConfig",
    "VasukiConfig",
    "BrandingConfig",
    "EditionConfig",
    "CopyrightConfig",
    "BookDefaultsConfig",
    "DEFAULT_CONFIG_DICT",
    "get_default_config",
    "load_config",
    "get_app_config",
    "reset_app_config",
    "resolve_config_path",
    "ConfigValidationError",
    "format_validation_error",
    "format_json_syntax_error",
    # Infrastructure & Environment Settings (.env)
    "Settings",
    "get_settings",
    "get_groq_models",
    "EnvironmentConfigurationError",
]

