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
        "file-code": '<path d="M10 12.5 8 15l2 2.5"/><path d="m14 12.5 2 2.5-2 2.5"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/>',
        "layers": '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 12.5-8.58 3.91a2 2 0 0 1-1.66 0L2 12.5"/><path d="m22 17.5-8.58 3.91a2 2 0 0 1-1.66 0L2 17.5"/>',
        "cpu": '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>',
        "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
        "server": '<rect width="20" height="8" x="2" y="2" rx="2" ry="2"/><rect width="20" height="8" x="2" y="14" rx="2" ry="2"/><line x1="6" x2="6.01" y1="6" y2="6"/><line x1="6" x2="6.01" y1="18" y2="18"/>',
        "sparkles": '<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>',
        "compass": '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
        "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
        "code": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
        "code-2": '<path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/>',
        "braces": '<path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5c0 1.1.9 2 2 2h1"/><path d="M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"/>',
        "terminal": '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>',
        "square-terminal": '<path d="m7 11 2-2-2-2"/><path d="M11 13h4"/><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>',
        "check-circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
        "check": '<polyline points="20 6 9 17 4 12"/>',
        "x": '<line x1="18" x2="6" y1="6" y2="18"/><line x1="6" x2="18" y1="6" y2="18"/>',
        "shield-check": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
        "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
        "lock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
        "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
        "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
        "gauge": '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
        "network": '<rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/>',
        "workflow": '<rect width="8" height="8" x="3" y="3" rx="2"/><path d="M7 11v4a2 2 0 0 0 2 2h4"/><rect width="8" height="8" x="13" y="13" rx="2"/>',
        "lightbulb": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
        "alert-triangle": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
        "alert-circle": '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
        "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
        "heart": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
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
        if isinstance(color, str):
            self.color = validate_color_token(color)
        else:
            self.color = color
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


ICON_MAP = {
    "database": ["database", "server", "layers"],
    "code": ["code", "code-2", "braces", "file-code", "cpu"],
    "terminal": ["terminal", "square-terminal", "cpu", "code"],
    "network": ["network", "workflow", "globe", "layers"],
    "performance": ["gauge", "activity", "zap", "cpu"],
    "security": ["shield-check", "lock", "shield"],
    "architecture": ["layers", "network", "workflow", "compass"],
    "cloud": ["globe", "layers", "server", "network"],
    "ai": ["sparkles", "cpu", "layers"],
}


def resolve_topic_decorative_icon(topic: str, context: str = "") -> str:
    """Deterministically resolve a subtle topic-related icon from Python icon mapping."""
    combined = f"{topic} {context}".lower()
    
    if any(k in combined for k in ["database", "storage", "table", "collection", "crud", "query", "lioran", "sql"]):
        return ICON_MAP["database"][(len(combined)) % len(ICON_MAP["database"])]
    elif any(k in combined for k in ["terminal", "cli", "shell", "bash", "command", "install", "run"]):
        return ICON_MAP["terminal"][(len(combined)) % len(ICON_MAP["terminal"])]
    elif any(k in combined for k in ["network", "cluster", "distributed", "protocol", "http", "api"]):
        return ICON_MAP["network"][(len(combined)) % len(ICON_MAP["network"])]
    elif any(k in combined for k in ["performance", "benchmark", "latency", "throughput", "speed", "metric"]):
        return ICON_MAP["performance"][(len(combined)) % len(ICON_MAP["performance"])]
    elif any(k in combined for k in ["security", "auth", "permission", "crypto", "safe", "lock"]):
        return ICON_MAP["security"][(len(combined)) % len(ICON_MAP["security"])]
    elif any(k in combined for k in ["architecture", "design", "system", "component", "pattern"]):
        return ICON_MAP["architecture"][(len(combined)) % len(ICON_MAP["architecture"])]
    elif any(k in combined for k in ["ai", "model", "neural", "prompt", "learning", "intelligence"]):
        return ICON_MAP["ai"][(len(combined)) % len(ICON_MAP["ai"])]
    elif any(k in combined for k in ["code", "function", "class", "syntax", "python", "typescript", "rust", "go"]):
        return ICON_MAP["code"][(len(combined)) % len(ICON_MAP["code"])]
    
    return "compass"


def render_lucide_icon(
    name: str,
    color: Union[ColorToken, str] = ColorToken.BRAND_GREEN,
    size: int = 24,
    stroke_width: float = 2.0,
) -> str:
    """Convenience helper to render a Lucide icon as SVG string."""
    icon = LucideIcon(name=name, color=color, size=size, stroke_width=stroke_width)
    return icon.to_svg()
