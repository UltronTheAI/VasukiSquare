"""Component renderer for structured technical blocks: code, terminals, tables, charts, diagrams, callouts, icons, sources, and end-matter."""

import html
import logging
from typing import Any, Dict, List, Optional, Union
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter

from vasukisquare.book.components import (
    AcknowledgementBlock,
    CalloutBlock,
    ChartBlock,
    ChecklistBlock,
    CodeBlock,
    CommonMistakeBlock,
    ComparisonBlock,
    ContentBlock,
    CopyrightBlock,
    DefinitionBlock,
    DiagramBlock,
    ExerciseBlock,
    HeadingBlock,
    IconTextBlock,
    ImageBlock,
    OutputBlock,
    QuoteBlock,
    SourceBlock,
    StatisticBlock,
    StepBlock,
    TableBlock,
    TerminalBlock,
    TerminalLine,
    TextBlock,
    TimelineBlock,
    TocBlock,
    TocEntry,
)
from vasukisquare.design.icons import render_lucide_icon, IconColorResolver
from vasukisquare.design.theme import Theme
from vasukisquare.design.tokens import ColorToken, validate_color_token
from vasukisquare.design.visual_components import (
    render_comparison_block,
    render_timeline_block,
    render_checklist_block,
    render_step_block,
    render_definition_block,
    render_exercise_block,
)
from vasukisquare.renderer.richtext import RichTextRenderer
from vasukisquare.renderer.url_normalizer import UrlNormalizer

logger = logging.getLogger(__name__)


