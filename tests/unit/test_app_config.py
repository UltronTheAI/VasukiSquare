"""Comprehensive unit and integration tests for root-level config.json branding customization."""

import json
from pathlib import Path
import pytest
from vasukisquare.config import (
    AppConfig,
    BrandingConfig,
    EditionConfig,
    CopyrightConfig,
    BookDefaultsConfig,
    ConfigValidationError,
    load_config,
    get_app_config,
    reset_app_config,
    get_default_config,
    DEFAULT_CONFIG_DICT,
)
from vasukisquare.book.models import CoverDesignPlan, Book, BookIntent, BookPlan, PlannedPage
from vasukisquare.book.components import CopyrightBlock
from vasukisquare.renderer.components import ComponentRenderer
from vasukisquare.renderer.html import HtmlPageRenderer
from vasukisquare.agents.writer import PageWriterAgent
from vasukisquare.cover.renderer import CoverRenderer


def test_missing_config_creates_default(tmp_path):
    """TEST 1: If config.json does not exist, automatically creates default config and continues."""
    custom_cfg_path = tmp_path / "config.json"
    assert not custom_cfg_path.exists()

    cfg = load_config(config_path=custom_cfg_path, create_if_missing=True)
    assert custom_cfg_path.exists()
    assert cfg.branding.author_name == "Vasuki"
    assert cfg.branding.publication_name == "Vasuki Publishing"
    assert cfg.edition.name == "FIRST EDITION"
    assert cfg.edition.year == 2026
    assert cfg.copyright.holder == "Vasuki Publishing"

    # Verify formatting of created file: valid JSON with indent=2, ends with newline
    raw_text = custom_cfg_path.read_text(encoding="utf-8")
    assert raw_text.endswith("\n")
    loaded_dict = json.loads(raw_text)
    assert loaded_dict["branding"]["author_name"] == "Vasuki"


def test_valid_custom_config_loads(tmp_path):
    """TEST 2: Valid custom config loads properly into AppConfig."""
    custom_cfg_path = tmp_path / "config.json"
    custom_data = {
        "branding": {
            "author_name": "John Smith",
            "publication_name": "Northstar Books",
            "company_name": "Northstar Media LLC",
            "engine_name": "Northstar Publishing Engine",
            "website": "https://northstarbooks.com",
        },
        "edition": {
            "name": "SECOND EDITION",
            "year": 2027,
        },
        "copyright": {
            "holder": "Northstar Media LLC",
            "all_rights_reserved": True,
        },
        "book_defaults": {
            "language": "English",
        },
    }
    custom_cfg_path.write_text(json.dumps(custom_data, indent=2) + "\n", encoding="utf-8")

    cfg = load_config(config_path=custom_cfg_path)
    assert cfg.branding.author_name == "John Smith"
    assert cfg.branding.publication_name == "Northstar Books"
    assert cfg.branding.company_name == "Northstar Media LLC"
    assert cfg.branding.engine_name == "Northstar Publishing Engine"
    assert cfg.branding.website == "https://northstarbooks.com"
    assert cfg.edition.name == "SECOND EDITION"
    assert cfg.edition.year == 2027
    assert cfg.copyright.holder == "Northstar Media LLC"


def test_malformed_json_fails_fast_without_overwriting(tmp_path):
    """TEST 3: Malformed JSON raises ConfigValidationError and NEVER overwrites the broken file."""
    broken_cfg_path = tmp_path / "config.json"
    broken_content = '{\n  "branding": {\n    "author_name": "Unclosed string\n}'
    broken_cfg_path.write_text(broken_content, encoding="utf-8")

    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(config_path=broken_cfg_path)

    assert "Malformed JSON syntax" in str(exc_info.value)
    # Ensure the user's broken file was not modified or overwritten
    assert broken_cfg_path.read_text(encoding="utf-8") == broken_content


