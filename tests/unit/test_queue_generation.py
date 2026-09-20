import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from tests.integration.test_database import create_mock_db
from vasukisquare.cli import parse_args, main_async
from vasukisquare.database.repository import BookIdeaRepository
from vasukisquare.research.models import BookIdea, IdeaScores, IdeaStatus
from vasukisquare.book.models import Book, PublicationInfo, PublicationStatus, PublicationVisibility
from vasukisquare.pipeline.state import GenerationState


@pytest.fixture
def mock_db():
    return create_mock_db()


@pytest.fixture
def idea_repo(mock_db):
    return BookIdeaRepository(mock_db, collection_name="book_ideas")


def test_cli_parser_manual_mode():
    args = parse_args(["--topic", "Kubernetes Internals", "--pages", "50"])
    assert args.topic == "Kubernetes Internals"
    assert args.pages == 50
    assert not args.from_queue
    assert args.idea_id is None


def test_cli_parser_queue_mode():
    args = parse_args(["--from-queue"])
    assert args.from_queue is True
    assert args.topic is None
    assert args.idea_id is None


def test_cli_parser_idea_id_mode():
    args = parse_args(["--idea-id", "idea_123"])
    assert args.idea_id == "idea_123"
    assert args.topic is None


def test_cli_parser_missing_topic_error():
    with pytest.raises(SystemExit):
        parse_args([])


@pytest.mark.asyncio
async def test_queue_empty_clean_exit(mock_db):
    """When queue has no ready ideas, main_async exits cleanly with None and exit code 0."""
    with patch("vasukisquare.cli.DatabaseManager") as MockDBManager:
        mock_instance = MagicMock()
        mock_instance.get_database.return_value = mock_db
        MockDBManager.return_value = mock_instance

        result = await main_async(["--from-queue"])
        assert result is None


@pytest.mark.asyncio
async def test_queue_dry_run_reverts_status(mock_db, idea_repo):
    """Dry run claims idea, prints details, and reverts status to READY without running pipeline."""
    idea = BookIdea(
        topic="Async Python Architecture",
        title="Async Python Deep Dive",
        prompt="Detailed prompt for async python.",
        pages=60,
        status=IdeaStatus.READY,
        scores=IdeaScores(trend=0.9, uniqueness=0.85, bookworthiness=0.95, evergreen=0.9, confidence=0.9),
    )
    idea_repo.create(idea)

    with patch("vasukisquare.cli.DatabaseManager") as MockDBManager, \
         patch("vasukisquare.cli.EbookGenerationPipeline") as MockPipeline:
        mock_instance = MagicMock()
        mock_instance.get_database.return_value = mock_db
        MockDBManager.return_value = mock_instance

        result = await main_async(["--from-queue", "--dry-run"])
        assert result is None
        # Pipeline should NOT be called in dry-run
        MockPipeline.assert_not_called()

        # Status in DB should be reverted to READY
        fetched = idea_repo.get_by_id(idea.id)
        assert fetched.status == IdeaStatus.READY


@pytest.mark.asyncio
async def test_queue_invalid_page_count_rejected(mock_db, idea_repo):
    """Idea with page count < 40 or > 100 is rejected and not generated."""
    idea = BookIdea(
        topic="Valid Idea Topic",
        title="Valid Idea Title",
        prompt="Prompt",
        pages=60,
        status=IdeaStatus.READY,
        scores=IdeaScores(trend=0.9, uniqueness=0.85, bookworthiness=0.95, evergreen=0.9, confidence=0.9),
    )
    idea_repo.create(idea)

    with patch("vasukisquare.cli.DatabaseManager") as MockDBManager, \
         patch("vasukisquare.cli.EbookGenerationPipeline") as MockPipeline:
        mock_instance = MagicMock()
        mock_instance.get_database.return_value = mock_db
        MockDBManager.return_value = mock_instance

        result = await main_async(["--from-queue", "--pages", "30"])
        assert result is None
        MockPipeline.assert_not_called()

        fetched = idea_repo.get_by_id(idea.id)
        assert fetched.status == IdeaStatus.REJECTED
        assert "40-100" in fetched.rejection_reason


