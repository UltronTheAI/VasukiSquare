"""Configuration loading for VasukiSquare using Pydantic Settings."""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Groq & LLM
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")

    # MongoDB
    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_database: str = Field(default="vasukisquare", alias="MONGODB_DATABASE")

    # Search & Retrieval
    tavily_api_key: Optional[str] = Field(default=None, alias="TAVILY_API_KEY")
    serper_api_key: Optional[str] = Field(default=None, alias="SERPER_API_KEY")
    brave_search_api_key: Optional[str] = Field(default=None, alias="BRAVE_SEARCH_API_KEY")

    # Research Limits
    research_max_sources: int = Field(default=30, alias="RESEARCH_MAX_SOURCES")
    research_max_pages_per_source: int = Field(default=5, alias="RESEARCH_MAX_PAGES_PER_SOURCE")

    # Generation Defaults
    default_language: str = Field(default="en", alias="DEFAULT_LANGUAGE")
    default_target_pages: int = Field(default=60, alias="DEFAULT_TARGET_PAGES")
    default_max_chapters: int = Field(default=12, alias="DEFAULT_MAX_CHAPTERS")

    # Rendering
    pdf_output_dir: str = Field(default="./output", alias="PDF_OUTPUT_DIR")
    temp_render_dir: str = Field(default="./.tmp", alias="TEMP_RENDER_DIR")
    chromium_headless: bool = Field(default=True, alias="CHROMIUM_HEADLESS")

    # Cover dimensions
    cover_width: int = Field(default=1600, alias="COVER_WIDTH")
    cover_height: int = Field(default=2560, alias="COVER_HEIGHT")


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()

