"""Procedural monochrome SVG vector primitives for VasukiSquare cover art system."""

import math
import random
from typing import Dict, List, Optional, Tuple


def _poly_to_svg(points: List[Tuple[float, float]], fill: str, opacity: float = 1.0) -> str:
    pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon points="{pts_str}" fill="{fill}" fill-opacity="{opacity:.2f}" />'


def _path_to_svg(d: str, fill: str = "none", stroke: str = "none", stroke_width: float = 1.0, opacity: float = 1.0) -> str:
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" opacity="{opacity:.2f}" />'


def generate_mountain_scenery(
    rng: random.Random,
    canvas_size: Tuple[int, int] = (1600, 2560),
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Monochrome layered mountain ridge polygons, peaks, and sun/moon."""
    w, h = canvas_size
    num_layers = rng.randint(3, 5)
    sun_x = rng.choice([w * 0.25, w * 0.5, w * 0.75])
    sun_y = h * rng.uniform(0.38, 0.52)
    sun_r = rng.uniform(48, 80)
    is_moon = rng.random() > 0.65

    elements = []

    # Celestial Body (Sun/Moon in sky/negative space)
    if is_moon:
        elements.append(
            f'<circle cx="{sun_x}" cy="{sun_y}" r="{sun_r}" fill="#111827" fill-opacity="0.12" />'
            f'<circle cx="{sun_x + sun_r * 0.35}" cy="{sun_y - sun_r * 0.2}" r="{sun_r * 0.9}" fill="{colors.get("bg", "#ffffff") if colors else "#ffffff"}" />'
        )
    else:
        elements.append(
            f'<circle cx="{sun_x}" cy="{sun_y}" r="{sun_r}" fill="#111827" fill-opacity="0.08" stroke="#111827" stroke-width="2" stroke-opacity="0.25" />'
        )

    # Mountain Layers from back to front
    layer_configs = [
        {"base_y": h * 0.58, "amplitude": 120, "points": 6, "color": "#111827", "opacity": 0.12},
        {"base_y": h * 0.68, "amplitude": 160, "points": 7, "color": "#111827", "opacity": 0.28},
        {"base_y": h * 0.78, "amplitude": 190, "points": 8, "color": "#111827", "opacity": 0.55},
        {"base_y": h * 0.88, "amplitude": 220, "points": 9, "color": "#111827", "opacity": 0.90},
    ]

    selected_layers = layer_configs[-num_layers:]

    for idx, cfg in enumerate(selected_layers):
        pts = [(0.0, float(h))]
        base_y = cfg["base_y"]
        amp = cfg["amplitude"]
        n_pts = cfg["points"]
        dx = w / (n_pts - 1)

        for i in range(n_pts):
            px = i * dx
            if i == 0 or i == n_pts - 1:
                py = base_y + rng.uniform(-20, 20)
            else:
                py = base_y - rng.uniform(amp * 0.3, amp)
            pts.append((px, py))

        pts.append((float(w), float(h)))
        elements.append(_poly_to_svg(pts, cfg["color"], cfg["opacity"]))

    # Ground base line
    elements.append(f'<line x1="0" y1="{h}" x2="{w}" y2="{h}" stroke="#111827" stroke-width="4" />')

    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{"".join(elements)}</svg>'


def generate_ocean_horizon(
    rng: random.Random,
    canvas_size: Tuple[int, int] = (1600, 2560),
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Minimalist monochrome ocean horizon, stylized waves, sun/moon, and optional sailboat."""
    w, h = canvas_size
    horizon_y = h * rng.uniform(0.55, 0.65)
    elements = []

    # Sun or Moon on horizon
    sun_x = w * rng.uniform(0.3, 0.7)
    sun_r = rng.uniform(60, 95)
    elements.append(
        f'<circle cx="{sun_x}" cy="{horizon_y - sun_r * 0.4}" r="{sun_r}" fill="#111827" fill-opacity="0.08" stroke="#111827" stroke-width="2" stroke-opacity="0.2" />'
    )

    # Horizon line
    elements.append(f'<line x1="0" y1="{horizon_y}" x2="{w}" y2="{horizon_y}" stroke="#111827" stroke-width="2.5" stroke-opacity="0.4" />')

    # Wave rows
    wave_rows = rng.randint(4, 7)
    for r in range(wave_rows):
        y = horizon_y + ((h - horizon_y) / wave_rows) * (r + 0.5)
        num_peaks = rng.randint(5, 9)
        step = w / num_peaks
        d = [f"M 0 {y}"]
        for i in range(num_peaks):
            cx1 = i * step + step * 0.25
            cy1 = y - rng.uniform(15, 35) * (1 + r * 0.2)
            cx2 = i * step + step * 0.75
            cy2 = y + rng.uniform(10, 25)
            ex = (i + 1) * step
            ey = y
            d.append(f"C {cx1:.1f} {cy1:.1f}, {cx2:.1f} {cy2:.1f}, {ex:.1f} {ey:.1f}")

        d.append(f"L {w} {h} L 0 {h} Z")
        opacity = 0.15 + (r / wave_rows) * 0.65
        elements.append(_path_to_svg(" ".join(d), fill="#111827", stroke="none", opacity=opacity))

    # Optional minimalist sailboat silhouette
    if rng.random() > 0.35:
        bx = w * rng.uniform(0.2, 0.8)
        by = horizon_y - rng.uniform(5, 20)
        bw, bh = 50, 45
        elements.append(
            f'<polygon points="{bx},{by} {bx+bw},{by} {bx+bw*0.8},{by+12} {bx+bw*0.2},{by+12}" fill="#111827" opacity="0.85" />'
            f'<polygon points="{bx+bw*0.45},{by-bh} {bx+bw*0.45},{by-2} {bx+bw*0.9},{by-2}" fill="#111827" opacity="0.85" />'
            f'<polygon points="{bx+bw*0.35},{by-bh*0.8} {bx+bw*0.35},{by-2} {bx+bw*0.05},{by-2}" fill="#111827" opacity="0.7" />'
        )

    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{"".join(elements)}</svg>'


def generate_sky_clouds(
    rng: random.Random,
    canvas_size: Tuple[int, int] = (1600, 2560),
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Editorial stylized cloud silhouettes, stars/moon, and open negative sky."""
    w, h = canvas_size
    elements = []

    # Moon / Sun in high sky
    mx = w * rng.uniform(0.2, 0.8)
    my = h * rng.uniform(0.18, 0.28)
    mr = rng.uniform(40, 65)
    elements.append(
        f'<circle cx="{mx}" cy="{my}" r="{mr}" fill="#111827" fill-opacity="0.07" stroke="#111827" stroke-width="1.5" stroke-opacity="0.3" />'
    )

    # Constellation / star dots
    num_stars = rng.randint(8, 16)
    for _ in range(num_stars):
        sx = rng.uniform(w * 0.1, w * 0.9)
        sy = rng.uniform(h * 0.1, h * 0.45)
        sr = rng.uniform(1.5, 3.5)
        elements.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{sr:.1f}" fill="#111827" opacity="{rng.uniform(0.2, 0.6):.2f}" />')

    # Stylized Cloud Silhouettes in lower 40% of canvas
    cloud_layers = [
        {"y": h * 0.65, "opacity": 0.12, "scale": 1.2},
        {"y": h * 0.78, "opacity": 0.25, "scale": 1.0},
        {"y": h * 0.90, "opacity": 0.65, "scale": 0.9},
    ]

    for layer in cloud_layers:
        cy = layer["y"]
        op = layer["opacity"]
        d = [f"M 0 {h} L 0 {cy}"]
        cx = 0.0
        while cx < w + 200:
            cr = rng.uniform(70, 140) * layer["scale"]
            d.append(f"A {cr} {cr} 0 0 1 {cx + cr * 1.6:.1f} {cy:.1f}")
            cx += cr * 1.6
        d.append(f"L {w} {h} Z")
        elements.append(_path_to_svg(" ".join(d), fill="#111827", opacity=op))

    # Birds in flight (3-5 birds)
    num_birds = rng.randint(3, 5)
    for _ in range(num_birds):
        bx = rng.uniform(w * 0.2, w * 0.8)
        by = rng.uniform(h * 0.35, h * 0.55)
        bsz = rng.uniform(14, 22)
        bird_path = f"M {bx-bsz} {by+bsz*0.3} Q {bx-bsz*0.4} {by-bsz*0.6} {bx} {by} Q {bx+bsz*0.4} {by-bsz*0.6} {bx+bsz} {by+bsz*0.3}"
        elements.append(_path_to_svg(bird_path, stroke="#111827", stroke_width=2.0, opacity=0.6))

    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{"".join(elements)}</svg>'


def generate_abstract_geometric(
    rng: random.Random,
    canvas_size: Tuple[int, int] = (1600, 2560),
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Bauhaus & Swiss inspired geometric composition: concentric arcs, grid modules, solid/outline forms."""
    w, h = canvas_size
    elements = []

    # Subtle orthogonal grid
    grid_spacing = 160
    for x in range(0, w, grid_spacing):
        elements.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{h}" stroke="#111827" stroke-width="0.75" stroke-opacity="0.04" stroke-dasharray="4 8" />')
    for y in range(0, h, grid_spacing):
        elements.append(f'<line x1="0" y1="{y}" x2="{w}" y2="{y}" stroke="#111827" stroke-width="0.75" stroke-opacity="0.04" stroke-dasharray="4 8" />')

    # Hero Geometric Centerpiece
    cx = w * rng.choice([0.35, 0.5, 0.65])
    cy = h * rng.choice([0.45, 0.55, 0.65])

    # Concentric Arcs / Circles
    radii = [120, 240, 360, 480]
    for r in radii:
        if rng.random() > 0.3:
            elements.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#111827" stroke-width="{rng.choice([1.5, 2.5, 4.0])}" stroke-opacity="{rng.uniform(0.12, 0.35):.2f}" />'
            )

    # Solid accent geometric block (semi-circle, quadrant or rectangle)
    shape_choice = rng.choice(["semicircle", "diagonal_block", "offset_circle", "stacked_bars"])
    if shape_choice == "semicircle":
        elements.append(
            f'<path d="M {cx - 200} {cy} A 200 200 0 0 1 {cx + 200} {cy} Z" fill="#111827" opacity="0.85" />'
        )
    elif shape_choice == "diagonal_block":
        elements.append(
            f'<polygon points="{cx-150},{cy-150} {cx+250},{cy-50} {cx+150},{cy+250} {cx-250},{cy+150}" fill="#111827" opacity="0.12" stroke="#111827" stroke-width="2" />'
        )
    elif shape_choice == "offset_circle":
        elements.append(
            f'<circle cx="{cx + 100}" cy="{cy - 80}" r="140" fill="#111827" opacity="0.85" />'
            f'<circle cx="{cx - 80}" cy="{cy + 100}" r="90" fill="none" stroke="#111827" stroke-width="3" opacity="0.5" />'
        )
    else:
        for i in range(5):
            elements.append(
                f'<rect x="{cx - 180 + i * 75}" y="{cy - 120}" width="45" height="{160 + i * 30}" fill="#111827" opacity="{0.15 + i * 0.16:.2f}" />'
            )

    # Fine registration crosshairs
    for (px, py) in [(w * 0.12, h * 0.12), (w * 0.88, h * 0.12), (w * 0.12, h * 0.88), (w * 0.88, h * 0.88)]:
        elements.append(
            f'<line x1="{px-16}" y1="{py}" x2="{px+16}" y2="{py}" stroke="#111827" stroke-width="1.5" opacity="0.3" />'
            f'<line x1="{px}" y1="{py-16}" x2="{px}" y2="{py+16}" stroke="#111827" stroke-width="1.5" opacity="0.3" />'
        )

    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{"".join(elements)}</svg>'


def generate_typographic_poster_accents(
    rng: random.Random,
    canvas_size: Tuple[int, int] = (1600, 2560),
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Editorial layout framing rules, oversized number watermarks, and grid boundaries."""
    w, h = canvas_size
    elements = []

    # Large numeral watermark (e.g. 01, VOL. 1, № 1)
    numeral = rng.choice(["01", "00", "01 //", "NO. 1", "VOL. I", "§ 1"])
    nx = w * rng.choice([0.12, 0.55])
    ny = h * rng.choice([0.38, 0.68])
    elements.append(
        f'<text x="{nx}" y="{ny}" font-family="Plus Jakarta Sans, Inter, sans-serif" font-weight="900" font-size="280" fill="#111827" fill-opacity="0.04" letter-spacing="-8">{numeral}</text>'
    )

    # Architectural framing rules
    margin_x = 120
    margin_y = 160
    elements.append(
        f'<rect x="{margin_x}" y="{margin_y}" width="{w - margin_x * 2}" height="{h - margin_y * 2}" fill="none" stroke="#111827" stroke-width="1.5" stroke-opacity="0.15" />'
    )
    # Divider rule
    elements.append(
        f'<line x1="{margin_x}" y1="{h * 0.48}" x2="{w - margin_x}" y2="{h * 0.48}" stroke="#111827" stroke-width="1.0" stroke-opacity="0.2" />'
    )

    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{"".join(elements)}</svg>'


def generate_botanical_foliage(
    rng: random.Random,
    canvas_size: Tuple[int, int] = (1600, 2560),
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Monochrome botanical stems, delicate leaves, and curving branches."""
    w, h = canvas_size
    elements = []

    # Curving central stem from bottom-right or bottom-left
    origin_left = rng.random() > 0.5
    sx = w * 0.15 if origin_left else w * 0.85
    sy = float(h)
    tx = w * 0.5 if origin_left else w * 0.5
    ty = h * rng.uniform(0.35, 0.48)
    cx = w * 0.1 if origin_left else w * 0.9
    cy = h * 0.65

    stem_path = f"M {sx} {sy} Q {cx} {cy} {tx} {ty}"
    elements.append(_path_to_svg(stem_path, stroke="#111827", stroke_width=4.0, opacity=0.75))

    # Leaves sprouting along curve
    num_leaves = rng.randint(7, 12)
    for i in range(num_leaves):
        t = (i + 1) / (num_leaves + 1)
        # Bezier point
        lx = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t ** 2 * tx
        ly = (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t ** 2 * ty
        side = 1 if i % 2 == 0 else -1
        leaf_len = rng.uniform(70, 120)
        leaf_w = rng.uniform(30, 50)
        angle = rng.uniform(25, 55) * side

        rad = math.radians(angle)
        dx = math.cos(rad) * leaf_len
        dy = math.sin(rad) * leaf_len

        # Leaf shape: Q curve out and back
        leaf_d = f"M {lx} {ly} Q {lx + dx * 0.5 - dy * 0.4} {ly + dy * 0.5 + dx * 0.4} {lx + dx} {ly + dy} Q {lx + dx * 0.5 + dy * 0.4} {ly + dy * 0.5 - dx * 0.4} {lx} {ly} Z"
        opacity = 0.45 if i % 3 == 0 else 0.85
        elements.append(_path_to_svg(leaf_d, fill="#111827", opacity=opacity))

    # Subtle botanical circle accent
    elements.append(
        f'<circle cx="{tx}" cy="{ty - 60}" r="35" fill="none" stroke="#111827" stroke-width="1.5" opacity="0.3" stroke-dasharray="3 5" />'
    )

    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{"".join(elements)}</svg>'


def generate_terrain_journey(
    rng: random.Random,
    canvas_size: Tuple[int, int] = (1600, 2560),
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Winding perspective ribbon path weaving through rolling hill contours toward sunrise."""
    w, h = canvas_size
    elements = []

    horizon_y = h * rng.uniform(0.46, 0.56)
    sun_x = w * 0.5
    sun_y = horizon_y
    sun_r = rng.uniform(60, 85)

    # Rising Sun at the horizon destination
    elements.append(
        f'<circle cx="{sun_x}" cy="{sun_y}" r="{sun_r}" fill="#111827" fill-opacity="0.08" stroke="#111827" stroke-width="2.5" stroke-opacity="0.35" />'
    )
    # Sun rays
    for i in range(8):
        angle = -180 + i * 25
        rad = math.radians(angle)
        x1 = sun_x + math.cos(rad) * (sun_r + 15)
        y1 = sun_y + math.sin(rad) * (sun_r + 15)
        x2 = sun_x + math.cos(rad) * (sun_r + 55)
        y2 = sun_y + math.sin(rad) * (sun_r + 55)
        elements.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111827" stroke-width="1.5" stroke-opacity="0.25" />')

    # Rolling Hill Contours
    hill_layers = [
        {"y": horizon_y + 60, "amp": 60, "opacity": 0.15},
        {"y": horizon_y + 240, "amp": 90, "opacity": 0.35},
        {"y": horizon_y + 480, "amp": 120, "opacity": 0.65},
    ]
    for idx, hill in enumerate(hill_layers):
        hy = hill["y"]
        amp = hill["amp"]
        pts = [
            f"M 0 {h}",
            f"L 0 {hy}",
            f"Q {w*0.3} {hy-amp} {w*0.5} {hy}",
            f"Q {w*0.75} {hy+amp*0.8} {w} {hy-amp*0.4}",
            f"L {w} {h} Z",
        ]
        elements.append(_path_to_svg(" ".join(pts), fill="#111827", opacity=hill["opacity"]))

    # Winding Perspective Ribbon Path (wide at bottom, narrow at horizon)
    p_pts = [
        f"M {w * 0.35} {h}",
        f"C {w * 0.42} {h * 0.85}, {w * 0.72} {h * 0.75}, {w * 0.62} {h * 0.65}",
        f"C {w * 0.52} {h * 0.58}, {w * 0.44} {horizon_y + 40}, {sun_x - 6} {horizon_y}",
        f"L {sun_x + 6} {horizon_y}",
        f"C {w * 0.48} {horizon_y + 40}, {w * 0.58} {h * 0.58}, {w * 0.68} {h * 0.65}",
        f"C {w * 0.78} {h * 0.75}, {w * 0.52} {h * 0.85}, {w * 0.65} {h} Z",
    ]
    elements.append(_path_to_svg(" ".join(p_pts), fill="#111827", stroke="none", opacity=0.92))

    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{"".join(elements)}</svg>'


def generate_symbolic_object(
    rng: random.Random,
    symbol_type: Optional[str] = None,
    canvas_size: Tuple[int, int] = (1600, 2560),
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Hero monochrome vector object: habit loop/calendar, terminal/code, neural nodes, balance scale, open book, compass."""
    w, h = canvas_size
    elements = []

    # Center placement for hero symbol in visual mid-lower zone
    cx = w * 0.5
    cy = h * 0.58

    valid_symbols = ["habit_loop", "terminal_code", "neural_nodes", "open_book", "compass", "balance_scale"]
    chosen_sym = symbol_type if symbol_type in valid_symbols else rng.choice(valid_symbols)

    if chosen_sym == "habit_loop":
        # Interlocking circular habit loop with arrows and calendar grid
        r = 220
        elements.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#111827" stroke-width="12" stroke-opacity="0.85" stroke-dasharray="140 24" />'
            f'<circle cx="{cx}" cy="{cy}" r="{r - 60}" fill="none" stroke="#111827" stroke-width="2" stroke-opacity="0.25" stroke-dasharray="6 8" />'
            f'<circle cx="{cx}" cy="{cy}" r="{r - 100}" fill="#111827" fill-opacity="0.06" />'
        )
        # Calendar dots inside loop
        for row in range(4):
            for col in range(4):
                dx = (col - 1.5) * 32
                dy = (row - 1.5) * 32
                op = 0.85 if (row + col) % 2 == 0 else 0.25
                elements.append(f'<circle cx="{cx + dx}" cy="{cy + dy}" r="6" fill="#111827" opacity="{op}" />')

    elif chosen_sym == "terminal_code":
        # Minimalist modern code terminal hero card
        tw, th = 560, 360
        elements.append(
            f'<rect x="{cx - tw/2}" y="{cy - th/2}" width="{tw}" height="{th}" rx="16" fill="#ffffff" stroke="#111827" stroke-width="4" stroke-opacity="0.9" />'
            f'<line x1="{cx - tw/2}" y1="{cy - th/2 + 56}" x2="{cx + tw/2}" y2="{cy - th/2 + 56}" stroke="#111827" stroke-width="2" stroke-opacity="0.2" />'
            f'<circle cx="{cx - tw/2 + 32}" cy="{cy - th/2 + 28}" r="8" fill="#111827" opacity="0.85" />'
            f'<circle cx="{cx - tw/2 + 58}" cy="{cy - th/2 + 28}" r="8" fill="#111827" opacity="0.35" />'
            f'<circle cx="{cx - tw/2 + 84}" cy="{cy - th/2 + 28}" r="8" fill="#111827" opacity="0.35" />'
            # Code line bars
            f'<rect x="{cx - tw/2 + 36}" y="{cy - th/2 + 95}" width="80" height="12" rx="4" fill="#111827" opacity="0.85" />'
            f'<rect x="{cx - tw/2 + 130}" y="{cy - th/2 + 95}" width="220" height="12" rx="4" fill="#111827" opacity="0.35" />'
            f'<rect x="{cx - tw/2 + 64}" y="{cy - th/2 + 135}" width="180" height="12" rx="4" fill="#111827" opacity="0.45" />'
            f'<rect x="{cx - tw/2 + 64}" y="{cy - th/2 + 175}" width="260" height="12" rx="4" fill="#111827" opacity="0.75" />'
            f'<rect x="{cx - tw/2 + 36}" y="{cy - th/2 + 225}" width="120" height="12" rx="4" fill="#111827" opacity="0.85" />'
        )

    elif chosen_sym == "neural_nodes":
        # Clean interconnected node cluster
        nodes = [
            (cx - 180, cy - 100), (cx, cy - 160), (cx + 180, cy - 90),
            (cx - 120, cy + 40), (cx + 80, cy + 30),
            (cx - 40, cy + 140), (cx + 160, cy + 130)
        ]
        for i, p1 in enumerate(nodes):
            for j, p2 in enumerate(nodes):
                if i < j and rng.random() > 0.4:
                    elements.append(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="#111827" stroke-width="2" stroke-opacity="0.35" />')
        for px, py in nodes:
            elements.append(
                f'<circle cx="{px}" cy="{py}" r="22" fill="#ffffff" stroke="#111827" stroke-width="4" stroke-opacity="0.9" />'
                f'<circle cx="{px}" cy="{py}" r="8" fill="#111827" opacity="0.85" />'
            )

    elif chosen_sym == "open_book":
        # Architectural open book silhouette with radiating lines
        bw, bh = 320, 180
        elements.append(
            f'<path d="M {cx} {cy+bh/2} Q {cx-bw/4} {cy+bh/2-30} {cx-bw/2} {cy+bh/2} L {cx-bw/2} {cy-bh/2} Q {cx-bw/4} {cy-bh/2-30} {cx} {cy-bh/2} Z" fill="#111827" opacity="0.85" />'
            f'<path d="M {cx} {cy+bh/2} Q {cx+bw/4} {cy+bh/2-30} {cx+bw/2} {cy+bh/2} L {cx+bw/2} {cy-bh/2} Q {cx+bw/4} {cy-bh/2-30} {cx} {cy-bh/2} Z" fill="#111827" opacity="0.75" />'
            f'<line x1="{cx}" y1="{cy-bh/2}" x2="{cx}" y2="{cy+bh/2+10}" stroke="#ffffff" stroke-width="3" />'
        )

    elif chosen_sym == "compass":
        # Precision navigation compass
        cr = 180
        elements.append(
            f'<circle cx="{cx}" cy="{cy}" r="{cr}" fill="none" stroke="#111827" stroke-width="3" stroke-opacity="0.6" />'
            f'<circle cx="{cx}" cy="{cy}" r="{cr-24}" fill="none" stroke="#111827" stroke-width="1.5" stroke-opacity="0.3" stroke-dasharray="4 6" />'
            # Needle
            f'<polygon points="{cx},{cy-cr+10} {cx-20},{cy} {cx},{cy-15} {cx+20},{cy}" fill="#111827" opacity="0.9" />'
            f'<polygon points="{cx},{cy+cr-10} {cx-20},{cy} {cx},{cy+15} {cx+20},{cy}" fill="#111827" opacity="0.3" />'
            f'<circle cx="{cx}" cy="{cy}" r="10" fill="#111827" />'
        )

    else:  # balance_scale
        elements.append(
            f'<line x1="{cx}" y1="{cy-160}" x2="{cx}" y2="{cy+160}" stroke="#111827" stroke-width="6" />'
            f'<line x1="{cx-160}" y1="{cy-100}" x2="{cx+160}" y2="{cy-100}" stroke="#111827" stroke-width="4" />'
            f'<polygon points="{cx-220},{cy-20} {cx-100},{cy-20} {cx-160},{cy-100}" fill="none" stroke="#111827" stroke-width="3" />'
            f'<polygon points="{cx+100},{cy-20} {cx+220},{cy-20} {cx+160},{cy-100}" fill="none" stroke="#111827" stroke-width="3" />'
            f'<rect x="{cx-80}" y="{cy+150}" width="160" height="20" rx="4" fill="#111827" />'
        )

    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{"".join(elements)}</svg>'


def generate_cinematic_landscape(
    rng: random.Random,
    canvas_size: Tuple[int, int] = (1600, 2560),
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Atmospheric minimalist landscape with 80% open negative sky and low 20% horizon silhouette."""
    w, h = canvas_size
    horizon_y = h * 0.82
    elements = []

    # Vast sky: delicate fine moon or lone horizon star
    sx = w * rng.uniform(0.3, 0.7)
    sy = h * rng.uniform(0.25, 0.35)
    sr = rng.uniform(25, 45)
    elements.append(
        f'<circle cx="{sx}" cy="{sy}" r="{sr}" fill="#111827" fill-opacity="0.08" stroke="#111827" stroke-width="1.5" stroke-opacity="0.3" />'
    )

    # Low landscape horizon silhouette
    hill_pts = [
        f"M 0 {h}",
        f"L 0 {horizon_y}",
        f"Q {w*0.25} {horizon_y-40} {w*0.5} {horizon_y-10}",
        f"Q {w*0.75} {horizon_y+30} {w} {horizon_y-25}",
        f"L {w} {h} Z",
    ]
    elements.append(_path_to_svg(" ".join(hill_pts), fill="#111827", opacity=0.92))

    # Single tiny solitary silhouette tree on ridge
    tx = w * rng.uniform(0.65, 0.8)
    ty = horizon_y - 18
    elements.append(
        f'<line x1="{tx}" y1="{ty}" x2="{tx}" y2="{ty-65}" stroke="#ffffff" stroke-width="3" stroke-opacity="0.9" />'
        f'<circle cx="{tx}" cy="{ty-75}" r="28" fill="#ffffff" fill-opacity="0.85" />'
    )

    # Atmospheric horizontal ground strip
    elements.append(
        f'<line x1="{w*0.1}" y1="{horizon_y - 2}" x2="{w*0.9}" y2="{horizon_y - 2}" stroke="#111827" stroke-width="1" stroke-opacity="0.3" />'
    )

    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{"".join(elements)}</svg>'


def generate_editorial_minimal(
    rng: random.Random,
    canvas_size: Tuple[int, int] = (1600, 2560),
    colors: Optional[Dict[str, str]] = None,
) -> str:
    """Editorial minimalist geometry: delicate hairlines, corner framing, and single subtle anchor ring."""
    w, h = canvas_size
    elements = []

    # Subtle anchor ring in lower third
    cx = w * rng.choice([0.5, 0.72])
    cy = h * rng.choice([0.62, 0.74])
    r = rng.uniform(140, 220)
    elements.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#111827" stroke-width="1.5" stroke-opacity="0.18" />'
        f'<circle cx="{cx}" cy="{cy}" r="{r * 0.4}" fill="#111827" fill-opacity="0.05" />'
    )

    # Hairline column guide
    elements.append(
        f'<line x1="{w * 0.12}" y1="{h * 0.15}" x2="{w * 0.12}" y2="{h * 0.85}" stroke="#111827" stroke-width="0.75" stroke-opacity="0.12" />'
    )

    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{"".join(elements)}</svg>'

