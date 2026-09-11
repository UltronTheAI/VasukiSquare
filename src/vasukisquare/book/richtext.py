"""Structured domain models for rich text formatting in VasukiSquare books."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

MarkType = Literal[
    "bold",
    "italic",
    "bold_italic",
    "inline_code",
    "strikethrough",
    "highlight",
    "superscript",
    "subscript",
    "kbd",
    "link",
]


class RichSpan(BaseModel):
    """Represents a discrete formatted text segment with semantic formatting marks."""

    text: str
    marks: List[MarkType] = Field(default_factory=list)
    href: Optional[str] = None

    def is_plain(self) -> bool:
        return not self.marks and not self.href


class RichParagraph(BaseModel):
    """Container for a sequence of RichSpans representing a single paragraph or heading line."""

    spans: List[RichSpan] = Field(default_factory=list)

