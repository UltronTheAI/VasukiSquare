"""Validated data models and schema definitions for VasukiSquare publication and branding configuration."""

from typing import Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


class BrandingConfig(BaseModel):
    """Branding metadata for publications, publisher imprints, and visual identities."""

    author_name: str = Field(
        ...,
        description="Public author or editorial team identity displayed on publication covers and imprints.",
    )
    publication_name: str = Field(
        ...,
        description="Publisher or publication imprint name (e.g. 'Vasuki Publishing' or 'Northstar Books').",
    )
    company_name: str = Field(
        ...,
        description="Parent company or publishing entity name (e.g. 'VasukiSquare' or 'Northstar Media LLC').",
    )
    engine_name: str = Field(
        ...,
        description="Formal engine or publishing system name (e.g. 'VasukiSquare AI Publishing Engine').",
    )
    website: Optional[str] = Field(
        default="https://vasukisquare.cc",
        description="Optional publisher website or landing URL. May be set to '' to omit website completely.",
    )

    @field_validator("author_name", "publication_name", "company_name", "engine_name")
    @classmethod
    def validate_non_empty_string(cls, v: str, info) -> str:
        if v is None or not isinstance(v, str) or not v.strip():
            raise ValueError(f"'{info.field_name}' must be a non-empty string.")
        return v.strip()

    @field_validator("website")
    @classmethod
    def validate_optional_website(cls, v: Optional[str]) -> str:
        if v is None:
            return ""
        v = v.strip()
        if not v:
            return ""
        # Validate URL structure if non-empty
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            # Check if domain-like (e.g. northstarbooks.com) or http/https URL
            if "." not in v:
                raise ValueError(
                    f"Invalid website URL format '{v}'. Expected a valid URL (e.g. 'https://example.com') or empty string ''."
                )
        return v


class EditionConfig(BaseModel):
    """Edition and publishing date metadata."""

    name: str = Field(
        ...,
        description="Edition designation label (e.g. 'FIRST EDITION' or 'SECOND EDITION').",
    )
    year: int = Field(
        ...,
        description="Publication calendar year (e.g. 2026).",
    )

    @field_validator("name")
    @classmethod
    def validate_edition_name(cls, v: str) -> str:
        if v is None or not isinstance(v, str) or not v.strip():
            raise ValueError("'name' must be a non-empty string.")
        return v.strip()

    @field_validator("year")
    @classmethod
    def validate_edition_year(cls, v: int) -> int:
        if v is None or not isinstance(v, int) or isinstance(v, bool):
            raise ValueError("'year' must be an integer.")
        if v < 1000 or v > 9999:
            raise ValueError(f"Invalid publication year {v}. Expected 4-digit year (1000-9999).")
        return v


class CopyrightConfig(BaseModel):
    """Copyright holder and rights reservation metadata."""

    holder: str = Field(
        ...,
        description="Copyright holder entity or legal name (e.g. 'Vasuki Publishing' or 'Northstar Media LLC').",
    )
    all_rights_reserved: bool = Field(
        default=True,
        description="Whether 'All Rights Reserved' legal reservation notice is active.",
    )

    @field_validator("holder")
    @classmethod
    def validate_holder(cls, v: str) -> str:
        if v is None or not isinstance(v, str) or not v.strip():
            raise ValueError("'holder' must be a non-empty string.")
        return v.strip()


class BookDefaultsConfig(BaseModel):
    """Default parameters for generated books."""

    language: str = Field(
        default="English",
        description="Default natural language for generated publication content.",
    )

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v is None or not isinstance(v, str) or not v.strip():
            raise ValueError("'language' must be a non-empty string.")
        return v.strip()


class AppConfig(BaseModel):
    """Root application and publication branding configuration model loaded from ./config.json."""

    branding: BrandingConfig
    edition: EditionConfig
    copyright: CopyrightConfig
    book_defaults: BookDefaultsConfig = Field(default_factory=BookDefaultsConfig)

