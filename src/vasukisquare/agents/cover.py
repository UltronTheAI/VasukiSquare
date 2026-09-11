"""AI-directed Cover Planner Agent designing custom covers conforming to DESIGN.md."""

import logging
from typing import Optional
from vasukisquare.config import Settings, get_settings
from vasukisquare.book.models import CoverPlan
from vasukisquare.design.tokens import ColorToken

logger = logging.getLogger(__name__)


class CoverPlannerAgent:
    """Agent responsible for planning bespoke, subject-aware cover designs within the design system."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    async def plan_cover(
        self,
        title: str,
        subtitle: Optional[str] = None,
        category: str = "Computer Science",
        tone: str = "authoritative",
        audience: str = "Engineers and Architects",
    ) -> CoverPlan:
        """Create a tailored CoverPlan using Groq/LangChain with offline deterministic fallback."""
        if not self.settings.groq_api_key:
            return self._heuristic_cover_plan(title, subtitle, category, tone, audience)

        try:
            from langchain_groq import ChatGroq
            from langchain_core.prompts import ChatPromptTemplate

            llm = ChatGroq(
                api_key=self.settings.groq_api_key,
                model_name=self.settings.groq_model,
                temperature=0.3,
            )
            structured_llm = llm.with_structured_output(CoverPlan)

            system_prompt = (
                "You are an executive art director for technical publishing. "
                "Select the optimal cover layout_style (minimal_geometric, orbital_rings, tech_matrix, abstract_mesh, layered_bands), "
                "palette_theme (brand_dark, deep_teal, accent_purple, accent_orange), and hero_icon (Lucide icon name). "
                "Ensure colors strictly map to DESIGN.md tokens."
            )

            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                (
                    "human",
                    "Title: {title}\nSubtitle: {subtitle}\nCategory: {category}\nTone: {tone}\nAudience: {audience}",
                ),
            ])

            chain = prompt_template | structured_llm
            result = await chain.ainvoke({
                "title": title,
                "subtitle": subtitle or "",
                "category": category,
                "tone": tone,
                "audience": audience,
            })
            if isinstance(result, CoverPlan):
                return result
            return self._heuristic_cover_plan(title, subtitle, category, tone, audience)
        except Exception as e:
            logger.warning(f"Cover planning LLM call failed, falling back to heuristic: {e}")
            return self._heuristic_cover_plan(title, subtitle, category, tone, audience)

    def _heuristic_cover_plan(
        self,
        title: str,
        subtitle: Optional[str] = None,
        category: str = "Computer Science",
        tone: str = "authoritative",
        audience: str = "Engineers and Architects",
    ) -> CoverPlan:
        """Deterministic cover selection based on title and domain keywords."""
        t_lower = (title + " " + (subtitle or "") + " " + category).lower()

        # Layout style selection
        if any(w in t_lower for w in ["database", "storage", "vector", "distributed", "system"]):
            layout_style = "orbital_rings"
            hero_icon = "database"
            palette = "deep_teal"
            accent = ColorToken.BRAND_GREEN.value
        elif any(w in t_lower for w in ["ai", "neural", "learning", "intelligence", "transformer"]):
            layout_style = "abstract_mesh"
            hero_icon = "sparkles"
            palette = "brand_dark"
            accent = ColorToken.ACCENT_PURPLE.value
        elif any(w in t_lower for w in ["code", "compiler", "programming", "rust", "python", "backend"]):
            layout_style = "tech_matrix"
            hero_icon = "code"
            palette = "brand_dark"
            accent = ColorToken.BRAND_GREEN.value
        elif any(w in t_lower for w in ["cloud", "infrastructure", "kubernetes", "network"]):
            layout_style = "layered_bands"
            hero_icon = "layers"
            palette = "deep_teal"
            accent = ColorToken.ACCENT_ORANGE.value
        else:
            layout_style = "minimal_geometric"
            hero_icon = "compass"
            palette = "brand_dark"
            accent = ColorToken.BRAND_GREEN.value

        return CoverPlan(
            title=title,
            subtitle=subtitle,
            category=category,
            tone=tone,
            audience=audience,
            palette_theme=palette,
            layout_style=layout_style,
            hero_icon=hero_icon,
            accent_color=accent,
            background_color=ColorToken.BRAND_TEAL_DEEP.value,
            author="VasukiSquare AI",
        )

