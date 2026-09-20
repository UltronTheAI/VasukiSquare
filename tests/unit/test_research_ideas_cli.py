"""Unit tests for scripts/research_ideas.py CLI argument parsing and execution."""

from unittest.mock import patch, MagicMock


from scripts.research_ideas import build_parser, main
from vasukisquare.research.models import BookIdea, IdeaScores


def test_cli_parser_defaults():
    parser = build_parser()
    args = parser.parse_args([])

    assert args.count == 5
    assert args.min_score == 0.70
    assert args.category is None
    assert args.dry_run is False
    assert args.export_json is None
    assert args.verbose is False


def test_cli_parser_custom_args():
    parser = build_parser()
    args = parser.parse_args([
        "--count", "10",
        "--min-score", "0.80",
        "--category", "Technology",
        "--dry-run",
        "--export-json", "artifacts/test_ideas.json",
        "--verbose",
        "--llm-provider", "groq",
    ])

    assert args.count == 10
    assert args.min_score == 0.80
    assert args.category == "Technology"
    assert args.dry_run is True
    assert args.export_json == "artifacts/test_ideas.json"
    assert args.verbose is True
    assert args.llm_provider == "groq"


def test_cli_main_dry_run_execution(tmp_path, capsys):
    export_path = str(tmp_path / "cli_ideas.json")
    test_args = ["--count", "2", "--dry-run", "--export-json", export_path]

    sample_idea = BookIdea(
        topic="Vector DBs",
        title="Vector DBs in Production",
        prompt="Full generation prompt...",
        pages=75,
        scores=IdeaScores(trend=0.85, uniqueness=0.85, bookworthiness=0.85, evergreen=0.85, confidence=0.85),
    )

    with patch("scripts.research_ideas.IdeaResearchService") as MockService:
        mock_instance = MagicMock()
        mock_instance.research_ideas.return_value = [sample_idea]
        mock_instance.export_ideas_to_json.return_value = export_path
        MockService.return_value = mock_instance

        main(test_args)

        mock_instance.research_ideas.assert_called_once_with(
            count=2,
            min_score=0.70,
            category=None,
            dry_run=True,
        )
        mock_instance.export_ideas_to_json.assert_called_once_with(
            [sample_idea],
            export_path,
        )

        captured = capsys.readouterr()
        assert "VasukiSquare Automated Idea Research" in captured.out
        assert "Vector DBs in Production" in captured.out
        assert "75 pages" in captured.out