class ComponentRenderer:
    """Renders structured technical content components into deterministic, high-contrast HTML."""

    @classmethod
    def render_block(cls, block: ContentBlock, theme: Union[Theme, str] = Theme.LIGHT) -> str:
        """Dispatch rendering for any ContentBlock variant."""
        if isinstance(theme, str):
            theme = Theme.DARK if theme.lower() == "dark" else Theme.LIGHT
        b_type = getattr(block, "type", None)
        if isinstance(block, CodeBlock) or b_type == "code":
            return cls.render_code(block, theme)
        elif isinstance(block, OutputBlock) or b_type == "output":
            return cls.render_output(block, theme)
        elif isinstance(block, CommonMistakeBlock) or b_type == "mistake":
            return cls.render_mistake(block, theme)
        elif isinstance(block, TerminalBlock) or b_type == "terminal":
            return cls.render_terminal(block, theme)
        elif isinstance(block, TableBlock) or b_type == "table":
            return cls.render_table(block, theme)
        elif isinstance(block, SourceBlock) or b_type == "source":
            return cls.render_source(block, theme)
        elif isinstance(block, CalloutBlock) or b_type in ("callout", "info", "warning", "tip", "note"):
            return cls.render_callout(block, theme)
        elif isinstance(block, IconTextBlock) or b_type == "icon_text":
            return cls.render_icon_text(block, theme)
        elif isinstance(block, ChartBlock) or b_type == "chart":
            return cls.render_chart(block, theme)
        elif isinstance(block, DiagramBlock) or b_type == "diagram":
            return cls.render_diagram(block, theme)
        elif isinstance(block, QuoteBlock) or b_type == "quote":
            return cls.render_quote(block, theme)
        elif isinstance(block, StatisticBlock) or b_type == "statistic":
            return cls.render_statistic(block, theme)
        elif isinstance(block, ImageBlock) or b_type == "image":
            return cls.render_image(block, theme)
        elif isinstance(block, HeadingBlock) or b_type == "heading":
            return cls.render_heading(block, theme)
        elif isinstance(block, TextBlock) or b_type == "text":
            return cls.render_text(block, theme)
        elif isinstance(block, ComparisonBlock) or b_type == "comparison":
            return render_comparison_block(
                title=getattr(block, "title", None) or "",
                left_title=getattr(block, "left_title", "Do"),
                left_items=getattr(block, "left_items", []),
                right_title=getattr(block, "right_title", "Don't"),
                right_items=getattr(block, "right_items", []),
                left_icon=getattr(block, "left_icon", "check"),
                right_icon=getattr(block, "right_icon", "x"),
                theme=theme,
            )
        elif isinstance(block, TimelineBlock) or b_type == "timeline":
            items = []
            for it in getattr(block, "items", []):
                if isinstance(it, dict):
                    items.append(it)
                elif hasattr(it, "model_dump"):
                    items.append(it.model_dump())
                else:
                    items.append({"title": str(it), "description": ""})
            return render_timeline_block(
                title=getattr(block, "title", None) or "",
                items=items,
                theme=theme,
            )
        elif isinstance(block, ChecklistBlock) or b_type == "checklist":
            items = []
            for it in getattr(block, "items", []):
                if isinstance(it, dict):
                    items.append(it)
                elif isinstance(it, str):
                    items.append({"text": it, "checked": True})
                elif hasattr(it, "model_dump"):
                    items.append(it.model_dump())
            return render_checklist_block(
                title=getattr(block, "title", None) or "",
                items=items,
                theme=theme,
            )
        elif isinstance(block, StepBlock) or b_type == "step":
            steps = []
            for s in getattr(block, "steps", []):
                if isinstance(s, dict):
                    steps.append(s)
                elif hasattr(s, "model_dump"):
                    steps.append(s.model_dump())
            return render_step_block(
                title=getattr(block, "title", None) or "",
                steps=steps,
                theme=theme,
            )
        elif isinstance(block, DefinitionBlock) or b_type == "definition":
            return render_definition_block(
                term=getattr(block, "term", ""),
                definition=getattr(block, "definition", ""),
                pronunciation=getattr(block, "pronunciation", None),
                part_of_speech=getattr(block, "part_of_speech", None),
                example=getattr(block, "example", None),
                theme=theme,
            )
        elif isinstance(block, ExerciseBlock) or b_type == "exercise":
            return render_exercise_block(
                title=getattr(block, "title", ""),
                objective=getattr(block, "objective", ""),
                instructions=getattr(block, "instructions", []),
                difficulty=getattr(block, "difficulty", "Intermediate"),
                starter_code=getattr(block, "starter_code", None),
                hints=getattr(block, "hints", None),
                theme=theme,
            )
        elif isinstance(block, AcknowledgementBlock) or b_type == "acknowledgement":
            return cls.render_acknowledgement(block, theme)
        elif isinstance(block, CopyrightBlock) or b_type == "copyright":
            return cls.render_copyright(block, theme)
        elif isinstance(block, TocBlock) or b_type == "toc":
            return cls.render_toc(block, theme)
        return ""


    @classmethod
    def render_code(cls, block: CodeBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render colorful syntax-highlighted code block with language badge, optional filename, and caption."""
        lang = (block.language or "text").lower().strip()
        try:
            lexer = get_lexer_by_name(lang, stripall=True)
        except Exception:
            lexer = TextLexer()

        formatter = HtmlFormatter(nowrap=True, classprefix="hl-", linenos=block.line_numbers)
        highlighted_code = highlight(block.code, lexer, formatter)

        filename_badge = f'<span class="code-filename">{html.escape(block.filename)}</span>' if block.filename else ""
        lang_badge = f'<span class="code-lang-badge">{html.escape(lang.upper())}</span>'
        caption_html = (
            f'<figcaption class="code-caption">{RichTextRenderer.render_text_or_markdown(block.caption)}</figcaption>'
            if block.caption
            else ""
        )

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
    def render_output(cls, block: OutputBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render dedicated console output block with distinct monospace output formatting."""
        escaped_out = html.escape(block.output.strip())
        title_badge = f'<span class="output-title-badge">{html.escape(block.title or "OUTPUT")}</span>'
        caption_html = (
            f'<figcaption class="output-caption" style="font-size: 11px; color: var(--theme-text-muted); margin-top: 4px;">{RichTextRenderer.render_text_or_markdown(block.caption)}</figcaption>'
            if block.caption and block.caption != "Expected Output"
            else ""
        )
        return f"""
        <figure class="component-output-figure">
          <div class="component-output-block theme-{theme.value}" style="border-left: 3px solid var(--theme-accent, #00ed64); background: rgba(0,0,0,0.04); border-radius: 0 4px 4px 0; padding: 10px 14px; margin: 8px 0; font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 12.5px; line-height: 1.45;">
            <div class="output-header" style="font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--theme-text-muted); margin-bottom: 6px;">
              {title_badge}
            </div>
            <pre style="margin: 0; white-space: pre-wrap; word-break: break-word;"><code>{escaped_out}</code></pre>
          </div>
          {caption_html}
        </figure>
        """

    @classmethod
    def render_mistake(cls, block: CommonMistakeBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render labeled common beginner mistake comparison block with incorrect vs corrected code."""
        lang = (block.language or "python").lower().strip()
        try:
            lexer = get_lexer_by_name(lang, stripall=True)
        except Exception:
            lexer = TextLexer()
        formatter = HtmlFormatter(nowrap=True, classprefix="hl-", linenos=False)
        hl_wrong = highlight(block.mistake_code, lexer, formatter)
        hl_fixed = highlight(block.corrected_code, lexer, formatter) if block.corrected_code else ""

        fixed_block_html = ""
        if block.corrected_code:
            fixed_block_html = f"""
            <div class="mistake-fixed" style="margin-top: 8px; border-left: 3px solid #00a35c; padding: 6px 10px; background: rgba(0, 163, 92, 0.06);">
              <div style="font-size: 10px; font-weight: 700; color: #00a35c; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">✓ Corrected Code</div>
              <pre style="margin: 0; font-family: 'JetBrains Mono', monospace; font-size: 12px;"><code>{hl_fixed}</code></pre>
            </div>
            """

        explanation_html = RichTextRenderer.render_text_or_markdown(block.explanation)
        err_badge = f' <span style="font-size: 10px; background: rgba(239, 68, 68, 0.15); color: #dc2626; padding: 2px 6px; border-radius: 3px;">{html.escape(block.error_type)}</span>' if block.error_type else ""

        return f"""
        <div class="component-mistake-card theme-{theme.value}" style="border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 6px; padding: 12px 14px; margin: 10px 0; background: rgba(239, 68, 68, 0.03);">
          <div class="mistake-header" style="display: flex; align-items: center; gap: 6px; font-weight: 700; font-size: 13px; color: #dc2626; margin-bottom: 8px;">
            <span>⚠️ {html.escape(block.title)}</span>
            {err_badge}
          </div>
          <div class="mistake-wrong" style="border-left: 3px solid #dc2626; padding: 6px 10px; background: rgba(239, 68, 68, 0.06); margin-bottom: 8px;">
            <div style="font-size: 10px; font-weight: 700; color: #dc2626; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">✗ Incorrect / Common Pitfall</div>
            <pre style="margin: 0; font-family: 'JetBrains Mono', monospace; font-size: 12px;"><code>{hl_wrong}</code></pre>
          </div>
          {fixed_block_html}
          <div class="mistake-explanation" style="font-size: 12px; line-height: 1.45; color: var(--theme-text); margin-top: 8px;">
            {explanation_html}
          </div>
        </div>
        """

    @classmethod
    def render_terminal(cls, block: TerminalBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render dedicated editorial terminal/console block with semantic colored lines."""
        lines_html = []
        for line in block.lines:
            if isinstance(line, TerminalLine):
                kind = line.kind
                txt = html.escape(line.text)
                prompt = html.escape(line.prompt or ("$ " if kind == "command" else ""))
                if kind == "command":
                    lines_html.append(f'<div class="terminal-line is-command"><span class="terminal-prompt">{prompt}</span><span class="terminal-cmd">{txt}</span></div>')
                elif kind in ("stdout", "output"):
                    lines_html.append(f'<div class="terminal-line is-stdout">{txt}</div>')
                elif kind == "success":
                    lines_html.append(f'<div class="terminal-line is-success">{txt}</div>')
                elif kind == "warning":
                    lines_html.append(f'<div class="terminal-line is-warning">{txt}</div>')
                elif kind == "error":
                    lines_html.append(f'<div class="terminal-line is-error">{txt}</div>')
                elif kind == "comment":
                    lines_html.append(f'<div class="terminal-line is-comment">{txt}</div>')
            else:
                raw = str(line).strip()
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
        <div class="component-terminal-window theme-{theme.value}">
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
        """Render high-contrast, structured A4 table with rich cell formatting and optional icons."""
        caption_html = (
            f'<caption class="table-caption">{RichTextRenderer.render_text_or_markdown(block.caption)}</caption>'
            if block.caption
            else ""
        )

        alignments = block.alignment or ["left"] * len(block.columns)

        # Header
        headers = []
        for idx, col in enumerate(block.columns):
            align = alignments[idx] if idx < len(alignments) else "left"
            h_icon_html = ""
            if block.header_icons and idx < len(block.header_icons) and block.header_icons[idx]:
                h_icon_col = IconColorResolver.resolve_color(theme, role="primary")
                h_icon_html = f'<span style="margin-right: 6px; vertical-align: middle;">{render_lucide_icon(block.header_icons[idx], color=h_icon_col, size=14)}</span>'
            headers.append(f'<th style="text-align: {align};">{h_icon_html}{RichTextRenderer.render_text_or_markdown(col)}</th>')
        thead = f"<thead><tr>{''.join(headers)}</tr></thead>"


        # Rows
        row_htmls = []
        for r_idx, row in enumerate(block.rows):
            cells = []
            for c_idx, cell in enumerate(row):
                align = alignments[c_idx] if c_idx < len(alignments) else "left"
                is_first_col = c_idx == 0 and block.highlight_first_column
                font_weight = "font-weight: 600;" if is_first_col else ""

                icon_html = ""
                if block.icons and r_idx < len(block.icons) and c_idx < len(block.icons[r_idx]):
                    icon_name = block.icons[r_idx][c_idx]
                    if icon_name:
                        icon_col = IconColorResolver.resolve_color(theme, role="primary")
                        icon_html = f'<span style="margin-right: 6px; vertical-align: middle;">{render_lucide_icon(icon_name, color=icon_col, size=14)}</span>'

                rendered_cell = RichTextRenderer.render_text_or_markdown(str(cell))
                cells.append(f'<td style="text-align: {align}; {font_weight}">{icon_html}{rendered_cell}</td>')
            row_htmls.append(f"<tr>{''.join(cells)}</tr>")
        tbody = f"<tbody>{''.join(row_htmls)}</tbody>"

        source_note_html = (
            f'<div class="table-source-note" style="font-size: 11px; color: var(--theme-text-muted); margin-top: 6px; text-align: right;">{RichTextRenderer.render_text_or_markdown(block.source_note)}</div>'
            if block.source_note
            else ""
        )

        return f"""
        <div class="component-table-container">
          <table class="component-table theme-{theme.value}">
            {caption_html}
            {thead}
            {tbody}
          </table>
          {source_note_html}
        </div>
        """

    @classmethod
    def render_source(cls, block: SourceBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render clean, clickable source link or reference card normalized without query artifacts."""
        normalized = UrlNormalizer.normalize_source(block.url, block.title, block.publisher)

        clean_url = html.escape(normalized.url)
        title_escaped = html.escape(normalized.display_title)
        pub_escaped = html.escape(normalized.publisher)
        domain_escaped = html.escape(normalized.domain)
        accessed = f'<span class="source-date">Accessed: {html.escape(block.accessed_at)}</span>' if block.accessed_at else ""
        num_badge = f'<span class="source-badge">[{block.source_number}]</span> ' if block.source_number else ""

        if block.mode == "inline":
            return f"""
            <a class="component-source-inline" href="{clean_url}" target="_blank" rel="noopener noreferrer" title="{title_escaped}">
              <span class="source-icon">↗</span>
              <span class="source-label">{num_badge}{title_escaped}</span>
              <span class="source-pub">({domain_escaped})</span>
            </a>
            """

        return f"""
        <div class="component-source-card theme-{theme.value}">
          <div class="source-header">
            <span class="source-publisher">{pub_escaped}</span>
            {accessed}
          </div>
          <h4 class="source-title"><a href="{clean_url}" target="_blank" rel="noopener noreferrer">{num_badge}{title_escaped}</a></h4>
          <div class="source-link-row">
            <span class="source-domain">🔗 {domain_escaped}</span>
            <a class="source-url-btn" href="{clean_url}" target="_blank" rel="noopener noreferrer">View Source ↗</a>
          </div>
        </div>
        """

    @classmethod
    def render_callout(cls, block: CalloutBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render semantic callout box (note, important, warning, tip, definition) with Lucide icon and rich text."""
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
        content_html = RichTextRenderer.render_text_or_markdown(block.content)

        return f"""
        <div class="component-callout callout-{block.variant} theme-{theme.value}">
          <div class="callout-header">
            <span class="callout-icon">{icon_svg}</span>
            <strong class="callout-title">{html.escape(block.title)}</strong>
          </div>
          <div class="callout-content">
            <p>{content_html}</p>
          </div>
        </div>
        """

    @classmethod
    def render_icon_text(cls, block: IconTextBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render one or more text items with prominent Lucide icons."""
        title_html = (
            f'<h3 class="icon-block-title typo-heading-4" style="margin-bottom: 12px;">{html.escape(block.title)}</h3>'
            if block.title
            else ""
        )

        items_html = []
        for item in block.items:
            color_token = ColorToken.BRAND_GREEN if theme == Theme.DARK else ColorToken.BRAND_GREEN_DARK
            if item.icon_color_token:
                try:
                    color_token = validate_color_token(item.icon_color_token)
                except Exception:
                    pass

            icon_svg = render_lucide_icon(item.icon, color=color_token, size=18)
            item_title = f"<strong>{html.escape(item.title)}</strong>" if item.title else ""
            item_text = RichTextRenderer.render_text_or_markdown(item.text)

            items_html.append(
                f"""
                <div class="icon-item">
                  <div class="icon-item-badge">{icon_svg}</div>
                  <div class="icon-item-content">
                    {item_title}
                    <p>{item_text}</p>
                  </div>
                </div>
                """
            )

        return f"""
        <div class="component-icon-text layout-{block.layout} theme-{theme.value}">
          {title_html}
          <div class="icon-list-container">
            {''.join(items_html)}
          </div>
        </div>
        """

    @classmethod
    def render_chart(cls, block: ChartBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render vector SVG chart deterministic offline with DESIGN.md color tokens."""
        title_escaped = html.escape(block.title)
        subtitle_html = (
            f'<div class="chart-subtitle" style="font-size: 12px; color: var(--theme-text-muted); text-align: center; margin-bottom: 8px;">{html.escape(block.subtitle)}</div>'
            if block.subtitle
            else ""
        )
        chart_type = block.chart_type.lower()

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
            svg_content = f"""
            <div class="chart-simple-fallback" style="padding: 24px; text-align: center; color: var(--theme-accent);">
              <strong>{title_escaped}</strong>
            </div>
            """

        x_label_html = f'<div class="chart-axis-label x-label">{html.escape(block.x_label)}</div>' if block.x_label else ""
        y_label_html = f'<div class="chart-axis-label y-label">{html.escape(block.y_label)}</div>' if block.y_label else ""
        source_note_html = (
            f'<div class="chart-source-note" style="font-size: 10.5px; color: var(--theme-text-muted); text-align: right; margin-top: 6px;">{RichTextRenderer.render_text_or_markdown(block.source_note)}</div>'
            if block.source_note
            else ""
        )

        return f"""
        <div class="component-chart-container theme-{theme.value}">
          <h4 class="chart-title">{title_escaped}</h4>
          {subtitle_html}
          {y_label_html}
          <div class="chart-svg-wrapper">
            {svg_content}
          </div>
          {x_label_html}
          {source_note_html}
        </div>
        """

    @classmethod
    def render_diagram(cls, block: DiagramBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render technical diagram / architecture flowchart."""
        caption_html = (
            f'<figcaption class="diagram-caption">{RichTextRenderer.render_text_or_markdown(block.caption)}</figcaption>'
            if block.caption
            else ""
        )
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

        rendered_quote = RichTextRenderer.render_text_or_markdown(block.quote)

        return f"""
        <div class="component-quote theme-{theme.value}">
          <blockquote>
            <p>{rendered_quote}</p>
          </blockquote>
          {attribution}
        </div>
        """

    @classmethod
    def render_statistic(cls, block: StatisticBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render large number callout with optional icon."""
        desc_html = (
            f'<p class="stat-description">{RichTextRenderer.render_text_or_markdown(block.description)}</p>'
            if block.description
            else ""
        )
        icon_html = ""
        if block.icon:
            icon_col = IconColorResolver.resolve_color(theme, role="primary")
            icon_html = f'<div style="margin-bottom: 6px;">{render_lucide_icon(block.icon, color=icon_col, size=32)}</div>'

        return f"""
        <div class="component-statistic theme-{theme.value}">
          {icon_html}
          <div class="stat-value">{html.escape(block.value)}</div>
          <div class="stat-label">{html.escape(block.label)}</div>
          {desc_html}
        </div>
        """

    @classmethod
    def render_image(cls, block: ImageBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render image block with clean sanitized caption."""
        alt_text = html.escape(UrlNormalizer.clean_text_artifacts(block.alt or ""))
        src_url = html.escape(block.src)
        caption_text = UrlNormalizer.clean_text_artifacts(block.caption or "")
        caption_html = f'<figcaption class="image-caption">{html.escape(caption_text)}</figcaption>' if caption_text else ""

        return f"""
        <figure class="component-image-figure theme-{theme.value}">
          <img src="{src_url}" alt="{alt_text}" class="content-image" style="max-width: 100%; border-radius: var(--radius-md);" />
          {caption_html}
        </figure>
        """

    @classmethod
    def render_heading(cls, block: HeadingBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render section or subsection heading with optional eyebrow and Lucide icon."""
        lvl = min(max(block.level, 1), 5)
        role_cls = f" typo-{block.typography_role}" if block.typography_role else f" typo-heading-{lvl}"
        eyebrow_html = (
            f'<div class="heading-eyebrow typo-eyebrow" style="margin-bottom: 4px;">{html.escape(block.eyebrow)}</div>'
            if block.eyebrow
            else ""
        )
        icon_html = ""
        if block.icon:
            icon_col = IconColorResolver.resolve_color(theme, role="primary")
            icon_html = f'<span class="heading-icon" style="margin-right: 8px; vertical-align: middle;">{render_lucide_icon(block.icon, color=icon_col, size=24)}</span>'

        heading_text = RichTextRenderer.render_text_or_markdown(block.text)

        return f"""
        <div class="content-heading-wrapper">
          {eyebrow_html}
          <h{lvl} class="content-heading-{lvl}{role_cls}">{icon_html}{heading_text}</h{lvl}>
        </div>
        """

    @classmethod
    def render_text(cls, block: TextBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render prose text block with full rich-text formatting."""
        role_cls = f" typo-{block.typography_role}" if block.typography_role else " typo-body-md"

        if block.rich_spans:
            rendered = RichTextRenderer.render_spans(block.rich_spans)
            return f'<p class="content-body{role_cls}">{rendered}</p>'

        if block.paragraphs:
            parts = [
                f'<p class="content-body{role_cls}">{RichTextRenderer.render_text_or_markdown(p)}</p>'
                for p in block.paragraphs
            ]
            return "".join(parts)

        return f'<p class="content-body{role_cls}">{RichTextRenderer.render_text_or_markdown(block.text)}</p>'

    @classmethod
    def render_acknowledgement(cls, block: AcknowledgementBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render dedicated full-page acknowledgement editorial page."""
        icon_col = ColorToken.BRAND_GREEN if theme == Theme.DARK else ColorToken.BRAND_GREEN_DARK
        icon_svg = render_lucide_icon(block.icon or "sparkles", color=icon_col, size=40)
        lead_html = f'<p class="ack-lead">{RichTextRenderer.render_text_or_markdown(block.lead)}</p>' if block.lead else ""

        if block.paragraphs:
            p_tags = "".join(f'<p>{RichTextRenderer.render_text_or_markdown(p)}</p>' for p in block.paragraphs)
            body_html = f'<div class="ack-body">{p_tags}</div>'
        elif block.body:
            body_html = f'<div class="ack-body"><p>{RichTextRenderer.render_text_or_markdown(block.body)}</p></div>'
        else:
            body_html = ""

        contributors_html = ""
        if block.contributors:
            items = "".join(f'<li>{html.escape(c)}</li>' for c in block.contributors)
            contributors_html = f'<div class="ack-contributors" style="margin-top: 24px;"><h3 style="font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px; color: var(--theme-text-muted);">Special Acknowledgements</h3><ul style="list-style: none; padding-left: 0; display: flex; flex-direction: column; gap: 8px;">{items}</ul></div>'

        signature_html = ""
        if block.signature:
            affil = f'<span class="ack-signature-affil">{html.escape(block.affiliation)}</span>' if block.affiliation else ""
            signature_html = f"""
            <div class="ack-signature-block">
              <span class="ack-signature-name">— {html.escape(block.signature)}</span>
              {affil}
            </div>
            """

        return f"""
        <div class="acknowledgement-container theme-{theme.value}">
          <div class="ack-header">
            <div class="ack-icon-wrapper">{icon_svg}</div>
            <h1 class="ack-title">{html.escape(block.title)}</h1>
            <div class="copyright-divider"></div>
          </div>
          {lead_html}
          {body_html}
          {contributors_html}
          {signature_html}
        </div>
        """


    @classmethod
    def render_copyright(cls, block: CopyrightBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render dedicated full-page copyright, publishing notice, and distribution restrictions."""
        title_escaped = html.escape(block.book_title or block.title)
        subtitle_html = (
            f'<p class="copyright-subtitle">{html.escape(block.book_subtitle)}</p>'
            if block.book_subtitle
            else ""
        )

        rights_notice = block.rights_notice or (
            f"Copyright © {block.year} {html.escape(block.rights_holder)}. All rights reserved.<br><br>"
            "No part of this publication may be reproduced, distributed, transmitted, stored, copied, "
            "republished, or shared in any form or by any means without prior written permission from the copyright holder, "
            "except where permitted by applicable law or brief quotations used for review, education, or scholarly citation."
        )

        restrictions = block.distribution_restrictions or (
            "<strong>Distribution Notice:</strong> Unauthorized redistribution, resale, republication, "
            "or commercial exploitation of this technical document is strictly prohibited without explicit written authorization."
        )

        isbn_html = (
            f'<div class="copyright-meta-item"><strong>ISBN</strong><span>{html.escape(block.isbn)}</span></div>'
            if block.isbn
            else ""
        )

        theme_val = getattr(theme, "value", str(theme))
        return f"""
        <div class="copyright-container theme-{theme_val}">
          <div class="copyright-header">
            <div class="typo-eyebrow" style="margin-bottom: 6px;">Publication Information</div>
            <h1 class="copyright-title">{title_escaped}</h1>
            {subtitle_html}
            <div class="copyright-divider"></div>
          </div>

          <div class="copyright-meta-grid">
            <div class="copyright-meta-item">
              <strong>Published By</strong>
              <span>{html.escape(block.publisher)}</span>
            </div>
            <div class="copyright-meta-item">
              <strong>Edition</strong>
              <span>{html.escape(block.edition)} ({block.year})</span>
            </div>
            <div class="copyright-meta-item">
              <strong>Rights Holder</strong>
              <span>{html.escape(block.rights_holder)}</span>
            </div>
            {isbn_html}
          </div>

          <div class="copyright-rights-notice">
            <p>{rights_notice}</p>
          </div>

          <div class="copyright-restriction-box">
            <p>{restrictions}</p>
          </div>

          <div class="copyright-footer-legal">
            <span>Published via {html.escape(getattr(block, 'engine', None) or 'VasukiSquare AI Publishing Engine')}</span>
            {f'<span>{html.escape(block.website.strip())}</span>' if getattr(block, 'website', None) and block.website.strip() else ''}
          </div>
        </div>
        """

    @classmethod
    def render_toc(cls, block: TocBlock, theme: Theme = Theme.LIGHT) -> str:
        """Render high-contrast, editorial Table of Contents with resolved page numbers and dotted leaders."""
        title_escaped = html.escape(block.title or "Table of Contents")
        subtitle_html = (
            f'<p class="toc-subtitle">{html.escape(block.subtitle)}</p>'
            if block.subtitle
            else ""
        )

        entries_html = []
        for entry in block.entries:
            ch_num_html = ""
            if entry.chapter_number is not None:
                ch_num_html = f'<span class="toc-chapter-badge">Chapter {entry.chapter_number}</span>'
            
            icon_html = ""
            if entry.icon:
                icon_col = IconColorResolver.resolve_color(theme, role="primary")
                icon_html = f'<span class="toc-icon">{render_lucide_icon(entry.icon, color=icon_col, size=16)}</span>'

            title_rendered = RichTextRenderer.render_text_or_markdown(entry.title)

            entries_html.append(
                f"""
                <div class="toc-row">
                  <div class="toc-row-left">
                    {ch_num_html}
                    {icon_html}
                    <span class="toc-row-title">{title_rendered}</span>
                  </div>
                  <div class="toc-dots-leader"></div>
                  <div class="toc-row-page">{entry.page_number}</div>
                </div>
                """
            )

        theme_val = getattr(theme, "value", str(theme))
        return f"""
        <div class="component-toc theme-{theme_val}">
          <div class="toc-header">
            <div class="typo-eyebrow">Contents</div>
            <h1 class="toc-title">{title_escaped}</h1>
            {subtitle_html}
            <div class="toc-divider"></div>
          </div>
          <div class="toc-entries-list">
            {''.join(entries_html)}
          </div>
        </div>
        """

