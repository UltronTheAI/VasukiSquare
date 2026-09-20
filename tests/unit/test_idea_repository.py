"""Unit tests for BookIdeaRepository using Mock DB."""

import pytest

from tests.integration.test_database import create_mock_db
from vasukisquare.database.repository import BookIdeaRepository
from vasukisquare.research.models import BookIdea, IdeaScores, IdeaStatus


@pytest.fixture
def mock_db():
    return create_mock_db()


@pytest.fixture
def idea_repo(mock_db):
    return BookIdeaRepository(mock_db, collection_name="book_ideas")


def test_create_and_get_idea(idea_repo):
    idea = BookIdea(
        topic="Vector DBs",
        title="Vector DBs in Depth",
        prompt="Full prompt here",
        pages=70,
        scores=IdeaScores(trend=0.8, uniqueness=0.8, bookworthiness=0.8, evergreen=0.8, confidence=0.8),
    )
    created = idea_repo.create(idea)
    assert created.slug == "vector-dbs-in-depth"

    fetched = idea_repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.title == "Vector DBs in Depth"
    assert fetched.status == IdeaStatus.READY


def test_unique_slug_resolution(idea_repo):
    idea1 = BookIdea(
        topic="Clean Code",
        title="Clean Code Guide",
        prompt="Prompt 1",
        pages=50,
    )
    idea2 = BookIdea(
        topic="Clean Code",
        title="Clean Code Guide",
        prompt="Prompt 2",
        pages=60,
    )

    created1 = idea_repo.create(idea1)
    created2 = idea_repo.create(idea2)

    assert created1.slug == "clean-code-guide"
    assert created2.slug == "clean-code-guide-2"


def test_claim_next_ready_idea(idea_repo):
    idea = BookIdea(
        topic="High Throughput Kafka",
        title="Kafka Architecture",
        prompt="Prompt",
        pages=80,
        status=IdeaStatus.READY,
        scores=IdeaScores(trend=0.9, uniqueness=0.9, bookworthiness=0.95, evergreen=0.9, confidence=0.9),
    )
    idea_repo.create(idea)

    claimed = idea_repo.claim_next_ready_idea()
    assert claimed is not None
    assert claimed.id == idea.id
    assert claimed.status == IdeaStatus.PROCESSING
    assert claimed.attempt_count == 1
    assert claimed.claimed_at is not None

    # Claiming again returns None because no more ready ideas exist
    claimed_again = idea_repo.claim_next_ready_idea()
    assert claimed_again is None


def test_mark_completed_and_rejected(idea_repo):
    idea = BookIdea(
        topic="Rust Concurrency",
        title="Rust Concurrency",
        prompt="Prompt",
        pages=65,
        status=IdeaStatus.PROCESSING,
    )
    idea_repo.create(idea)

    # Mark completed
    completed = idea_repo.mark_completed(idea.id, book_id="book-999", output_path="/output/book.pdf")
    assert completed is not None
    assert completed.status == IdeaStatus.COMPLETED
    assert completed.generation.book_id == "book-999"
    assert completed.completed_at is not None

    # Mark rejected
    idea2 = BookIdea(
        topic="Old Tech",
        title="Old Tech Guide",
        prompt="Prompt",
        pages=45,
    )
    idea_repo.create(idea2)
    rejected = idea_repo.mark_rejected(idea2.id, reason="Duplicate topic")
    assert rejected is not None
    assert rejected.status == IdeaStatus.REJECTED
    assert rejected.rejection_reason == "Duplicate topic"


def test_get_historical_records(mock_db, idea_repo):
    # Insert existing book in books collection
    mock_db["books"].insert_one({
        "_id": "book-100",
        "title": "Existing Python Book",
        "topic": "Python Programming",
        "slug": "existing-python-book",
        "description": "A guide to Python",
    })

    # Insert idea in book_ideas collection
    idea = BookIdea(
        topic="Rust Programming",
        title="Existing Rust Book",
        prompt="Prompt",
        pages=55,
    )
    idea_repo.create(idea)

    records = idea_repo.get_historical_records()
    assert len(records) == 2
    titles = [r["title"] for r in records]
    assert "Existing Python Book" in titles
    assert "Existing Rust Book" in titles