@pytest.mark.asyncio
async def test_queue_successful_generation_flow(mock_db, idea_repo):
    """Successful generation claims idea, executes pipeline, links book, and marks COMPLETED."""
    idea = BookIdea(
        topic="Distributed Consensus in Rust",
        title="Distributed Consensus in Rust",
        prompt="Deep dive into Raft and Paxos.",
        pages=75,
        status=IdeaStatus.READY,
        scores=IdeaScores(trend=0.92, uniqueness=0.88, bookworthiness=0.96, evergreen=0.9, confidence=0.95),
    )
    idea_repo.create(idea)

    # Prepare fake generation state
    fake_book = Book(
        id="book_generated_123",
        title="Distributed Consensus in Rust",
        topic="Distributed Consensus in Rust",
        prompt="Deep dive into Raft and Paxos.",
        idea_id=idea.id,
        publication=PublicationInfo(status=PublicationStatus.PUBLISHED, visibility=PublicationVisibility.PUBLIC),
    )
    fake_state = GenerationState(topic=idea.topic)
    fake_state.book = fake_book
    fake_state.pages = [MagicMock() for _ in range(75)]
    fake_state.artifacts = {"book_html": "/output/distributed-consensus.html"}

    with patch("vasukisquare.cli.DatabaseManager") as MockDBManager, \
         patch("vasukisquare.cli.EbookGenerationPipeline") as MockPipeline:
        mock_instance = MagicMock()
        mock_instance.get_database.return_value = mock_db
        MockDBManager.return_value = mock_instance

        mock_pipeline_inst = MagicMock()
        mock_pipeline_inst.run = AsyncMock(return_value=fake_state)
        MockPipeline.return_value = mock_pipeline_inst

        result = await main_async(["--from-queue"])
        assert result == fake_state

        # Check that pipeline.run was called with idea's parameters
        mock_pipeline_inst.run.assert_awaited_once_with(
            topic=idea.topic,
            title=idea.title,
            prompt=idea.prompt,
            target_pages=75,
            output_dir=Path("./output"),
            generate_pdf=True,
            persist_db=True,
            resume=False,
            idea_id=idea.id,
        )

        # Check idea transition to COMPLETED
        fetched = idea_repo.get_by_id(idea.id)
        assert fetched.status == IdeaStatus.COMPLETED
        assert fetched.generation.book_id == "book_generated_123"
        assert fetched.generation.output_path == "/output/distributed-consensus.html"


@pytest.mark.asyncio
async def test_queue_failed_generation_flow(mock_db, idea_repo):
    """Pipeline failure sets idea to FAILED with error message and re-raises exception."""
    idea = BookIdea(
        topic="High Frequency Trading Systems",
        title="HFT Systems",
        prompt="Low latency trading.",
        pages=55,
        status=IdeaStatus.READY,
        scores=IdeaScores(trend=0.85, uniqueness=0.85, bookworthiness=0.9, evergreen=0.85, confidence=0.85),
    )
    idea_repo.create(idea)

    with patch("vasukisquare.cli.DatabaseManager") as MockDBManager, \
         patch("vasukisquare.cli.EbookGenerationPipeline") as MockPipeline:
        mock_instance = MagicMock()
        mock_instance.get_database.return_value = mock_db
        MockDBManager.return_value = mock_instance

        mock_pipeline_inst = MagicMock()
        mock_pipeline_inst.run = AsyncMock(side_effect=RuntimeError("GPU/LLM Out of Memory"))
        MockPipeline.return_value = mock_pipeline_inst

        with pytest.raises(RuntimeError, match="GPU/LLM Out of Memory"):
            await main_async(["--from-queue"])

        fetched = idea_repo.get_by_id(idea.id)
        assert fetched.status == IdeaStatus.FAILED
        assert "GPU/LLM Out of Memory" in fetched.generation.error


@pytest.mark.asyncio
async def test_queue_specific_idea_id(mock_db, idea_repo):
    """Generating with --idea-id claims that specific idea."""
    idea1 = BookIdea(
        topic="Topic 1",
        title="Title 1",
        prompt="Prompt 1",
        pages=50,
        status=IdeaStatus.READY,
        scores=IdeaScores(trend=0.9, uniqueness=0.9, bookworthiness=0.9, evergreen=0.9, confidence=0.9),
    )
    idea2 = BookIdea(
        topic="Topic 2",
        title="Title 2",
        prompt="Prompt 2",
        pages=60,
        status=IdeaStatus.READY,
        scores=IdeaScores(trend=0.8, uniqueness=0.8, bookworthiness=0.8, evergreen=0.8, confidence=0.8),
    )
    idea_repo.create(idea1)
    idea_repo.create(idea2)

    with patch("vasukisquare.cli.DatabaseManager") as MockDBManager, \
         patch("vasukisquare.cli.EbookGenerationPipeline") as MockPipeline:
        mock_instance = MagicMock()
        mock_instance.get_database.return_value = mock_db
        MockDBManager.return_value = mock_instance

        mock_pipeline_inst = MagicMock()
        fake_state = GenerationState(topic=idea2.topic)
        fake_state.pages = [MagicMock() for _ in range(60)]
        mock_pipeline_inst.run = AsyncMock(return_value=fake_state)
        MockPipeline.return_value = mock_pipeline_inst

        await main_async(["--idea-id", idea2.id])

        fetched1 = idea_repo.get_by_id(idea1.id)
        fetched2 = idea_repo.get_by_id(idea2.id)

        assert fetched1.status == IdeaStatus.READY
        assert fetched2.status == IdeaStatus.COMPLETED


