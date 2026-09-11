"""Structured rich text models, inline formatting parser, and HTML sanitizer for VasukiSquare."""

import html
import re
from typing import List, Literal, Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field

from vasukisquare.book.richtext import MarkType, RichSpan, RichParagraph

ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


class RichTextParser:
    """Parses markdown-like authoring strings into structured, typed RichSpan models."""

    TOKEN_PATTERNS = [
        ("bold_italic", re.compile(r"\*\*\*(?=\S)(.+?)(?<=\S)\*\*\*")),
        ("bold", re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")),
        ("italic", re.compile(r"\*(?=\S)(.+?)(?<=\S)\*")),
        ("inline_code", re.compile(r"`(?=\S)(.+?)(?<=\S)`")),
        ("strikethrough", re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")),
        ("highlight", re.compile(r"==(?=\S)(.+?)(?<=\S)==")),
        ("kbd", re.compile(r"<kbd>(.+?)</kbd>")),
        ("link", re.compile(r"\[(?P<link_text>[^\]]+)\]\((?P<link_href>[^\)]+)\)")),
    ]

    MASTER_REGEX = re.compile(
        r"(\*\*\*(?=\S).+?(?<=\S)\*\*\*)|"
        r"(\*\*(?=\S).+?(?<=\S)\*\*)|"
        r"(\*(?=\S).+?(?<=\S)\*)|"
        r"(`(?=\S).+?(?<=\S)`)|"
        r"(~~(?=\S).+?(?<=\S)~~)|"
        r"(==(?=\S).+?(?<=\S)==)|"
        r"(<kbd>.+?</kbd>)|"
        r"(\[[^\]]+\]\([^\)]+\))"
    )

    @classmethod
    def parse_inline_formatting(cls, text: str) -> List[RichSpan]:
        """Convert a string containing inline formatting tokens into a list of typed RichSpans."""
        if not text:
            return []

        spans: List[RichSpan] = []
        last_idx = 0

        for match in cls.MASTER_REGEX.finditer(text):
            start, end = match.span()
            if start > last_idx:
                plain_text = text[last_idx:start]
                if plain_text:
                    spans.append(RichSpan(text=plain_text))

            token = match.group(0)
            matched = False

            if token.startswith("***") and token.endswith("***"):
                spans.append(RichSpan(text=token[3:-3], marks=["bold_italic"]))
                matched = True
            elif token.startswith("**") and token.endswith("**"):
                spans.append(RichSpan(text=token[2:-2], marks=["bold"]))
                matched = True
            elif token.startswith("*") and token.endswith("*"):
                spans.append(RichSpan(text=token[1:-1], marks=["italic"]))
                matched = True
            elif token.startswith("`") and token.endswith("`"):
                spans.append(RichSpan(text=token[1:-1], marks=["inline_code"]))
                matched = True
            elif token.startswith("~~") and token.endswith("~~"):
                spans.append(RichSpan(text=token[2:-2], marks=["strikethrough"]))
                matched = True
            elif token.startswith("==") and token.endswith("=="):
                spans.append(RichSpan(text=token[2:-2], marks=["highlight"]))
                matched = True
            elif token.startswith("<kbd>") and token.endswith("</kbd>"):
                spans.append(RichSpan(text=token[5:-6], marks=["kbd"]))
                matched = True
            elif token.startswith("[") and "](" in token and token.endswith(")"):
                m_link = re.match(r"\[(?P<link_text>[^\]]+)\]\((?P<link_href>[^\)]+)\)", token)
                if m_link:
                    spans.append(
                        RichSpan(
                            text=m_link.group("link_text"),
                            marks=["link"],
                            href=m_link.group("link_href"),
                        )
                    )
                    matched = True

            if not matched:
                spans.append(RichSpan(text=token))

            last_idx = end

        if last_idx < len(text):
            remaining = text[last_idx:]
            if remaining:
                spans.append(RichSpan(text=remaining))

        return spans if spans else [RichSpan(text=text)]


class RichTextRenderer:
    """Sanitizes and renders RichSpan sequences into safe HTML tags."""

    @staticmethod
    def is_safe_url(url: str) -> bool:
        """Validate that a URL uses an approved protocol."""
        if not url:
            return False
        try:
            parsed = urlparse(url.strip())
            return parsed.scheme.lower() in ALLOWED_URL_SCHEMES
        except Exception:
            return False

    @classmethod
    def render_span(cls, span: RichSpan) -> str:
        """Render a single RichSpan to sanitized HTML with appropriate tags."""
        escaped_text = html.escape(span.text)
        output = escaped_text

        for mark in span.marks:
            if mark == "bold_italic":
                output = f"<strong><em>{output}</em></strong>"
            elif mark == "bold":
                output = f"<strong>{output}</strong>"
            elif mark == "italic":
                output = f"<em>{output}</em>"
            elif mark == "inline_code":
                output = f'<code class="rich-code">{output}</code>'
            elif mark == "strikethrough":
                output = f"<s>{output}</s>"
            elif mark == "highlight":
                output = f'<mark class="rich-highlight">{output}</mark>'
            elif mark == "superscript":
                output = f"<sup>{output}</sup>"
            elif mark == "subscript":
                output = f"<sub>{output}</sub>"
            elif mark == "kbd":
                output = f'<kbd class="rich-kbd">{output}</kbd>'

        if span.href or "link" in span.marks:
            if span.href and cls.is_safe_url(span.href):
                clean_href = html.escape(span.href)
                output = f'<a class="rich-link" href="{clean_href}" target="_blank" rel="noopener noreferrer">{output}</a>'
            else:
                output = f'<a class="rich-link" href="#" target="_blank" rel="noopener noreferrer">{output}</a>'

        return output

    @classmethod
    def render_spans(cls, spans: List[RichSpan]) -> str:
        """Render a list of RichSpans to HTML."""
        return "".join(cls.render_span(s) for s in spans)


    @classmethod
    def render_text_or_markdown(cls, text: str) -> str:
        """Parse inline formatting on the fly and render safe HTML."""
        if not text:
            return ""
        spans = RichTextParser.parse_inline_formatting(text)
        return cls.render_spans(spans)