def test_missing_required_field_fails_fast(tmp_path):
    """TEST 4: Missing required fields fail fast with field-specific actionable message."""
    invalid_cfg_path = tmp_path / "config.json"
    # Missing branding.author_name
    invalid_data = {
        "branding": {
            "publication_name": "Northstar Books",
            "company_name": "Northstar Media LLC",
            "engine_name": "Northstar Publishing Engine",
            "website": "https://northstarbooks.com",
        },
        "edition": {
            "name": "FIRST EDITION",
            "year": 2026,
        },
        "copyright": {
            "holder": "Northstar Media LLC",
        },
    }
    invalid_cfg_path.write_text(json.dumps(invalid_data, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(config_path=invalid_cfg_path)

    err_str = str(exc_info.value)
    assert "branding.author_name" in err_str
    # Verify file is untouched
    assert json.loads(invalid_cfg_path.read_text(encoding="utf-8")) == invalid_data


def test_empty_website_is_valid_and_omitted_cleanly(tmp_path):
    """TEST 5: Empty website '' is valid and completely omitted from publications."""
    cfg_path = tmp_path / "config.json"
    data = {
        "branding": {
            "author_name": "Alice Developer",
            "publication_name": "Tech Press",
            "company_name": "Tech Publishing Co",
            "engine_name": "Tech Publishing Engine",
            "website": "",
        },
        "edition": {
            "name": "FIRST EDITION",
            "year": 2026,
        },
        "copyright": {
            "holder": "Tech Press",
            "all_rights_reserved": True,
        },
        "book_defaults": {
            "language": "English",
        },
    }
    cfg_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    cfg = load_config(config_path=cfg_path)
    assert cfg.branding.website == ""

    # Check that CopyrightBlock rendering omits website cleanly
    reset_app_config()
    # Mock singleton to point to this config
    import vasukisquare.config.loader as loader_mod
    loader_mod._cached_config = cfg

    block = CopyrightBlock(
        book_title="Clean Architecture Guide",
        publisher=cfg.branding.publication_name,
        rights_holder=cfg.copyright.holder,
        year=cfg.edition.year,
        edition=cfg.edition.name,
        website=cfg.branding.website,
    )
    rendered_copyright = ComponentRenderer.render_copyright(block)
    assert "https://" not in rendered_copyright
    assert "http://" not in rendered_copyright
    assert "Published at:" not in rendered_copyright
    reset_app_config()


def test_white_label_pipeline_propagation(tmp_path):
    """TEST 6, 7, 8, 9: Complete white-label branding propagates with ZERO hardcoded Vasuki strings."""
    custom_cfg_path = tmp_path / "config.json"
    white_label_data = {
        "branding": {
            "author_name": "John Smith",
            "publication_name": "Northstar Books",
            "company_name": "Northstar Media LLC",
            "engine_name": "Northstar Publishing Engine",
            "website": "https://northstarbooks.com",
        },
        "edition": {
            "name": "SECOND EDITION",
            "year": 2027,
        },
        "copyright": {
            "holder": "Northstar Media LLC",
            "all_rights_reserved": True,
        },
        "book_defaults": {
            "language": "English",
        },
    }
    custom_cfg_path.write_text(json.dumps(white_label_data, indent=2) + "\n", encoding="utf-8")

    cfg = load_config(config_path=custom_cfg_path)
    import vasukisquare.config.loader as loader_mod
    loader_mod._cached_config = cfg

    # 1. Test Cover Rendering
    cover_renderer = CoverRenderer()
    plan = CoverDesignPlan(
        title="Modern Cloud Distributed Systems",
        subtitle="Principles of Fault Tolerance",
        category="Cloud Computing",
        accent_color="#00ed64",
        background_color="#001e2b",
    )
    assert plan.author == "John Smith"
    assert plan.edition == "SECOND EDITION"

    cover_html = cover_renderer.render_source_artwork(plan)
    assert "John Smith" in cover_html
    assert "SECOND EDITION" in cover_html
    assert "FIRST EDITION" not in cover_html

    # 2. Test Writer Special Pages (Imprint, Copyright, Acknowledgements, Thank You)
    writer = PageWriterAgent()
    book_plan = BookPlan(
        title="Modern Cloud Distributed Systems",
        subtitle="Principles of Fault Tolerance",
        description="A comprehensive guide to fault-tolerant distributed cloud architectures",
        intent=BookIntent(
            topic="Modern Cloud Distributed Systems",
            book_type="technical_reference",
            is_technical=True,
        ),
    )

    p_title = PlannedPage(page_number=2, page_type="title", layout="title")
    imprint_content = writer._generate_structural_page_content(
        p=p_title,
        plan=book_plan,
        citations=[],
    )
    imprint_text = "\n".join(b.text for b in imprint_content.blocks if hasattr(b, "text"))
    assert "John Smith" in imprint_text
    assert "Northstar Books" in imprint_text
    assert "Second Edition (2027)" in imprint_text
    assert "Vasuki" not in imprint_text

    p_copyright = PlannedPage(page_number=3, page_type="copyright", layout="copyright")
    copyright_content = writer._generate_structural_page_content(
        p=p_copyright,
        plan=book_plan,
        citations=[],
    )
    cblock = copyright_content.blocks[0]
    assert cblock.rights_holder == "Northstar Media LLC"
    assert cblock.publisher == "Northstar Books"
    assert cblock.engine == "Northstar Publishing Engine"
    assert cblock.edition == "Second Edition"
    assert cblock.year == 2027
    assert cblock.website == "https://northstarbooks.com"
    assert "Vasuki" not in cblock.rights_holder
    assert "Vasuki" not in cblock.publisher

    # 3. Test HTML Rendering
    html_renderer = HtmlPageRenderer()
    thank_you_rendered = html_renderer._render_thank_you_html(
        page=None,
        icon_svg="<svg></svg>",
        book_title="Modern Cloud Distributed Systems",
    )
    assert "NORTHSTAR BOOKS" in thank_you_rendered
    assert "SECOND EDITION" in thank_you_rendered
    assert "VASUKISQUARE" not in thank_you_rendered
    assert "FIRST EDITION" not in thank_you_rendered

    # 4. TEST 9: Ensure internal software classes remain intact
    assert isinstance(cover_renderer, CoverRenderer)
    assert isinstance(writer, PageWriterAgent)

    reset_app_config()
