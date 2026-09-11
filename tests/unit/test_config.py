"""Unit tests for configuration loading."""

from vasukisquare.config import Settings, get_settings


def test_settings_defaults():
    settings = Settings()
    assert settings.app_env in ["development", "test", "production"]
    assert settings.mongodb_database == "vasukisquare"
    assert settings.research_max_sources == 30
    assert settings.cover_width == 1600
    assert settings.cover_height == 2560


def test_get_settings_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

