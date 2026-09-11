"""Component renderer for structured technical blocks: code, terminals, tables, charts, diagrams, callouts, and sources."""

import html
import logging
from typing import Any, Dict, List, Optional
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter

from vasukisquare.book.components import (
    CalloutBlock,
    ChartBlock,
    CodeBlock,
    ContentBlock,
    DiagramBlock,
    HeadingBlock,
    QuoteBlock,
    SourceBlock,
    StatisticBlock,
    TableBlock,
    TerminalBlock,
    TextBlock,
)
from vasukisquare.design.icons import render_lucide_icon, IconColorResolver
from vasukisquare.design.theme import Theme
from vasukisquare.design.tokens import ColorToken

logger = logging.getLogger(__name__)


class ComponentRenderer:
    """Renders structured technical content components into deterministic, high-contrast HTML."""

    @classmethod
    def render_block(cls, block: ContentBlock, theme: Theme = Theme.LIGHT) -> str:
        """Dispatch rendering for any ContentBlock variant."""
        if isinstance(block, CodeBlock) or getattr(block, "type", None) == "code":
            return cls.render_code(block, theme)
        elif isinstance(block, TerminalBlock) or getattr(block, "type", None) == "terminal":
            return cls.render_terminal(block, theme)
        elif isinstance(block, TableBlock) or getattr(block, "type", None) == "table":
            return cls.render_table(block, theme)
        elif isinstance(block, SourceBlock) or getattr(block, "type", None) == "source":
            return cls.render_source(block, theme)
        elif isinstance(block, CalloutBlock) or getattr(block, "type", None) == "callout":
            return cls.render_callout(block, theme)
        elif isinstance(block, ChartBlock) or getattr(block, "type", None) == "chart":
            return cls.render_chart(block, theme)
        elif isinstance(block, DiagramBlock) or getattr(block, "type", None) == "diagram":
            return cls.render_diagram(block, theme)
        elif isinstance(block, QuoteBlock) or getattr(block, "type", None) == "quote":
            return cls.render_quote(block, theme)
        elif isinstance(block, StatisticBlock) or getattr(block, "type", None) == "statistic":
            return cls.render_statistic(block, theme)
        elif isinstance(block, HeadingBlock) or getattr(block, "type", None) == "heading":
            return cls.render_heading(block, theme)
        elif isinstance(block, TextBlock) or getattr(block, "type", None) == "text":
            return cls.render_text(block, theme)
        return ""

    @classmethod
    def render_code(cls, block: CodeBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render syntax-highlighted code block with language badge, optional filename, and caption."""
        lang = (block.language or "text").lower().strip()
        try:
            lexer = get_lexer_by_name(lang, stripall=True)
        except Exception:
            lexer = TextLexer()

        # Pygments HTML formatting
        formatter = HtmlFormatter(nowrap=True, classprefix="hl-")
        highlighted_code = highlight(block.code, lexer, formatter)

        filename_badge = f'<span class="code-filename">{html.escape(block.filename)}</span>' if block.filename else ""
        lang_badge = f'<span class="code-lang-badge">{html.escape(lang.upper())}</span>'
        caption_html = f'<figcaption class="code-caption">{html.escape(block.caption)}</figcaption>' if block.caption else ""

        return f"""
        <figure class="component-code-figure">
          <div class="component-code-block theme-{theme.value}">
            <div class="code-header">
              {filename_badge}
              {lang_badge}
            </div>
            <pre class="code-pre"><code class="language-{lang}">{highlighted_code}</code></pre>
          </div>
          {caption_html}
        </figure>
        """

    @classmethod
    def render_terminal(cls, block: TerminalBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render dedicated editorial terminal/console block with command, stdout, and error styling."""
        lines_html = []
        for line in block.lines:
            raw = line.strip()
            if raw.startswith("$ ") or raw.startswith("# "):
                prefix = raw[:2]
                cmd = raw[2:]
                lines_html.append(
                    f'<div class="terminal-line is-command"><span class="terminal-prompt">{html.escape(prefix)}</span><span class="terminal-cmd">{html.escape(cmd)}</span></div>'
                )
            elif raw.startswith("[error]") or raw.startswith("Error:") or "FAILED" in raw:
                lines_html.append(f'<div class="terminal-line is-error">{html.escape(raw)}</div>')
            elif raw.startswith("[warning]") or raw.startswith("Warning:"):
                lines_html.append(f'<div class="terminal-line is-warning">{html.escape(raw)}</div>')
            elif raw.startswith("[success]") or raw.startswith("✓") or "SUCCESS" in raw:
                lines_html.append(f'<div class="terminal-line is-success">{html.escape(raw)}</div>')
            elif raw.startswith("//") or raw.startswith("#") or raw.startswith("/*"):
                lines_html.append(f'<div class="terminal-line is-comment">{html.escape(raw)}</div>')
            else:
                lines_html.append(f'<div class="terminal-line is-stdout">{html.escape(raw)}</div>')

        shell_label = f'<span class="terminal-shell">{html.escape(block.shell.upper())}</span>'
        title_label = f'<span class="terminal-title">{html.escape(block.title)}</span>'

        return f"""
        <div class="component-terminal-window">
          <div class="terminal-header">
            <div class="terminal-dots">
              <span class="dot dot-red"></span>
              <span class="dot dot-yellow"></span>
              <span class="dot dot-green"></span>
            </div>
            {title_label}
            {shell_label}
          </div>
          <div class="terminal-body">
            {''.join(lines_html)}
          </div>
        </div>
        """

    @classmethod
    def render_table(cls, block: TableBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render high-contrast, structured A4 table."""
        caption_html = f'<caption class="table-caption">{html.escape(block.caption)}</caption>' if block.caption else ""

        # Alignments
        alignments = block.alignment or ["left"] * len(block.columns)

        # Header
        headers = []
        for idx, col in enumerate(block.columns):
            align = alignments[idx] if idx < len(alignments) else "left"
            headers.append(f'<th style="text-align: {align};">{html.escape(col)}</th>')
        thead = f"<thead><tr>{''.join(headers)}</tr></thead>"

        # Rows
        row_htmls = []
        for row in block.rows:
            cells = []
            for idx, cell in enumerate(row):
                align = alignments[idx] if idx < len(alignments) else "left"
                cells.append(f'<td style="text-align: {align};">{html.escape(str(cell))}</td>')
            row_htmls.append(f"<tr>{''.join(cells)}</tr>")
        tbody = f"<tbody>{''.join(row_htmls)}</tbody>"

        return f"""
        <div class="component-table-container">
          <table class="component-table theme-{theme.value}">
            {caption_html}
            {thead}
            {tbody}
          </table>
        </div>
        """

    @classmethod
    def render_source(cls, block: SourceBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render clickable source link or reference card."""
        clean_url = html.escape(block.url)
        title_escaped = html.escape(block.title)
        pub_escaped = html.escape(block.publisher or "Primary Source")
        accessed = f'<span class="source-date">Accessed: {html.escape(block.accessed_at)}</span>' if block.accessed_at else ""

        # Display domain or title rather than enormous raw string
        try:
            from urllib.parse import urlparse
            domain = urlparse(block.url).netloc or block.publisher or "External Link"
        except Exception:
            domain = block.publisher or "External Link"

        if block.mode == "inline":
            return f"""
            <a class="component-source-inline" href="{clean_url}" target="_blank" title="{title_escaped}">
              <span class="source-icon">↗</span>
              <span class="source-label">{title_escaped}</span>
              <span class="source-pub">({html.escape(domain)})</span>
            </a>
            """

        return f"""
        <div class="component-source-card theme-{theme.value}">
          <div class="source-header">
            <span class="source-publisher">{pub_escaped}</span>
            {accessed}
          </div>
          <h4 class="source-title"><a href="{clean_url}" target="_blank">{title_escaped}</a></h4>
          <div class="source-link-row">
            <span class="source-domain">🔗 {html.escape(domain)}</span>
            <a class="source-url-btn" href="{clean_url}" target="_blank">View Reference ↗</a>
          </div>
        </div>
        """

    @classmethod
    def render_callout(cls, block: CalloutBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render semantic callout box (note, important, warning, tip, definition) with Lucide icon."""
        icon_map = {
            "note": "info",
            "important": "alert-triangle",
            "warning": "alert-circle",
            "tip": "lightbulb",
            "definition": "book-open",
        }
        icon_name = block.icon or icon_map.get(block.variant, "info")
        icon_color = IconColorResolver.resolve_color(theme, role="primary")
        icon_svg = render_lucide_icon(icon_name, color=icon_color, size=20)

        return f"""
        <div class="component-callout callout-{block.variant} theme-{theme.value}">
          <div class="callout-header">
            <span class="callout-icon">{icon_svg}</span>
            <strong class="callout-title">{html.escape(block.title)}</strong>
          </div>
          <div class="callout-content">
            <p>{html.escape(block.content)}</p>
          </div>
        </div>
        """

    @classmethod
    def render_chart(cls, block: ChartBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render vector SVG chart deterministic offline with DESIGN.md color tokens."""
        title_escaped = html.escape(block.title)
        chart_type = block.chart_type.lower()

        # Token color sequence
        palette = [
            "#00ed64",  # brand green
            "#00a35c",  # brand green mid
            "#7b3ff2",  # accent purple
            "#fa6e39",  # accent orange
            "#3d4f9f",  # accent blue
            "#00684a",  # brand green dark
        ]

        svg_content = ""
        width = 620
        height = 240
        margin_left = 60
        margin_bottom = 40
        margin_top = 20
        margin_right = 20
        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        text_color = "#e1e5e8" if theme == Theme.DARK else "#3d4f5b"
        grid_color = "#1c2d38" if theme == Theme.DARK else "#e1e5e8"

        if chart_type == "bar" and block.labels and block.series:
            series_data = block.series[0].get("values", [])
            max_val = max(series_data) if series_data else 100
            max_val = max(max_val, 1)

            num_bars = len(block.labels)
            bar_width = min(40, int(plot_w / (num_bars * 1.5)))
            gap = int((plot_w - (num_bars * bar_width)) / max(1, num_bars + 1))

            bars = []
            grid_lines = []

            # 4 horizontal grid lines
            for i in range(5):
                y_pos = margin_top + int(plot_h * (1 - (i / 4.0)))
                val_label = int(max_val * (i / 4.0))
                grid_lines.append(
                    f'<line x1="{margin_left}" y1="{y_pos}" x2="{width - margin_right}" y2="{y_pos}" stroke="{grid_color}" stroke-dasharray="3,3" stroke-width="1"/>'
                )
                grid_lines.append(
                    f'<text x="{margin_left - 8}" y="{y_pos + 4}" fill="{text_color}" font-size="10" text-anchor="end">{val_label}</text>'
                )

            for idx, label in enumerate(block.labels):
                val = series_data[idx] if idx < len(series_data) else 0
                b_h = int((val / max_val) * plot_h)
                x_pos = margin_left + gap + idx * (bar_width + gap)
                y_pos = margin_top + plot_h - b_h
                color = palette[idx % len(palette)]

                bars.append(
                    f'<rect x="{x_pos}" y="{y_pos}" width="{bar_width}" height="{b_h}" fill="{color}" rx="4"/>'
                )
                bars.append(
                    f'<text x="{x_pos + bar_width // 2}" y="{y_pos - 6}" fill="{text_color}" font-size="11" font-weight="600" text-anchor="middle">{val:,}</text>'
                )
                bars.append(
                    f'<text x="{x_pos + bar_width // 2}" y="{margin_top + plot_h + 16}" fill="{text_color}" font-size="11" text-anchor="middle">{html.escape(str(label))}</text>'
                )

            svg_content = f"""
            <svg viewBox="0 0 {width} {height}" class="chart-svg" xmlns="http://www.w3.org/2000/svg">
              {''.join(grid_lines)}
              {''.join(bars)}
            </svg>
            """

        elif chart_type == "line" and block.labels and block.series:
            series_data = block.series[0].get("values", [])
            max_val = max(series_data) if series_data else 100
            max_val = max(max_val, 1)
            num_pts = len(block.labels)

            grid_lines = []
            for i in range(5):
                y_pos = margin_top + int(plot_h * (1 - (i / 4.0)))
                val_label = int(max_val * (i / 4.0))
                grid_lines.append(
                    f'<line x1="{margin_left}" y1="{y_pos}" x2="{width - margin_right}" y2="{y_pos}" stroke="{grid_color}" stroke-dasharray="3,3" stroke-width="1"/>'
                )
                grid_lines.append(
                    f'<text x="{margin_left - 8}" y="{y_pos + 4}" fill="{text_color}" font-size="10" text-anchor="end">{val_label}</text>'
                )

            points = []
            circles = []
            for idx, label in enumerate(block.labels):
                val = series_data[idx] if idx < len(series_data) else 0
                x_pos = margin_left + int(idx * (plot_w / max(1, num_pts - 1)))
                y_pos = margin_top + plot_h - int((val / max_val) * plot_h)
                points.append(f"{x_pos},{y_pos}")
                circles.append(f'<circle cx="{x_pos}" cy="{y_pos}" r="5" fill="#00ed64" stroke="#001e2b" stroke-width="2"/>')
                circles.append(
                    f'<text x="{x_pos}" y="{margin_top + plot_h + 16}" fill="{text_color}" font-size="11" text-anchor="middle">{html.escape(str(label))}</text>'
                )

            poly = f'<polyline fill="none" stroke="#00ed64" stroke-width="3" points="{" ".join(points)}"/>'
            svg_content = f"""
            <svg viewBox="0 0 {width} {height}" class="chart-svg" xmlns="http://www.w3.org/2000/svg">
              {''.join(grid_lines)}
              {poly}
              {''.join(circles)}
            </svg>
            """

        else:
            # Fallback simple card for pie/donut or multi-series
            svg_content = f"""
            <div class="chart-simple-fallback" style="padding: 24px; text-align: center; color: var(--theme-accent);">
              <strong>{title_escaped}</strong>
              <p style="font-size: 12px; margin-top: 8px;">{', '.join([f"{l}: {s.get('values', [''])[0]}" for l, s in zip(block.labels, block.series)])}</p>
            </div>
            """

        x_label_html = f'<div class="chart-axis-label x-label">{html.escape(block.x_label)}</div>' if block.x_label else ""
        y_label_html = f'<div class="chart-axis-label y-label">{html.escape(block.y_label)}</div>' if block.y_label else ""

        return f"""
        <div class="component-chart-container theme-{theme.value}">
          <h4 class="chart-title">{title_escaped}</h4>
          {y_label_html}
          <div class="chart-svg-wrapper">
            {svg_content}
          </div>
          {x_label_html}
        </div>
        """

    @classmethod
    def render_diagram(cls, block: DiagramBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render technical diagram / architecture flowchart."""
        caption_html = f'<figcaption class="diagram-caption">{html.escape(block.caption)}</figcaption>' if block.caption else ""
        escaped_code = html.escape(block.code)

        return f"""
        <figure class="component-diagram-figure theme-{theme.value}">
          <div class="diagram-frame">
            <div class="mermaid-container" data-mermaid="{escaped_code}">
              <pre class="mermaid">{escaped_code}</pre>
            </div>
          </div>
          {caption_html}
        </figure>
        """

    @classmethod
    def render_quote(cls, block: QuoteBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render blockquote with attribution."""
        attribution = ""
        if block.author:
            affil = f", <em>{html.escape(block.affiliation)}</em>" if block.affiliation else ""
            attribution = f'<cite class="quote-author">— {html.escape(block.author)}{affil}</cite>'

        return f"""
        <div class="component-quote theme-{theme.value}">
          <blockquote>
            <p>{html.escape(block.quote)}</p>
          </blockquote>
          {attribution}
        </div>
        """

    @classmethod
    def render_statistic(cls, block: StatisticBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render large number callout."""
        desc_html = f'<p class="stat-description">{html.escape(block.description)}</p>' if block.description else ""

        return f"""
        <div class="component-statistic theme-{theme.value}">
          <div class="stat-value">{html.escape(block.value)}</div>
          <div class="stat-label">{html.escape(block.label)}</div>
          {desc_html}
        </div>
        """

    @classmethod
    def render_heading(cls, block: HeadingBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render semantic section heading."""
        lvl = min(max(block.level, 1), 5)
        return f'<h{lvl} class="content-heading-{lvl}">{html.escape(block.text)}</h{lvl}>'

    @classmethod
    def render_text(cls, block: TextBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render prose text block."""
        if block.paragraphs:
            return "".join([f'<p class="content-body">{html.escape(p)}</p>' for p in block.paragraphs])
        return f'<p class="content-body">{html.escape(block.text)}</p>'

