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

        if style in ("orbital_rings", "structural_rings"):
            return CoverPatternGenerator._render_orbital_rings(width, height, accent_color, secondary_color)
        elif style in ("tech_matrix", "abstract_matrix", "matrix"):
            return CoverPatternGenerator._render_tech_matrix(width, height, accent_color, secondary_color)
        elif style in ("layered_bands", "angular_lines"):
            return CoverPatternGenerator._render_layered_bands(width, height, accent_color, secondary_color)
        elif style in ("abstract_mesh", "neural_mesh"):
            return CoverPatternGenerator._render_abstract_mesh(width, height, accent_color, secondary_color)
        elif style in ("database_nodes", "storage_nodes", "b_tree"):
            return CoverPatternGenerator._render_database_nodes(width, height, accent_color, secondary_color)
        elif style in ("circuit_grid", "system_topology"):
            return CoverPatternGenerator._render_circuit_grid(width, height, accent_color, secondary_color)
        elif style in ("dense_blueprint", "blueprint_grid"):
            return CoverPatternGenerator._render_dense_blueprint(width, height, accent_color, secondary_color)
        elif style in ("code_terminal_frame", "syntax_brackets"):
            return CoverPatternGenerator._render_code_terminal_frame(width, height, accent_color, secondary_color)
        elif style in ("orthogonal_axes", "abstract_lines"):
            return CoverPatternGenerator._render_orthogonal_axes(width, height, accent_color, secondary_color)
        elif style in ("none", "clean"):
            return ""
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
    def _render_database_nodes(w: int, h: int, accent: str, sec: str) -> str:
        """Render interconnected database cluster/tree nodes and storage blocks."""
        elements = []
        cx, cy = int(w * 0.55), int(h * 0.38)
        
        # Draw node layers (Root -> Leaves)
        nodes = [
            (cx, cy - 180, 36),
            (cx - 240, cy, 28),
            (cx + 240, cy, 28),
            (cx - 360, cy + 190, 22),
            (cx - 120, cy + 190, 22),
            (cx + 120, cy + 190, 22),
            (cx + 360, cy + 190, 22),
        ]
        
        # Connections
        lines = [
            (nodes[0], nodes[1]),
            (nodes[0], nodes[2]),
            (nodes[1], nodes[3]),
            (nodes[1], nodes[4]),
            (nodes[2], nodes[5]),
            (nodes[2], nodes[6]),
        ]
        
        for (x1, y1, _), (x2, y2, _) in lines:
            elements.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{sec}" stroke-width="2" stroke-dasharray="6 4" opacity="0.5"/>'
            )
            
        for idx, (x, y, r) in enumerate(nodes):
            color = accent if idx % 2 == 0 else sec
            elements.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{color}" stroke-width="2" opacity="0.8"/>')
            elements.append(f'<circle cx="{x}" cy="{y}" r="{r//3}" fill="{color}" opacity="0.6"/>')

        # Storage row blocks at lower background
        for i in range(5):
            y_pos = int(h * 0.65) + (i * 45)
            elements.append(
                f'<rect x="{w*0.1}" y="{y_pos}" width="{w*0.8}" height="28" rx="4" fill="none" stroke="{sec}" stroke-width="1.2" opacity="{0.2 + (i*0.08)}"/>'
            )
            elements.append(
                f'<rect x="{w*0.12}" y="{y_pos + 6}" width="40" height="16" rx="2" fill="{accent}" opacity="{0.4 + (i*0.1)}"/>'
            )

        return "".join(elements)

    @staticmethod
    def _render_circuit_grid(w: int, h: int, accent: str, sec: str) -> str:
        """Render system bus topology, IC lines, and terminal nodes."""
        elements = []
        step_x = 140
        step_y = 120
        
        # Orthogonal trace paths
        traces = [
            f"M 0 {int(h*0.2)} H {int(w*0.4)} V {int(h*0.35)} H {w}",
            f"M {int(w*0.2)} 0 V {int(h*0.45)} H {int(w*0.7)} V {h}",
            f"M {w} {int(h*0.55)} H {int(w*0.6)} V {int(h*0.75)} H 0",
            f"M {int(w*0.8)} 0 V {int(h*0.3)} H {int(w*0.5)} V {int(h*0.6)}",
        ]
        for t in traces:
            elements.append(f'<path d="{t}" fill="none" stroke="{sec}" stroke-width="2" opacity="0.45"/>')
            
        # Micro nodes at intersections
        for x in range(100, w, step_x):
            for y in range(150, int(h*0.75), step_y):
                if (x + y) % 3 == 0:
                    elements.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{accent}" opacity="0.6"/>')
                    elements.append(f'<circle cx="{x}" cy="{y}" r="9" fill="none" stroke="{accent}" stroke-width="1" opacity="0.3"/>')
                elif (x * y) % 4 == 0:
                    elements.append(f'<rect x="{x-5}" y="{y-5}" width="10" height="10" fill="none" stroke="{sec}" stroke-width="1.5" opacity="0.4"/>')

        return "".join(elements)

    @staticmethod
    def _render_dense_blueprint(w: int, h: int, accent: str, sec: str) -> str:
        """Render dense engineering blueprint grid with coordinate marks."""
        elements = []
        grid_step = 60
        
        # Fine grid lines
        for x in range(0, w, grid_step):
            alpha = 0.3 if x % (grid_step * 3) == 0 else 0.12
            elements.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{h}" stroke="{sec}" stroke-width="1" opacity="{alpha}"/>')
            
        for y in range(0, h, grid_step):
            alpha = 0.3 if y % (grid_step * 3) == 0 else 0.12
            elements.append(f'<line x1="0" y1="{y}" x2="{w}" y2="{y}" stroke="{sec}" stroke-width="1" opacity="{alpha}"/>')

        # Corner technical marks
        elements.append(f'<rect x="40" y="40" width="80" height="80" fill="none" stroke="{accent}" stroke-width="2" opacity="0.7"/>')
        elements.append(f'<rect x="{w-120}" y="40" width="80" height="80" fill="none" stroke="{accent}" stroke-width="2" opacity="0.7"/>')
        elements.append(f'<circle cx="{w//2}" cy="{h//2}" r="320" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="12 8" opacity="0.4"/>')

        return "".join(elements)

    @staticmethod
    def _render_code_terminal_frame(w: int, h: int, accent: str, sec: str) -> str:
        """Render subtle syntax bracket frames and terminal geometry."""
        elements = []
        cx, cy = w // 2, int(h * 0.45)
        
        # Giant stylized bracket shapes
        elements.append(
            f'<path d="M {cx - 380} {cy - 260} H {cx - 480} V {cy + 260} H {cx - 380}" fill="none" stroke="{sec}" stroke-width="3" opacity="0.4"/>'
        )
        elements.append(
            f'<path d="M {cx + 380} {cy - 260} H {cx + 480} V {cy + 260} H {cx + 380}" fill="none" stroke="{accent}" stroke-width="3" opacity="0.55"/>'
        )
        # Slashes and code runes
        elements.append(
            f'<line x1="{cx - 80}" y1="{cy + 220}" x2="{cx + 80}" y2="{cy - 220}" stroke="{accent}" stroke-width="2.5" opacity="0.6"/>'
        )
        return "".join(elements)

    @staticmethod
    def _render_orthogonal_axes(w: int, h: int, accent: str, sec: str) -> str:
        """Render clean minimalist orthogonal axis crosshairs and metric divisions."""
        elements = []
        cx = int(w * 0.25)
        cy = int(h * 0.6)
        
        # Axis lines
        elements.append(f'<line x1="60" y1="{cy}" x2="{w - 60}" y2="{cy}" stroke="{sec}" stroke-width="1.5" opacity="0.5"/>')
        elements.append(f'<line x1="{cx}" y1="80" x2="{cx}" y2="{h - 80}" stroke="{sec}" stroke-width="1.5" opacity="0.5"/>')
        
        # Axis ticks
        for x in range(100, w - 80, 80):
            elements.append(f'<line x1="{x}" y1="{cy - 6}" x2="{x}" y2="{cy + 6}" stroke="{accent}" stroke-width="1.5" opacity="0.6"/>')
        for y in range(120, h - 100, 80):
            elements.append(f'<line x1="{cx - 6}" y1="{y}" x2="{cx + 6}" y2="{y}" stroke="{accent}" stroke-width="1.5" opacity="0.6"/>')

        elements.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="{accent}"/>')
        return "".join(elements)

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

