"""Cover preflight and contrast validator for VasukiSquare covers."""

import re
from typing import List, Optional
from pydantic import BaseModel, Field
from vasukisquare.book.models import CoverDesignPlan
from vasukisquare.cover.styles import ALL_COVER_STYLES
from vasukisquare.cover.contrast import (
    CoverContrastReport,
    calculate_contrast_ratio,
    validate_cover_contrast,
)


class CoverValidationReport(BaseModel):
    """Result of cover preflight, readability, and contrast validation checks."""

    valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    style: str = ""
    author: str = ""
    seed: int = 0
    contrast_report: Optional[CoverContrastReport] = None
    footer_strip_exists: bool = True
    footer_strip_full_width: bool = True
    footer_strip_touches_bottom: bool = True
    footer_metadata_inside_strip: bool = True
    author_contrast_pass: bool = True
    edition_contrast_pass: bool = True
    no_metadata_over_artwork: bool = True


class CoverValidator:
    """Validates rendered cover specifications, typography contrast/readability, and publisher layout rules."""

    @staticmethod
    def validate_cover_contrast(
        background_color: str,
        title_color: Optional[str] = None,
        subtitle_color: Optional[str] = None,
        author_color: Optional[str] = None,
        edition_color: Optional[str] = None,
        category_color: Optional[str] = None,
        header_color: Optional[str] = None,
        container_bg: Optional[str] = None,
        footer_bg: Optional[str] = None,
        auto_correct: bool = True,
    ) -> CoverContrastReport:
        """Validate text contrast independently across title, subtitle, author, edition, category, and header."""
        return validate_cover_contrast(
            background_color=background_color,
            title_color=title_color,
            subtitle_color=subtitle_color,
            author_color=author_color,
            edition_color=edition_color,
            category_color=category_color,
            header_color=header_color,
            container_bg=container_bg,
            footer_bg=footer_bg,
            auto_correct=auto_correct,
        )

    @staticmethod
    def validate_cover(plan: CoverDesignPlan, html_content: str) -> CoverValidationReport:
        errors = []
        warnings = []

        # 1. Style validation
        style = plan.cover_style or plan.composition_style
        if style not in ALL_COVER_STYLES:
            warnings.append(f"Style '{style}' is not in standard 10 CoverStyle families.")

        # 2. Title validation
        if not plan.title or not plan.title.strip():
            errors.append("Cover title is missing or empty.")
        elif plan.title not in html_content and plan.title.lower() not in html_content.lower():
            errors.append("Rendered cover HTML does not contain the book title.")

        # 3. Author validation
        expected_author = plan.author or "Vasuki"
        if expected_author not in html_content:
            errors.append(f"Rendered cover HTML does not contain author '{expected_author}'.")

        # 4. Brand label removal validation
        # The generic top-left 'VASUKISQUARE' label must not be rendered on the cover
        if 'class="cover-brand-label"' in html_content:
            errors.append("Found forbidden 'cover-brand-label' class on cover.")
        if '<span class="cover-brand-label">VASUKISQUARE</span>' in html_content:
            errors.append("Found forbidden generic VASUKISQUARE brand header on cover.")

        # 5. Full-bleed and background validation
        bg = (plan.background_color or "").lower()
        if not bg:
            errors.append("Cover background color is not specified.")

        # 6. Solid Dark Title Container Preflight
        # The title + subtitle must sit inside a solid opaque dark container
        if "cover-title-container" not in html_content:
            warnings.append("Cover does not use 'cover-title-container' wrapper.")
        else:
            # Verify container is not transparent
            cont_match = re.search(r"class=\"cover-title-container\"[^>]*style=\"([^\"]*)\"", html_content)
            if cont_match:
                cont_style = cont_match.group(1).lower()
                if "background-color: transparent" in cont_style or "opacity: 0" in cont_style or "rgba(0, 0, 0, 0)" in cont_style:
                    errors.append("Title container must have a solid opaque background color to prevent artwork lines crossing.")

        # 7. Extract colors & evaluate contrast
        container_bg = "#001e2b"
        cont_bg_m = re.search(r"class=\"cover-title-container\"[^>]*style=\"[^\"]*background-color:\s*([^;\"'>]+)", html_content)
        if cont_bg_m:
            container_bg = cont_bg_m.group(1).strip()

        footer_bg = "#001e2b"
        foot_bg_m = re.search(r"class=\"[^\"]*cover-footer-strip[^\"]*\"[^>]*style=\"[^\"]*background-color:\s*([^;\"'>]+)", html_content)
        if not foot_bg_m:
            foot_style_m = re.search(r"\.cover-footer-strip\s*\{[^}]*background-color:\s*([^;}\s]+)", html_content)
            if foot_style_m:
                footer_bg = foot_style_m.group(1).strip()
        else:
            footer_bg = foot_bg_m.group(1).strip()

        # Extract actual title color from HTML if present
        title_color = None
        h1_match = re.search(r"<h1[^>]*style=\"[^\"]*color:\s*([^;\"'>]+)", html_content)
        if h1_match:
            title_color = h1_match.group(1).strip()

        # Extract subtitle color
        subtitle_color = None
        p_match = re.search(r"<p[^>]*style=\"[^\"]*color:\s*([^;\"'>]+)", html_content)
        if p_match:
            subtitle_color = p_match.group(1).strip()

        # Extract author / edition color
        author_color = None
        auth_match = re.search(r"<(?:div|span)[^>]*style=\"[^\"]*color:\s*([^;\"'>]+)[^\"]*\"[^>]*>\s*" + re.escape(expected_author), html_content)
        if auth_match:
            author_color = auth_match.group(1).strip()

        edition_color = None
        ed_match = re.search(r"<(?:div|span)[^>]*style=\"[^\"]*color:\s*([^;\"'>]+)[^\"]*\"[^>]*>\s*FIRST EDITION", html_content)
        if ed_match:
            edition_color = ed_match.group(1).strip()

        contrast_report: Optional[CoverContrastReport] = None
        if bg and html_content:
            contrast_report = validate_cover_contrast(
                background_color=bg,
                title_color=title_color,
                subtitle_color=subtitle_color,
                author_color=author_color,
                edition_color=edition_color,
                container_bg=container_bg,
                footer_bg=footer_bg,
                auto_correct=True,
            )
            if not contrast_report.valid:
                errors.extend(contrast_report.errors)

        # 8. Subtitle-Artwork Collision Preflight
        if plan.subtitle:
            sub_len = len(plan.subtitle)
            if sub_len > 180:
                warnings.append(f"Subtitle length ({sub_len} chars) may crowd cover artwork. Recommended <= 140 chars.")

        # 9. Cover Bottom Footer Strip Preflight Checks
        footer_strip_exists = False
        footer_strip_full_width = False
        footer_strip_touches_bottom = False
        footer_metadata_inside_strip = False
        author_contrast_pass = True
        edition_contrast_pass = True
        no_metadata_over_artwork = False

        footer_match = re.search(r"<footer[^>]*class=\"([^\"]*cover-footer[^\"]*)\"[^>]*>(.*?)</footer>", html_content, re.DOTALL | re.IGNORECASE)
        if not footer_match:
            footer_match = re.search(r"<footer[^>]*>(.*?)</footer>", html_content, re.DOTALL | re.IGNORECASE)
        if not footer_match:
            footer_match = re.search(r"<div[^>]*class=\"([^\"]*cover-footer-strip[^\"]*)\"[^>]*>(.*?)</div>\s*</div>\s*$", html_content, re.DOTALL | re.IGNORECASE)

        if footer_match:
            footer_strip_exists = True
            footer_tag_full = footer_match.group(0)
            footer_inner = footer_match.group(2)

            # Width check (100% width)
            if "width: 100%" in html_content or "width: 100%" in footer_tag_full or ("left: 0" in footer_tag_full and "right: 0" in footer_tag_full):
                footer_strip_full_width = True
            else:
                errors.append("footer_strip_full_width fail: Footer strip must span 100% of cover width.")

            # Touches bottom check (bottom: 0)
            if "bottom: 0" in html_content or "bottom: 0px" in footer_tag_full or "bottom: 0" in footer_tag_full:
                footer_strip_touches_bottom = True
            else:
                errors.append("footer_strip_touches_bottom fail: Footer strip must touch physical bottom edge (bottom: 0).")

            # Metadata inside strip check
            if expected_author in footer_inner and ("FIRST EDITION" in footer_inner or "EDITION" in footer_inner):
                footer_metadata_inside_strip = True
            else:
                errors.append("footer_metadata_inside_strip fail: Author and edition must be placed inside the footer strip.")

            # Solid / non-transparent check (no metadata floating directly over artwork)
            is_transparent = (
                "background-color: transparent" in footer_tag_full
                or "opacity: 0" in footer_tag_full
                or "rgba(0, 0, 0, 0)" in footer_tag_full
                or "background: transparent" in footer_tag_full
            )
            if is_transparent:
                errors.append("no_metadata_over_artwork fail: Footer strip must have a solid opaque background color.")
                no_metadata_over_artwork = False
            else:
                no_metadata_over_artwork = footer_strip_exists and footer_metadata_inside_strip

            # Author & edition contrast checks against footer_bg
            if author_color:
                ac_ratio = calculate_contrast_ratio(footer_bg, author_color)
                if ac_ratio < 4.5:
                    author_contrast_pass = False
                    errors.append(f"author_contrast_pass fail: Author contrast {ac_ratio:.2f}:1 < 4.5:1 vs footer background '{footer_bg}'.")
            if edition_color:
                ec_ratio = calculate_contrast_ratio(footer_bg, edition_color)
                if ec_ratio < 4.5:
                    edition_contrast_pass = False
                    errors.append(f"edition_contrast_pass fail: Edition contrast {ec_ratio:.2f}:1 < 4.5:1 vs footer background '{footer_bg}'.")
        else:
            footer_strip_exists = False
            footer_strip_full_width = False
            footer_strip_touches_bottom = False
            footer_metadata_inside_strip = False
            no_metadata_over_artwork = False
            errors.append("footer_strip_exists fail: Cover is missing required solid bottom footer strip (.cover-footer-strip).")

        return CoverValidationReport(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            style=style,
            author=expected_author,
            seed=plan.cover_seed,
            contrast_report=contrast_report,
            footer_strip_exists=footer_strip_exists,
            footer_strip_full_width=footer_strip_full_width,
            footer_strip_touches_bottom=footer_strip_touches_bottom,
            footer_metadata_inside_strip=footer_metadata_inside_strip,
            author_contrast_pass=author_contrast_pass,
            edition_contrast_pass=edition_contrast_pass,
            no_metadata_over_artwork=no_metadata_over_artwork,
        )
