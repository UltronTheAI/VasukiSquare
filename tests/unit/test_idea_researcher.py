"""Unit tests for IdeaResearchService, research pipeline, dry-run mode, and JSON export."""

import json
from pathlib import Path
import pytest

from tests.integration.test_database import create_mock_db
from vasukisquare.config import Settings
from vasukisquare.database.repository import BookIdeaRepository
from vasukisquare.research.idea_researcher import IdeaResearchService
from vasukisquare.research.models import IdeaStatus


@pytest.fixture
def mock_settings():
    return Settings(
        app_env="test",
        vasukisquare_mock_mode=True,
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="vasukisquare_test",
        idea_collection="book_ideas",
    )


@pytest.fixture
def mock_db():
    return create_mock_db()


@pytest.fixture
def idea_repo(mock_db):
    return BookIdeaRepository(mock_db, collection_name="book_ideas")


def test_idea_research_service_mock_mode(mock_settings, idea_repo):
    service = IdeaResearchService(settings=mock_settings, repository=idea_repo)
    ideas = service.research_ideas(count=3, min_score=0.70, dry_run=False)

    assert len(ideas) == 3
    for idea in ideas:
        assert idea.status == IdeaStatus.READY
        assert 40 <= idea.pages <= 100
        assert len(idea.title) <= 50
        assert idea.scores.composite_score >= 0.70
        assert len(idea.prompt) > 100

    # Verify persisted in database
    db_ideas = idea_repo.get_by_status(IdeaStatus.READY)
    assert len(db_ideas) == 3


def test_idea_research_dry_run_mode(mock_settings, idea_repo):
    service = IdeaResearchService(settings=mock_settings, repository=idea_repo)
    ideas = service.research_ideas(count=2, min_score=0.70, dry_run=True)

    assert len(ideas) == 2
    # Verify NOT persisted in DB during dry-run
    db_ideas = idea_repo.get_by_status(IdeaStatus.READY)
    assert len(db_ideas) == 0


def test_idea_export_to_json(tmp_path, mock_settings, idea_repo):
    service = IdeaResearchService(settings=mock_settings, repository=idea_repo)
    ideas = service.research_ideas(count=2, min_score=0.70, dry_run=True)

    export_file = tmp_path / "research_ideas.json"
    exported_path = service.export_ideas_to_json(ideas, export_file)

    assert Path(exported_path).exists()
    content = json.loads(Path(exported_path).read_text(encoding="utf-8"))
    assert isinstance(content, list)
    assert len(content) == 2
    assert "topic" in content[0]
    assert "title" in content[0]
    assert "pages" in content[0]
    assert "prompt" in content[0]
    assert "scores" in content[0]
    assert "composite" in content[0]["scores"]