def test_queue_concurrency_atomic_claim(idea_repo):
    """Two concurrent workers claim distinct ideas without collision."""
    idea1 = BookIdea(
        topic="Concurrent Architecture 1",
        title="Title 1",
        prompt="Prompt 1",
        pages=50,
        status=IdeaStatus.READY,
        scores=IdeaScores(trend=0.9, uniqueness=0.9, bookworthiness=0.95, evergreen=0.9, confidence=0.9),
    )
    idea2 = BookIdea(
        topic="Concurrent Architecture 2",
        title="Title 2",
        prompt="Prompt 2",
        pages=55,
        status=IdeaStatus.READY,
        scores=IdeaScores(trend=0.85, uniqueness=0.85, bookworthiness=0.88, evergreen=0.85, confidence=0.85),
    )
    idea_repo.create(idea1)
    idea_repo.create(idea2)

    claim1 = idea_repo.claim_next_ready_idea()
    claim2 = idea_repo.claim_next_ready_idea()
    claim3 = idea_repo.claim_next_ready_idea()

    assert claim1 is not None
    assert claim2 is not None
    assert claim3 is None
    assert claim1.id != claim2.id
    assert claim1.id == idea1.id  # Higher bookworthiness score (0.95 vs 0.88)
    assert claim2.id == idea2.id


def test_queue_stale_claim_recovery(mock_db, idea_repo):
    """An idea stuck in PROCESSING past stale timeout is recovered and claimed."""
    stale_time = datetime.now(timezone.utc) - timedelta(hours=4)
    idea = BookIdea(
        topic="Stale Processing Idea",
        title="Stale Idea",
        prompt="Prompt",
        pages=50,
        status=IdeaStatus.PROCESSING,
        claimed_at=stale_time,
        attempt_count=1,
        scores=IdeaScores(trend=0.9, uniqueness=0.9, bookworthiness=0.9, evergreen=0.9, confidence=0.9),
    )
    idea_repo.create(idea)

    # Claim with stale timeout of 180 minutes (3 hours)
    reclaimed = idea_repo.claim_next_ready_idea(stale_timeout_minutes=180, max_attempts=3)
    assert reclaimed is not None
    assert reclaimed.id == idea.id
    assert reclaimed.status == IdeaStatus.PROCESSING
    assert reclaimed.attempt_count == 2


def test_queue_max_attempts_exceeded(mock_db, idea_repo):
    """An idea that has reached max_attempts is never claimed again."""
    stale_time = datetime.now(timezone.utc) - timedelta(hours=4)
    idea = BookIdea(
        topic="Max Attempts Idea",
        title="Max Attempts Idea",
        prompt="Prompt",
        pages=50,
        status=IdeaStatus.PROCESSING,
        claimed_at=stale_time,
        attempt_count=3,
        scores=IdeaScores(trend=0.9, uniqueness=0.9, bookworthiness=0.9, evergreen=0.9, confidence=0.9),
    )
    idea_repo.create(idea)

    claimed = idea_repo.claim_next_ready_idea(stale_timeout_minutes=180, max_attempts=3)
    assert claimed is None


def test_queue_failure_exhausts_attempts_transitions_rejected(mock_db, idea_repo):
    """When an idea fails on its final attempt, it transitions to REJECTED."""
    idea = BookIdea(
        topic="Final Attempt Idea",
        title="Final Attempt Idea",
        prompt="Prompt",
        pages=50,
        status=IdeaStatus.PROCESSING,
        attempt_count=3,
        scores=IdeaScores(trend=0.9, uniqueness=0.9, bookworthiness=0.9, evergreen=0.9, confidence=0.9),
    )
    idea_repo.create(idea)

    rejected = idea_repo.mark_failed(idea.id, error="Fatal network failure", max_attempts=3)
    assert rejected is not None
    assert rejected.status == IdeaStatus.REJECTED
    assert "Max generation attempts" in rejected.rejection_reason


def test_completed_idea_terminal_cannot_update(mock_db, idea_repo):
    """Completed ideas are terminal and cannot have status updated via update_status."""
    idea = BookIdea(
        topic="Completed Idea",
        title="Completed Idea",
        prompt="Prompt",
        pages=50,
        status=IdeaStatus.READY,
        scores=IdeaScores(trend=0.9, uniqueness=0.9, bookworthiness=0.9, evergreen=0.9, confidence=0.9),
    )
    idea_repo.create(idea)
    idea_repo.mark_completed(idea.id, book_id="book_123")

    updated = idea_repo.update_status(idea.id, IdeaStatus.READY)
    assert updated is not None
    assert updated.status == IdeaStatus.COMPLETED  # Stays COMPLETED


def test_database_manager_get_database_compatibility(mock_db):
    """DatabaseManager provides both .db and .get_database() returning the configured Database."""
    from vasukisquare.database.connection import DatabaseManager
    db_mgr = DatabaseManager(db=mock_db)
    assert db_mgr.db is mock_db
    assert db_mgr.get_database() is mock_db


@pytest.mark.asyncio
async def test_queue_mode_with_real_db_manager(mock_db):
    """Queue mode works end-to-end when DatabaseManager is instantiated directly with mock db."""
    from vasukisquare.database.connection import DatabaseManager
    real_db_mgr = DatabaseManager(db=mock_db)
    with patch("vasukisquare.cli.DatabaseManager", return_value=real_db_mgr):
        result = await main_async(["--from-queue"])
        assert result is None

