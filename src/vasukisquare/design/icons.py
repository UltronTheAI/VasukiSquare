"""Lucide icon handling and tokenized color resolution mapped from DESIGN.md."""

import html
from typing import Any, Optional, Union
from vasukisquare.design.tokens import ColorToken, validate_color_token, normalize_design_color
from vasukisquare.design.theme import Theme


class IconColorResolver:
    """Resolves semantic icon colors strictly from DESIGN.md tokens based on theme and role."""

    @staticmethod
    def resolve_color(theme: Theme = Theme.LIGHT, role: str = "primary") -> ColorToken:
        """Select an optimal ColorToken for an icon given chapter theme and semantic role."""
        if theme == Theme.DARK:
            if role == "primary":
                return ColorToken.BRAND_GREEN
            elif role == "accent-purple":
                return ColorToken.ACCENT_PURPLE
            elif role == "accent-orange":
                return ColorToken.ACCENT_ORANGE
            elif role == "muted":
                return ColorToken.ON_DARK_MUTED
            return ColorToken.ON_DARK
        else:
            if role == "primary":
                return ColorToken.BRAND_GREEN_DARK
            elif role == "accent-purple":
                return ColorToken.ACCENT_PURPLE
            elif role == "accent-orange":
                return ColorToken.ACCENT_ORANGE
            elif role == "muted":
                return ColorToken.MUTED
            return ColorToken.INK


class LucideIcon:
    """Lucide-compatible SVG icon representation enforcing DESIGN.md tokens."""

    DEFAULT_ICONS = {
        "book-open": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
        "bookmark": '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
        "file-text": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
        "layers": '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 12.5-8.58 3.91a2 2 0 0 1-1.66 0L2 12.5"/><path d="m22 17.5-8.58 3.91a2 2 0 0 1-1.66 0L2 17.5"/>',
        "cpu": '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>',
        "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
        "sparkles": '<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>',
        "compass": '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
        "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
        "code": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
        "terminal": '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>',
        "check-circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    }

    def __init__(
        self,
        name: str,
        color: Union[ColorToken, str] = ColorToken.BRAND_GREEN,
        size: int = 24,
        stroke_width: float = 2.0,
        custom_path: Optional[str] = None,
    ):
        self.name = name.strip().lower()
        self.color = normalize_design_color(color, fallback_token=ColorToken.BRAND_GREEN)
        self.size = size
        self.stroke_width = stroke_width
        self.custom_path = custom_path

    def get_inner_svg(self) -> str:
        """Get the SVG inner elements for the icon."""
        if self.custom_path:
            return self.custom_path
        if self.name in self.DEFAULT_ICONS:
            return self.DEFAULT_ICONS[self.name]
        # Generic fallback circle
        return '<circle cx="12" cy="12" r="10"/>'

    def to_svg(self) -> str:
        """Render complete SVG markup with design token styling."""
        inner = self.get_inner_svg()
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{self.size}" height="{self.size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{self.color.value}" stroke-width="{self.stroke_width}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'class="lucide lucide-{html.escape(self.name)}" data-token-color="{self.color.name}">'
            f'{inner}'
            f'</svg>'
        )


def render_lucide_icon(
    name: str,
    color: Union[ColorToken, str] = ColorToken.BRAND_GREEN,
    size: int = 24,
    stroke_width: float = 2.0,
) -> str:
    """Convenience helper to render a Lucide icon as SVG string."""
    icon = LucideIcon(name=name, color=color, size=size, stroke_width=stroke_width)
    return icon.to_svg()
