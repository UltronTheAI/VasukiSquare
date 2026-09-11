"""Procedural abstract SVG pattern and geometric graphic generators for book covers."""

import math
from typing import Tuple
from vasukisquare.design.tokens import ColorToken, validate_color_token


class CoverPatternGenerator:
    """Generates geometric and abstract SVG backgrounds bound strictly to DESIGN.md tokens."""

    @staticmethod
    def generate_pattern(
        style: str,
        accent_color: str = ColorToken.BRAND_GREEN.value,
        secondary_color: str = ColorToken.BRAND_TEAL.value,
        canvas_size: Tuple[int, int] = (1600, 2560),
    ) -> str:
        """Render parametric SVG markup for the specified layout style."""
        validate_color_token(accent_color)
        validate_color_token(secondary_color)
        width, height = canvas_size

        if style == "orbital_rings":
            return CoverPatternGenerator._render_orbital_rings(width, height, accent_color, secondary_color)
        elif style == "tech_matrix":
            return CoverPatternGenerator._render_tech_matrix(width, height, accent_color, secondary_color)
        elif style == "layered_bands":
            return CoverPatternGenerator._render_layered_bands(width, height, accent_color, secondary_color)
        elif style == "abstract_mesh":
            return CoverPatternGenerator._render_abstract_mesh(width, height, accent_color, secondary_color)
        else:
            return CoverPatternGenerator._render_minimal_geometric(width, height, accent_color, secondary_color)

    @staticmethod
    def _render_orbital_rings(w: int, h: int, accent: str, sec: str) -> str:
        cx, cy = w // 2, int(h * 0.42)
        rings = []
        for r in [220, 360, 520, 680, 840]:
            rings.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{sec}" stroke-width="1.5" stroke-dasharray="8 6" opacity="0.45"/>'
            )
        rings.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="600" ry="240" fill="none" stroke="{accent}" stroke-width="2.5" transform="rotate(-25 {cx} {cy})" opacity="0.7"/>'
        )
        rings.append(
            f'<circle cx="{cx + 380}" cy="{cy - 160}" r="12" fill="{accent}"/>'
        )
        return "".join(rings)

    @staticmethod
    def _render_tech_matrix(w: int, h: int, accent: str, sec: str) -> str:
        elements = []
        step = 80
        for x_idx, x in enumerate(range(120, w - 120, step)):
            for y_idx, y in enumerate(range(160, int(h * 0.7), step)):
                if (x_idx + y_idx) % 4 == 0:
                    elements.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{accent}" opacity="0.6"/>')
                elif (x_idx * y_idx) % 5 == 0:
                    elements.append(f'<rect x="{x-4}" y="{y-4}" width="8" height="8" fill="none" stroke="{sec}" stroke-width="1" opacity="0.35"/>')
                else:
                    elements.append(f'<circle cx="{x}" cy="{y}" r="1.5" fill="{sec}" opacity="0.2"/>')
        return "".join(elements)

    @staticmethod
    def _render_layered_bands(w: int, h: int, accent: str, sec: str) -> str:
        bands = []
        for i, offset in enumerate([200, 400, 600, 800]):
            alpha = 0.2 + (i * 0.1)
            bands.append(
                f'<path d="M -100 {h - offset} Q {w // 2} {h - offset - 300} {w + 100} {h - offset + 100}" '
                f'fill="none" stroke="{accent if i % 2 == 0 else sec}" stroke-width="{3 + i}" opacity="{alpha}"/>'
            )
        return "".join(bands)

    @staticmethod
    def _render_abstract_mesh(w: int, h: int, accent: str, sec: str) -> str:
        cx, cy = w // 2, int(h * 0.44)
        polygons = []
        points = []
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            px = cx + int(360 * math.cos(rad))
            py = cy + int(360 * math.sin(rad))
            points.append((px, py))
            polygons.append(f'<line x1="{cx}" y1="{cy}" x2="{px}" y2="{py}" stroke="{sec}" stroke-width="1.5" opacity="0.4"/>')

        for i in range(len(points)):
            p1 = points[i]
            p2 = points[(i + 1) % len(points)]
            polygons.append(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="{accent}" stroke-width="2" opacity="0.65"/>')
        return "".join(polygons)

    @staticmethod
    def _render_minimal_geometric(w: int, h: int, accent: str, sec: str) -> str:
        cx, cy = w // 2, int(h * 0.42)
        return (
            f'<rect x="{cx - 300}" y="{cy - 300}" width="600" height="600" fill="none" stroke="{sec}" stroke-width="2" opacity="0.35" transform="rotate(45 {cx} {cy})"/>'
            f'<circle cx="{cx}" cy="{cy}" r="380" fill="none" stroke="{accent}" stroke-width="2" opacity="0.6"/>'
            f'<circle cx="{cx}" cy="{cy}" r="6" fill="{accent}"/>'
        )

