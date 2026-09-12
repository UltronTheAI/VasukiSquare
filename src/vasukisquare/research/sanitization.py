"""Source sanitization, MediaWiki/Wikipedia template stripping, and text cleaner for research ingestion."""

import html
import re
from typing import List, Tuple


# Regex patterns for stripping MediaWiki / Wikipedia editing markup
WIKIPEDIA_MARKUP_PATTERNS = [
    r"\{\{Cite[^\}]*\}\}",                     # {{Cite web ...}}, {{Cite book ...}}
    r"\{\{[^\}]*\}\}",                          # Any general {{ ... }} template
    r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]",          # [[Link target|Display text]] -> Display text
    r"\[\[[^\]]*\]\]",                          # Stray [[...]]
    r"&lt;ref[^&]*&gt;.*?&lt;/ref&gt;",        # &lt;ref&gt;...&lt;/ref&gt;
    r"&lt;ref[^/]*?/&gt;",                      # &lt;ref ... /&gt;
    r"<ref[^>]*>.*?</ref>",                     # <ref>...</ref>
    r"<ref[^/]*?/>",                            # <ref ... />
    r"&lt;!--.*?--&gt;",                        # Comments &lt;!-- ... --&gt;
    r"<!--.*?-->",                              # Comments <!-- ... -->
    r"__TOC__",                                 # Table of contents marker
    r"__NOTOC__",                               # No table of contents marker
    r"&lt;/?gallery.*?&gt;",                    # Gallery tags
    r"&lt;/?math.*?&gt;",                       # Math tags
    r"&lt;/?code.*?&gt;",                       # Code tags
    r"&lt;/?span.*?&gt;",                       # Span tags
    r"&lt;/?div.*?&gt;",                        # Div tags
]

# UI / Scraper garbage strings to strip
SCRAPER_BOILERPLATE_PATTERNS = [
    r"(?i)\bjump to content\b",
    r"(?i)\bjump to navigation\b",
    r"(?i)\bfrom wikipedia, the free encyclopedia\b",
    r"(?i)\bfrom wikipedia\b",
    r"(?i)\bedit section\b",
    r"(?i)\bedit this page\b",
    r"(?i)\bcookie (?:policy|preferences|settings|notice|consent)\b",
    r"(?i)\baccept (?:all )?cookies\b",
    r"(?i)\bsign up for (?:our )?newsletter\b",
    r"(?i)\bsubscribe to (?:our )?newsletter\b",
    r"(?i)\ball rights reserved\b",
    r"(?i)\bprivacy policy\b",
    r"(?i)\bterms of service\b",
    r"(?i)\bshare on (?:twitter|facebook|linkedin|reddit|x)\b",
    r"(?i)\bfollow us on\b",
    r"(?i)\bread more:\b",
    r"(?i)\brelated articles?\b",
    r"(?i)\btable of contents\b",
]

# Obvious source title SEO suffixes to strip when extracting clean topics
SEO_TITLE_SUFFIX_PATTERNS = [
    r"\s*-\s*Wikipedia(?:\s.*)?$",
    r"\s*-\s*DEV Community(?:\s.*)?$",
    r"\s*-\s*Uvik Software(?:\s.*)?$",
    r"\s*-\s*Python\.org(?:\s.*)?$",
    r"\s*-\s*GeeksforGeeks(?:\s.*)?$",
    r"\s*-\s*W3Schools(?:\s.*)?$",
    r"\s*-\s*Medium(?:\s.*)?$",
    r"\s*-\s*FreeCodeCamp(?:\s.*)?$",
    r"\s*\|\s*.*$",                            # Suffix after pipe: "Title | Company"
    r"\s*-\s*(?:Complete|Beginner|Step-by-Step|Ultimate) Guide\s*$",
    r"\s*in \d{4}\s*$",                        # "in 2026", "in 2025"
]


def clean_source_title(title: str) -> str:
    """Clean SEO phrases, company names, year stamps, and domain artifacts from article titles."""
    if not title:
        return "Untitled Source"

    cleaned = title.strip()
    for pat in SEO_TITLE_SUFFIX_PATTERNS:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    # Decode HTML entities
    cleaned = html.unescape(cleaned)
    # Remove leading/trailing quotes
    cleaned = cleaned.strip('"\'`')
    return cleaned if cleaned else "Untitled Source"


def sanitize_source_text(raw_text: str) -> str:
    """Sanitize scraped web / Wikipedia text by removing editing markup, boilerplate, and HTML entities."""
    if not raw_text:
        return ""

    text = raw_text

    # 1. Unescape HTML entities first so markup patterns match reliably
    text = html.unescape(text)

    # 2. Strip Wikipedia / MediaWiki markup patterns
    for pat in WIKIPEDIA_MARKUP_PATTERNS:
        text = re.sub(pat, " ", text, flags=re.DOTALL | re.IGNORECASE)

    # 3. Strip scraper boilerplate
    for pat in SCRAPER_BOILERPLATE_PATTERNS:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE)

    # 4. Remove residual HTML tags if any
    text = re.sub(r"<[^>]+>", " ", text)

    # 5. Remove Wikipedia section header indicators like "== History ==" or "=== Syntax ==="
    text = re.sub(r"={2,}\s*([^=]+?)\s*={2,}", r"\1.", text)

    # 6. Normalize whitespace and newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = text.strip()

    return text


def validate_source_cleanliness(text: str) -> Tuple[bool, List[str]]:
    """Validate that text is clean and free of raw Wiki markup or scraper artifacts."""
    issues = []
    if not text:
        return True, []

    if re.search(r"\{\{Cite", text, re.IGNORECASE):
        issues.append("Contains uncleaned {{Cite ...}} markup")
    if re.search(r"\[\[.*?\|.*?\]\]", text):
        issues.append("Contains uncleaned [[link|text]] MediaWiki markup")
    if re.search(r"&lt;/ref&gt;|<ref>", text, re.IGNORECASE):
        issues.append("Contains uncleaned citation reference tags")
    if re.search(r"(?i)jump to content", text):
        issues.append("Contains 'Jump to content' navigation artifact")
    if re.search(r"(?i)from wikipedia, the free encyclopedia", text):
        issues.append("Contains Wikipedia header boilerplate")

    return len(issues) == 0, issues

