"""Layout selection engine enforcing anti-repetition constraints and composition variety."""

from typing import List, Optional
from vasukisquare.book.layout import LayoutType, VisualAnchorType

# Mapping from visual anchor types to preferred layout candidates in order of priority
ANCHOR_LAYOUT_PREFERENCES = {
    VisualAnchorType.CODE: [LayoutType.CODE_FOCUS, LayoutType.SPLIT_EXPLAINER, LayoutType.CASE_STUDY],
    VisualAnchorType.TABLE: [LayoutType.COMPARISON, LayoutType.CONCEPT_GRID, LayoutType.EDITORIAL],
    VisualAnchorType.DIAGRAM: [LayoutType.DIAGRAM_FOCUS, LayoutType.SPLIT_EXPLAINER, LayoutType.CONCEPT_GRID],
    VisualAnchorType.TIMELINE: [LayoutType.TIMELINE, LayoutType.CASE_STUDY, LayoutType.EDITORIAL],
    VisualAnchorType.QUOTE: [LayoutType.QUOTE, LayoutType.FULL_BLEED_STATEMENT, LayoutType.EDITORIAL],
    VisualAnchorType.COMPARISON: [LayoutType.COMPARISON, LayoutType.CONCEPT_GRID, LayoutType.SPLIT_EXPLAINER],
    VisualAnchorType.STATISTIC: [LayoutType.LARGE_NUMBER, LayoutType.RESEARCH_HIGHLIGHT, LayoutType.SUMMARY],
    VisualAnchorType.TEXT: [LayoutType.EDITORIAL, LayoutType.DEFINITION, LayoutType.SPLIT_EXPLAINER, LayoutType.SUMMARY],
}


class LayoutConstraintEngine:
    """Enforces page-to-page visual variety and prevents repetitive adjacent layouts."""

    def __init__(self, max_consecutive_same_layout: int = 1):
        self.max_consecutive_same_layout = max_consecutive_same_layout

    def select_layout(
        self,
        anchor: VisualAnchorType,
        previous_layout: Optional[LayoutType] = None,
    ) -> LayoutType:
        """Select a layout matching the visual anchor while avoiding repeating the previous layout."""
        candidates = ANCHOR_LAYOUT_PREFERENCES.get(anchor, [LayoutType.EDITORIAL, LayoutType.SPLIT_EXPLAINER])

        for candidate in candidates:
            if candidate != previous_layout:
                return candidate

        # Fallback to alternate general editorial layout
        for fallback in [LayoutType.EDITORIAL, LayoutType.SPLIT_EXPLAINER, LayoutType.CONCEPT_GRID, LayoutType.SUMMARY]:
            if fallback != previous_layout:
                return fallback

        return LayoutType.EDITORIAL

    def validate_layout_sequence(self, layouts: List[LayoutType]) -> bool:
        """Validate that a list of content page layouts contains no illegal consecutive repetitions."""
        if len(layouts) <= 1:
            return True

        for i in range(1, len(layouts)):
            curr = layouts[i]
            prev = layouts[i - 1]
            # Ignore structural pages like chapter openers
            if curr in {LayoutType.CHAPTER_OPENER, LayoutType.COVER, LayoutType.TOC}:
                continue
            if curr == prev:
                return False
        return True

