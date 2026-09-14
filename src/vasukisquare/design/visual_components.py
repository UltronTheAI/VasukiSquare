"""Visual component renderers and helpers for rich A4 book page layouts.

Supports 16 standard visual component blocks:
1. IconCard
2. InfoCard
3. WarningCard
4. TipCard
5. StatisticCard
6. QuoteCard
7. CodeBlock
8. TerminalBlock
9. ChartBlock
10. DiagramBlock
11. ComparisonBlock
12. TimelineBlock
13. ChecklistBlock
14. StepBlock
15. DefinitionBlock
16. ExerciseBlock
"""

import html
from typing import Any, Dict, List, Optional
from vasukisquare.design.icons import render_lucide_icon, IconColorResolver
from vasukisquare.design.theme import Theme
from vasukisquare.design.tokens import ColorToken
from vasukisquare.renderer.richtext import RichTextRenderer


def render_icon_card(
    title: str,
    description: str,
    icon: str = "sparkles",
    icon_color: Optional[str] = None,
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render a modern visual icon card with styled Lucide icon."""
    if not (title or "").strip() and not (description or "").strip():
        return ""
    color = icon_color or IconColorResolver.resolve_color(theme, role="primary")
    icon_svg = render_lucide_icon(icon, color=color, size=24)
    rendered_title = html.escape(title)
    rendered_desc = RichTextRenderer.render_text_or_markdown(description)
    return f"""
    <div class="component-card component-icon-card theme-{theme.value}">
      <div class="card-icon-header">
        <span class="card-icon-badge">{icon_svg}</span>
        <h4 class="card-title">{rendered_title}</h4>
      </div>
      <div class="card-body">
        <p>{rendered_desc}</p>
      </div>
    </div>
    """


def render_info_card(
    title: str,
    content: str,
    icon: str = "info",
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render an informational callout card."""
    if not (content or "").strip() and not (title or "").strip():
        return ""
    color = IconColorResolver.resolve_color(theme, role="primary")
    icon_svg = render_lucide_icon(icon, color=color, size=20)
    rendered_title = html.escape(title)
    rendered_content = RichTextRenderer.render_text_or_markdown(content)
    return f"""
    <div class="component-callout callout-info theme-{theme.value}">
      <div class="callout-header">
        <span class="callout-icon">{icon_svg}</span>
        <strong class="callout-title">{rendered_title}</strong>
      </div>
      <div class="callout-content">
        <p>{rendered_content}</p>
      </div>
    </div>
    """


def render_warning_card(
    title: str,
    content: str,
    icon: str = "alert-triangle",
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render a warning or pitfall card."""
    if not (content or "").strip() and not (title or "").strip():
        return ""
    color = "#fa6e39" if theme == Theme.LIGHT else "#ff8a50"
    icon_svg = render_lucide_icon(icon, color=color, size=20)
    rendered_title = html.escape(title)
    rendered_content = RichTextRenderer.render_text_or_markdown(content)
    return f"""
    <div class="component-callout callout-warning theme-{theme.value}">
      <div class="callout-header">
        <span class="callout-icon">{icon_svg}</span>
        <strong class="callout-title">{rendered_title}</strong>
      </div>
      <div class="callout-content">
        <p>{rendered_content}</p>
      </div>
    </div>
    """


def render_tip_card(
    title: str,
    content: str,
    icon: str = "lightbulb",
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render a pro-tip or best-practice card."""
    if not (content or "").strip() and not (title or "").strip():
        return ""
    color = "#00a35c" if theme == Theme.LIGHT else "#00ed64"
    icon_svg = render_lucide_icon(icon, color=color, size=20)
    rendered_title = html.escape(title)
    rendered_content = RichTextRenderer.render_text_or_markdown(content)
    return f"""
    <div class="component-callout callout-tip theme-{theme.value}">
      <div class="callout-header">
        <span class="callout-icon">{icon_svg}</span>
        <strong class="callout-title">{rendered_title}</strong>
      </div>
      <div class="callout-content">
        <p>{rendered_content}</p>
      </div>
    </div>
    """


def render_statistic_card(
    value: str,
    label: str,
    context: Optional[str] = None,
    icon: Optional[str] = "trending-up",
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render an impactful metric / statistic card."""
    if not (value or "").strip() or not (label or "").strip():
        return ""
    icon_html = ""
    if icon:
        color = IconColorResolver.resolve_color(theme, role="primary")
        icon_html = f'<div class="stat-icon">{render_lucide_icon(icon, color=color, size=28)}</div>'
    rendered_val = html.escape(value)
    rendered_lbl = html.escape(label)
    ctx_html = f'<p class="stat-context">{RichTextRenderer.render_text_or_markdown(context)}</p>' if context else ""
    return f"""
    <div class="component-statistic theme-{theme.value}">
      {icon_html}
      <div class="stat-value">{rendered_val}</div>
      <div class="stat-label">{rendered_lbl}</div>
      {ctx_html}
    </div>
    """


def render_quote_card(
    quote: str,
    author: Optional[str] = None,
    role: Optional[str] = None,
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render an editorial pull quote card."""
    if not (quote or "").strip():
        return ""
    rendered_quote = RichTextRenderer.render_text_or_markdown(quote)
    attribution_html = ""
    if author:
        affil = f", <em>{html.escape(role)}</em>" if role else ""
        attribution_html = f'<cite class="quote-author">— {html.escape(author)}{affil}</cite>'
    return f"""
    <div class="component-quote theme-{theme.value}">
      <blockquote>
        <p>{rendered_quote}</p>
      </blockquote>
      {attribution_html}
    </div>
    """


def render_comparison_block(
    title: str,
    left_title: str,
    left_items: List[str],
    right_title: str,
    right_items: List[str],
    left_icon: str = "check",
    right_icon: str = "x",
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render side-by-side comparison block (Do vs Don't, Option A vs Option B)."""
    valid_left = [item for item in (left_items or []) if item and str(item).strip()]
    valid_right = [item for item in (right_items or []) if item and str(item).strip()]
    if not valid_left and not valid_right:
        return ""

    left_color = "#00a35c" if theme == Theme.LIGHT else "#00ed64"
    right_color = "#fa6e39"
    l_icon = render_lucide_icon(left_icon, color=left_color, size=16)
    r_icon = render_lucide_icon(right_icon, color=right_color, size=16)

    l_list = "".join(f'<li><span class="comp-icon">{l_icon}</span><span>{RichTextRenderer.render_text_or_markdown(item)}</span></li>' for item in valid_left)
    r_list = "".join(f'<li><span class="comp-icon">{r_icon}</span><span>{RichTextRenderer.render_text_or_markdown(item)}</span></li>' for item in valid_right)

    title_html = f'<h4 class="comparison-title">{html.escape(title)}</h4>' if title else ""

    return f"""
    <div class="component-comparison theme-{theme.value}">
      {title_html}
      <div class="comparison-grid">
        <div class="comparison-col comparison-left">
          <h5 class="comparison-col-header">{html.escape(left_title)}</h5>
          <ul class="comparison-list">
            {l_list}
          </ul>
        </div>
        <div class="comparison-col comparison-right">
          <h5 class="comparison-col-header">{html.escape(right_title)}</h5>
          <ul class="comparison-list">
            {r_list}
          </ul>
        </div>
      </div>
    </div>
    """


def render_timeline_block(
    title: str,
    items: List[Dict[str, str]],
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render a vertical timeline or chronological sequence."""
    valid_items = [it for it in (items or []) if it and (it.get("title") or it.get("description") or it.get("year"))]
    if not valid_items:
        return ""

    title_html = f'<h4 class="timeline-title">{html.escape(title)}</h4>' if title else ""
    color = IconColorResolver.resolve_color(theme, role="primary")

    nodes_html = []
    for idx, item in enumerate(valid_items):
        time_tag = html.escape(item.get("time") or item.get("step") or item.get("year") or f"Phase {idx+1}")
        item_title = html.escape(item.get("title", ""))
        desc = RichTextRenderer.render_text_or_markdown(item.get("description", ""))
        dot_icon = render_lucide_icon("circle-dot", color=color, size=14)
        nodes_html.append(f"""
        <div class="timeline-item">
          <div class="timeline-marker">{dot_icon}</div>
          <div class="timeline-content">
            <span class="timeline-tag">{time_tag}</span>
            <h5 class="timeline-heading">{item_title}</h5>
            <p class="timeline-desc">{desc}</p>
          </div>
        </div>
        """)

    return f"""
    <div class="component-timeline theme-{theme.value}">
      {title_html}
      <div class="timeline-track">
        {''.join(nodes_html)}
      </div>
    </div>
    """


def render_checklist_block(
    title: str,
    items: List[Dict[str, Any]],
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render an interactive checklist / key takeaway list."""
    valid_items = []
    for it in (items or []):
        if isinstance(it, dict) and it.get("text") and str(it.get("text")).strip():
            valid_items.append(it)
        elif isinstance(it, str) and it.strip():
            valid_items.append({"text": it.strip(), "checked": True})

    if not valid_items:
        return ""

    title_html = f'<h4 class="checklist-title">{html.escape(title)}</h4>' if title else ""
    color = "#00a35c" if theme == Theme.LIGHT else "#00ed64"
    check_svg = render_lucide_icon("check-square", color=color, size=16)
    uncheck_svg = render_lucide_icon("square", color="#a8b3bc", size=16)

    rows = []
    for item in valid_items:
        text = RichTextRenderer.render_text_or_markdown(item.get("text", ""))
        is_checked = item.get("checked", True)
        ico = check_svg if is_checked else uncheck_svg
        rows.append(f"""
        <li class="checklist-row">
          <span class="checklist-checkbox">{ico}</span>
          <span class="checklist-text">{text}</span>
        </li>
        """)

    return f"""
    <div class="component-checklist theme-{theme.value}">
      {title_html}
      <ul class="checklist-items">
        {''.join(rows)}
      </ul>
    </div>
    """


def render_step_block(
    title: str,
    steps: List[Dict[str, Any]],
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render a step-by-step procedural tutorial block."""
    valid_steps = [s for s in (steps or []) if s and (s.get("title") or s.get("description") or s.get("code"))]
    if not valid_steps:
        return ""

    title_html = f'<h4 class="step-block-title">{html.escape(title)}</h4>' if title else ""

    steps_html = []
    for idx, s in enumerate(valid_steps):
        s_num = s.get("step_number", idx + 1)
        s_title = html.escape(s.get("title", f"Step {s_num}"))
        s_desc = RichTextRenderer.render_text_or_markdown(s.get("description", ""))
        code_html = ""
        if s.get("code"):
            c_text = html.escape(s.get("code", ""))
            lang = html.escape(s.get("language", "bash"))
            code_html = f'<pre class="step-code"><code class="language-{lang}">{c_text}</code></pre>'

        steps_html.append(f"""
        <div class="step-card">
          <div class="step-badge">{s_num}</div>
          <div class="step-details">
            <h5 class="step-heading">{s_title}</h5>
            <p class="step-desc">{s_desc}</p>
            {code_html}
          </div>
        </div>
        """)

    return f"""
    <div class="component-steps theme-{theme.value}">
      {title_html}
      <div class="step-list">
        {''.join(steps_html)}
      </div>
    </div>
    """


def render_definition_block(
    term: str,
    definition: str,
    pronunciation: Optional[str] = None,
    part_of_speech: Optional[str] = None,
    example: Optional[str] = None,
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render a formal technical glossary / definition card."""
    if not (term or "").strip() or not (definition or "").strip():
        return ""

    pron_html = f'<span class="def-pronunciation">/{html.escape(pronunciation)}/</span>' if pronunciation else ""
    pos_html = f'<span class="def-pos">({html.escape(part_of_speech)})</span>' if part_of_speech else ""
    ex_html = f'<div class="def-example"><strong>Example:</strong> {RichTextRenderer.render_text_or_markdown(example)}</div>' if example else ""

    return f"""
    <div class="component-definition theme-{theme.value}">
      <div class="def-header">
        <span class="def-icon">{render_lucide_icon('book-marked', color=IconColorResolver.resolve_color(theme, role='primary'), size=18)}</span>
        <h4 class="def-term">{html.escape(term)}</h4>
        {pron_html}
        {pos_html}
      </div>
      <div class="def-body">
        <p>{RichTextRenderer.render_text_or_markdown(definition)}</p>
      </div>
      {ex_html}
    </div>
    """


def render_exercise_block(
    title: str,
    objective: str,
    instructions: List[str],
    difficulty: str = "Intermediate",
    starter_code: Optional[str] = None,
    hints: Optional[List[str]] = None,
    theme: Theme = Theme.LIGHT,
) -> str:
    """Render a hands-on practical exercise / coding challenge block."""
    valid_instr = [i for i in (instructions or []) if i and str(i).strip()]
    if not (objective or "").strip() and not valid_instr:
        return ""

    color = IconColorResolver.resolve_color(theme, role="primary")
    icon_svg = render_lucide_icon("hammer", color=color, size=20)
    diff_badge = f'<span class="exercise-difficulty diff-{difficulty.lower()}">{html.escape(difficulty)}</span>'
    obj_html = f'<p class="exercise-objective"><strong>Objective:</strong> {RichTextRenderer.render_text_or_markdown(objective)}</p>' if (objective or "").strip() else ""

    instr_items = "".join(f'<li>{RichTextRenderer.render_text_or_markdown(i)}</li>' for i in valid_instr)
    instr_html = f'<ol class="exercise-instructions">{instr_items}</ol>' if valid_instr else ""

    code_html = ""
    if starter_code:
        code_html = f'<div class="exercise-starter"><span class="starter-label">Starter Code:</span><pre><code class="language-python">{html.escape(starter_code)}</code></pre></div>'

    hints_html = ""
    if hints:
        valid_hints = [h for h in hints if h and str(h).strip()]
        if valid_hints:
            h_items = "".join(f'<li>{RichTextRenderer.render_text_or_markdown(h)}</li>' for h in valid_hints)
            hints_html = f'<div class="exercise-hints"><strong class="hints-label">Hints & Suggestions:</strong><ul>{h_items}</ul></div>'

    return f"""
    <div class="component-exercise theme-{theme.value}">
      <div class="exercise-header">
        <div class="exercise-header-left">
          <span class="exercise-icon">{icon_svg}</span>
          <h4 class="exercise-title">{html.escape(title or 'Practice Challenge')}</h4>
        </div>
        {diff_badge}
      </div>
      <div class="exercise-body">
        {obj_html}
        {instr_html}
        {code_html}
        {hints_html}
      </div>
    </div>
    """

