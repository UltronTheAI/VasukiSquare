"""Configuration loading for VasukiSquare using Pydantic Settings."""

from functools import lru_cache
from typing import Any, Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentConfigurationError(Exception):
    """Raised when required production environment configuration is missing."""
    pass


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env/.env.local files."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    vasukisquare_mock_mode: bool = Field(default=False, alias="VASUKISQUARE_MOCK_MODE")

    # LLM Provider Selection: "auto", "groq", or "ollama"
    llm_provider: str = Field(default="auto", alias="LLM_PROVIDER")
    llm_temperature: float = Field(default=0.25, alias="LLM_TEMPERATURE")
    llm_fallback_on_rate_limit: bool = Field(default=False, alias="LLM_FALLBACK_ON_RATE_LIMIT")

    # Groq & Cloud LLM Model Pool
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_MODEL")
    groq_models: Optional[str] = Field(default=None, alias="GROQ_MODELS")
    groq_model_strategy: str = Field(default="ordered", alias="GROQ_MODEL_STRATEGY")
    groq_model_fallback: bool = Field(default=True, alias="GROQ_MODEL_FALLBACK")
    groq_retries_per_model: int = Field(default=1, alias="GROQ_RETRIES_PER_MODEL")
    groq_max_model_attempts: int = Field(default=0, alias="GROQ_MAX_MODEL_ATTEMPTS")
    groq_model_cooldown_seconds: float = Field(default=60.0, alias="GROQ_MODEL_COOLDOWN_SECONDS")
    groq_wait_for_rate_limit: bool = Field(default=True, alias="GROQ_WAIT_FOR_RATE_LIMIT")
    groq_max_rate_limit_wait_seconds: float = Field(default=60.0, alias="GROQ_MAX_RATE_LIMIT_WAIT_SECONDS")
    groq_rate_limit_buffer_seconds: float = Field(default=1.0, alias="GROQ_RATE_LIMIT_BUFFER_SECONDS")

    # Optional task-specific Groq model groups
    groq_models_writing: Optional[str] = Field(default=None, alias="GROQ_MODELS_WRITING")
    groq_models_research: Optional[str] = Field(default=None, alias="GROQ_MODELS_RESEARCH")
    groq_models_planning: Optional[str] = Field(default=None, alias="GROQ_MODELS_PLANNING")

    # Ollama Local Fallback
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5:7b-instruct", alias="OLLAMA_MODEL")
    ollama_num_ctx: int = Field(default=8192, alias="OLLAMA_NUM_CTX")


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
    min_research_sources: int = Field(default=3, alias="MIN_RESEARCH_SOURCES")

    # Generation Defaults
    default_language: str = Field(default="en", alias="DEFAULT_LANGUAGE")
    default_target_pages: int = Field(default=60, alias="DEFAULT_TARGET_PAGES")
    default_max_chapters: int = Field(default=12, alias="DEFAULT_MAX_CHAPTERS")

    # Rendering
    pdf_output_dir: str = Field(default="./output", alias="PDF_OUTPUT_DIR")
    temp_render_dir: str = Field(default="./.tmp", alias="TEMP_RENDER_DIR")
    chromium_headless: bool = Field(default=True, alias="CHROMIUM_HEADLESS")

    # Cover dimensions & Design Variation
    cover_width: int = Field(default=1600, alias="COVER_WIDTH")
    cover_height: int = Field(default=2560, alias="COVER_HEIGHT")
    cover_temperature: float = Field(default=0.8, alias="COVER_TEMPERATURE")
    cover_variation_enabled: bool = Field(default=True, alias="COVER_VARIATION_ENABLED")
    cover_max_retries: int = Field(default=1, alias="COVER_MAX_RETRIES")

    def model_post_init(self, __context: Any) -> None:
        if self.app_env == "test":
            self.vasukisquare_mock_mode = True

    @property
    def has_web_search_provider(self) -> bool:
        """Check if at least one general web search provider is configured."""
        return bool(self.tavily_api_key or self.serper_api_key or self.brave_search_api_key)

    @property
    def active_search_provider_name(self) -> str:
        """Return the name of the active search provider."""
        if self.tavily_api_key:
            return "tavily"
        if self.serper_api_key:
            return "serper"
        if self.brave_search_api_key:
            return "brave"
        return "mock"

    def get_groq_models(self, group: Optional[str] = None) -> list[str]:
        """Parse and return ordered list of unique Groq models for a given task group or general pool."""
        raw_val = None
        if group:
            grp_lower = group.lower().strip()
            if grp_lower == "writing" and self.groq_models_writing:
                raw_val = self.groq_models_writing
            elif grp_lower == "research" and self.groq_models_research:
                raw_val = self.groq_models_research
            elif grp_lower == "planning" and self.groq_models_planning:
                raw_val = self.groq_models_planning

        if not raw_val:
            raw_val = self.groq_models or self.groq_model

        if not raw_val or not raw_val.strip():
            return ["openai/gpt-oss-120b"]

        # Split on commas, trim whitespace, ignore empty, deduplicate preserving order
        models: list[str] = []
        seen: set[str] = set()
        for item in raw_val.split(","):
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                models.append(cleaned)

        return models if models else ["openai/gpt-oss-120b"]

    def resolve_llm_provider(self) -> tuple[str, str, str]:
        """Resolve active LLM provider, active model, and rationale string.
        
        Returns:
            (provider_name, model_name, reason_description)
        """
        prov = (self.llm_provider or "auto").strip().lower()
        groq_models = self.get_groq_models()
        active_groq_model = groq_models[0]
        model_count_str = f" (pool of {len(groq_models)} models)" if len(groq_models) > 1 else ""

        if prov == "auto":
            if self.groq_api_key and self.groq_api_key.strip():
                return ("groq", active_groq_model, f"GROQ_API_KEY configured{model_count_str}")
            return ("ollama", self.ollama_model, "GROQ_API_KEY missing or empty")

        if prov == "groq":
            if not self.groq_api_key or not self.groq_api_key.strip():
                raise EnvironmentConfigurationError(
                    "LLM_PROVIDER is set to 'groq' but GROQ_API_KEY is missing or empty. "
                    "Set GROQ_API_KEY in .env/.env.local or set LLM_PROVIDER=auto / LLM_PROVIDER=ollama."
                )
            return ("groq", active_groq_model, f"Explicitly set via LLM_PROVIDER=groq{model_count_str}")

        if prov == "ollama":
            return ("ollama", self.ollama_model, "Explicitly set via LLM_PROVIDER=ollama")

        raise EnvironmentConfigurationError(
            f"Unsupported LLM_PROVIDER '{self.llm_provider}'. Supported values: 'auto', 'groq', 'ollama'."
        )


    def validate_production_environment(self) -> None:
        """Validate required configuration for production book generation."""
        if self.vasukisquare_mock_mode:
            return

        # 1. Search provider check
        if not self.has_web_search_provider:
            raise EnvironmentConfigurationError(
                "Production generation configuration check failed: missing Web Search Provider Key. "
                "Set TAVILY_API_KEY, SERPER_API_KEY, or BRAVE_SEARCH_API_KEY in .env/.env.local."
            )

        # 2. LLM Provider and Model Check
        provider, model, reason = self.resolve_llm_provider()

        if provider == "groq":
            if not self.groq_api_key or self.groq_api_key.startswith("gsk_test_key"):
                raise EnvironmentConfigurationError(
                    "Valid GROQ_API_KEY required when Groq is the active provider."
                )
        elif provider == "ollama":
            # Check Ollama server availability and model presence
            import httpx
            base_url = self.ollama_base_url.rstrip("/")
            try:
                resp = httpx.get(f"{base_url}/api/tags", timeout=5.0)
                if resp.status_code != 200:
                    raise EnvironmentConfigurationError(
                        f"Ollama server at {base_url} returned status code {resp.status_code}."
                    )
                models_data = resp.json().get("models", [])
                installed_model_names = [m.get("name", "") for m in models_data]
                # Match full name (e.g. qwen2.5:7b-instruct:latest or qwen2.5:7b-instruct)
                target_model = self.ollama_model.lower()
                matched = any(
                    target_model == m.lower()
                    or target_model == m.lower().split(":")[0]
                    or m.lower().startswith(target_model)
                    for m in installed_model_names
                )
                if not matched:
                    raise EnvironmentConfigurationError(
                        f"Configured Ollama model '{self.ollama_model}' is not installed.\n"
                        f"Installed models: {installed_model_names or 'None'}\n"
                        f"Run: ollama pull {self.ollama_model}"
                    )
            except Exception as e:
                if isinstance(e, EnvironmentConfigurationError):
                    raise
                raise EnvironmentConfigurationError(
                    f"Ollama was selected ({reason}), but the Ollama server is unavailable at {base_url}.\n"
                    f"Start Ollama and ensure the configured model exists:\n"
                    f"ollama pull {self.ollama_model}"
                ) from e


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()


def get_groq_models(group: Optional[str] = None) -> list[str]:
    """Convenience helper to retrieve configured Groq models."""
    return get_settings().get_groq_models(group)


