"""URL normalization and source title extractor for citations and web links."""

import re
from typing import Optional
from urllib.parse import parse_qs, unquote, unquote_plus, urlparse
from pydantic import BaseModel, Field


class NormalizedSource(BaseModel):
    """Normalized metadata for a web source citation."""

    url: str
    display_title: str
    domain: str
    publisher: str
    is_search_url: bool = False
    clean_query: Optional[str] = None


class UrlNormalizer:
    """Sanitizes raw URLs, extracts clean titles, and normalizes search-query links."""

    SEARCH_DOMAINS = {
        "google.com",
        "www.google.com",
        "bing.com",
        "www.bing.com",
        "search.yahoo.com",
        "duckduckgo.com",
        "example.com",
    }

    KNOWN_PUBLISHERS = {
        "en.wikipedia.org": "Wikipedia",
        "wikipedia.org": "Wikipedia",
        "postgresql.org": "PostgreSQL Documentation",
        "www.postgresql.org": "PostgreSQL Documentation",
        "docs.python.org": "Python Documentation",
        "rust-lang.org": "Rust Documentation",
        "doc.rust-lang.org": "Rust Documentation",
        "github.com": "GitHub",
        "arxiv.org": "arXiv Research",
        "acm.org": "ACM Digital Library",
        "ieee.org": "IEEE Xplore",
        "mongodb.com": "MongoDB Documentation",
        "redis.io": "Redis Documentation",
    }

    @classmethod
    def clean_text_artifacts(cls, text: str) -> str:
        """Strip percent encoding, URL query keys, plus signs, and file extension artifacts from text."""
        if not text:
            return ""

        # Decode percent-encoding
        decoded = unquote_plus(text)

        # Remove leading search parameter keys like q=, query=, search=, p=, url=
        decoded = re.sub(r"^(?:https?://[^/]+/search\?)?(?:q|query|search|p|url|r)=+", "", decoded, flags=re.IGNORECASE)
        # Remove trailing tracking params
        decoded = re.sub(r"&(?:utm_[^=]+|hl|ie|oe|oq|source)=[^&]*", "", decoded, flags=re.IGNORECASE)
        # Replace pluses and multiple underscores/dashes with single space
        decoded = decoded.replace("+", " ").replace("_", " ")
        # Strip trailing punctuation/whitespace
        decoded = re.sub(r"\s+", " ", decoded).strip()

        return decoded

    @classmethod
    def normalize_source(
        cls,
        url: str,
        title: Optional[str] = None,
        publisher: Optional[str] = None,
    ) -> NormalizedSource:
        """Parse raw URL and title, returning sanitized source citation metadata."""
        raw_url = (url or "").strip()
        parsed = urlparse(raw_url)
        domain = parsed.netloc.lower() or "external.link"

        is_search = any(sd in domain for sd in cls.SEARCH_DOMAINS) or "search" in parsed.path.lower()
        clean_query = None

        # Extract search query if present
        if parsed.query:
            qs = parse_qs(parsed.query)
            for qkey in ("q", "query", "p", "search", "term"):
                if qkey in qs and qs[qkey]:
                    clean_query = cls.clean_text_artifacts(qs[qkey][0])
                    break

        # Resolve clean display title
        display_title = ""

        # 1. Clean existing provided title if valid and not a raw URL / query
        if title:
            cleaned_title = cls.clean_text_artifacts(title)
            # Check if title was simply "Search Result for ..." or "q=..."
            if cleaned_title.lower().startswith("search result for "):
                cleaned_title = cleaned_title[18:].strip()
            if cleaned_title and not cleaned_title.startswith("http"):
                display_title = cleaned_title

        # 2. If title still empty or was a search query, use query or path
        if not display_title:
            if clean_query:
                # Format clean query as a title
                display_title = clean_query.title()
            elif parsed.path and parsed.path != "/":
                # Derive title from last path segment
                slug = parsed.path.rstrip("/").split("/")[-1]
                slug = slug.replace(".html", "").replace(".htm", "").replace(".php", "")
                display_title = cls.clean_text_artifacts(slug).title()
            else:
                display_title = domain.capitalize()

        # Resolve clean publisher
        resolved_pub = publisher
        if not resolved_pub or resolved_pub.lower() in ("search engine", "web search", "search"):
            resolved_pub = cls.KNOWN_PUBLISHERS.get(domain)
            if not resolved_pub:
                # Format domain as publisher name
                parts = domain.split(".")
                if len(parts) >= 2 and parts[-2] not in ("co", "com", "org", "gov", "edu"):
                    resolved_pub = parts[-2].capitalize()
                else:
                    resolved_pub = domain


        # Ensure title does not contain encoded query syntax
        display_title = cls.clean_text_artifacts(display_title)
        if len(display_title) > 80:
            display_title = display_title[:77] + "..."

        normalized_url = raw_url
        if is_search:
            if domain in cls.SEARCH_DOMAINS:
                normalized_url = f"https://{domain}/"
            elif parsed.query:
                normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        return NormalizedSource(
            url=normalized_url,
            display_title=display_title or "Reference Source",
            domain=domain,
            publisher=resolved_pub or "Primary Source",
            is_search_url=is_search,
            clean_query=clean_query,
        )

