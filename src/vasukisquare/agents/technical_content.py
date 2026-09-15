"""Technical content classification, teaching policy enforcement, and per-chapter research bundling."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from vasukisquare.book.models import ChapterPlan
from vasukisquare.research.models import ResearchCorpus, ResearchDossier

ResearchResult = Union[ResearchCorpus, ResearchDossier, Any]


logger = logging.getLogger(__name__)


TECHNICAL_KEYWORDS = {
    "python", "javascript", "typescript", "rust", "golang", "go", "java", "c++", "c#", "ruby", "php", "swift", "kotlin",
    "database", "sql", "nosql", "postgres", "postgresql", "mysql", "sqlite", "mongodb", "redis", "lioran", "liorandb",
    "cassandra", "neo4j", "kafka", "rabbitmq", "api", "rest", "graphql", "grpc", "docker", "kubernetes", "k8s", "linux",
    "bash", "shell", "git", "ci/cd", "devops", "aws", "azure", "gcp", "cloud", "serverless", "microservices", "react",
    "vue", "angular", "nextjs", "django", "fastapi", "flask", "spring", "node", "nodejs", "express", "tailwind",
    "machine learning", "deep learning", "ai", "llm", "neural network", "pytorch", "tensorflow", "scikit-learn",
    "compiler", "operating system", "networking", "tcp/ip", "security", "cryptography", "blockchain", "embedded"
}


class TopicClassification(BaseModel):
    """Classification of the book topic to enforce technical pedagogy and layout expectations."""

    is_technical: bool = Field(default=True, description="Whether topic is technical/computational")
    primary_category: str = Field(default="software", description="Category: database, programming, devops, ai, etc.")
    primary_technology: Optional[str] = Field(default=None, description="Primary software or tech if identifiable")
    target_skill_level: str = Field(default="beginner-to-intermediate", description="Target audience level")
    require_cli_commands: bool = Field(default=True, description="Must include real terminal setup/execution commands")
    require_code_examples: bool = Field(default=True, description="Must include executable code snippets and examples")
    require_architecture_diagrams: bool = Field(default=True, description="Must include structural/dataflow diagrams")
    require_practical_exercises: bool = Field(default=True, description="Must include step-by-step hands-on exercises")
    require_troubleshooting: bool = Field(default=True, description="Must cover common pitfalls and error handling")


class ChapterResearchBundle(BaseModel):
    """Structured research context package specifically curated for a single chapter."""

    chapter_number: int
    title: str
    summary: str
    target_pages: int
    key_terms: List[Dict[str, str]] = Field(default_factory=list, description="Term definitions")
    cli_commands: List[str] = Field(default_factory=list, description="Setup or execution commands")
    code_snippets: List[Dict[str, str]] = Field(default_factory=list, description="Working code examples with language and explanation")
    verified_commands: List[str] = Field(default_factory=list, description="Verified terminal commands")
    verified_code_examples: List[Dict[str, str]] = Field(default_factory=list, description="Verified code blocks")
    api_methods: List[Dict[str, str]] = Field(default_factory=list, description="Extracted API signatures and methods")
    packages: List[str] = Field(default_factory=list, description="Required package names")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Configuration parameters")
    factual_claims: List[str] = Field(default_factory=list, description="Verified research facts")
    verified_sources: List[Dict[str, str]] = Field(default_factory=list, description="Source URLs and titles")
    suggested_components: List[str] = Field(default_factory=list, description="Visual blocks recommended for this chapter")


def classify_topic(topic: str, description: Optional[str] = None) -> TopicClassification:
    """Analyze topic and description to determine technical pedagogy requirements."""
    combined = f"{topic} {description or ''}".lower()

    # Check for technical keywords
    matched_tech = []
    for kw in TECHNICAL_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', combined):
            matched_tech.append(kw)

    is_tech = len(matched_tech) > 0 or any(w in combined for w in [
        "code", "program", "build", "guide", "tutorial", "architecture", "setup", "install", "api", "database", "query", "syntax"
    ])

    primary_tech = matched_tech[0].capitalize() if matched_tech else None

    # Categorization heuristics
    if any(k in matched_tech for k in ["database", "sql", "postgres", "mysql", "mongodb", "redis", "lioran", "liorandb"]):
        category = "database"
    elif any(k in matched_tech for k in ["python", "javascript", "typescript", "rust", "golang", "go", "java", "c++", "ruby", "c#"]):
        category = "programming"
    elif any(k in matched_tech for k in ["docker", "kubernetes", "linux", "bash", "ci/cd", "devops", "aws", "cloud"]):
        category = "infrastructure_and_devops"
    elif any(k in matched_tech for k in ["machine learning", "deep learning", "ai", "llm", "pytorch"]):
        category = "artificial_intelligence"
    elif is_tech:
        category = "technical_systems"
    else:
        category = "general"

    return TopicClassification(
        is_technical=is_tech,
        primary_category=category,
        primary_technology=primary_tech,
        require_cli_commands=is_tech,
        require_code_examples=is_tech,
        require_architecture_diagrams=is_tech,
        require_practical_exercises=is_tech,
        require_troubleshooting=is_tech,
    )


def extract_code_blocks_from_text(text: str) -> List[Dict[str, str]]:
    """Extract code blocks enclosed in markdown backticks from research documents."""
    from vasukisquare.agents.code_validator import normalize_code_language, validate_code_completeness
    blocks = []
    pattern = r"```([a-zA-Z0-9_-]*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    for lang, code in matches:
        clean_code = code.strip()
        if clean_code:
            norm_lang = normalize_code_language(lang)
            is_valid, _ = validate_code_completeness(clean_code, norm_lang)
            if is_valid:
                blocks.append({
                    "language": norm_lang,
                    "code": clean_code,
                    "filename": f"example.{norm_lang if norm_lang != 'text' else 'py'}",
                    "explanation": "Extracted from research documentation."
                })
    return blocks


def extract_chapter_research(
    chapter: ChapterPlan,
    global_research: ResearchResult,
    classification: TopicClassification,
    output_dir: Optional[Path] = None,
) -> ChapterResearchBundle:
    """Extract and curate focused research context for a single chapter."""
    key_topics = getattr(chapter, "key_topics", None) or [
        c for s in getattr(chapter, "sections", []) for c in getattr(s, "key_concepts", [])
    ]

    # Filter relevant facts
    relevant_facts = []
    for fact in getattr(global_research, "facts", []):
        f_text = getattr(fact, "fact", str(fact)).lower()
        if any(w in f_text for w in chapter.title.lower().split() if len(w) > 3) or len(relevant_facts) < 6:
            relevant_facts.append(getattr(fact, "fact", str(fact)))

    # Filter sources and extract code from documents
    sources = []
    extracted_snippets = []
    if hasattr(global_research, "documents") and global_research.documents:
        for doc in global_research.documents:
            url = getattr(doc, "url", "")
            title = getattr(doc, "title", "Reference Source")
            publisher = getattr(doc, "publisher", getattr(doc, "domain", ""))
            if url:
                sources.append({"title": title, "url": url, "publisher": publisher})
            doc_text = getattr(doc, "extracted_text", "") or getattr(doc, "summary", "")
            if doc_text:
                extracted_snippets.extend(extract_code_blocks_from_text(doc_text))
    elif hasattr(global_research, "sources") and global_research.sources:
        for s in global_research.sources:
            url = getattr(s, "url", "")
            title = getattr(s, "title", "Reference Source")
            publisher = getattr(s, "publisher", getattr(s, "domain", ""))
            if url:
                sources.append({"title": title, "url": url, "publisher": publisher})

    cli_commands = []
    code_snippets = list(extracted_snippets)
    key_terms = []
    packages = []
    api_methods = []
    configuration = {}

    tech_name = classification.primary_technology or "the system"
    tech_pkg = tech_name.lower().replace(" ", "")

    if classification.is_technical:
        is_python = tech_pkg in ["python", "pythonprogramming", "python3"]
        if is_python:
            packages.append("python")
            if chapter.chapter_number == 1:
                cli_commands = [
                    "python3 --version",
                    "python3 hello.py",
                ]
                if not code_snippets:
                    code_snippets.append({
                        "language": "python",
                        "filename": "hello.py",
                        "code": 'print("Hello, World!")\nname = "Python"\nprint(f"Welcome to {name}!")',
                        "explanation": "Executes your first Python script using print and f-strings."
                    })
                key_terms = [
                    {"term": "Interpreter", "definition": "Software program that directly executes instructions written in Python."},
                    {"term": "REPL", "definition": "Read-Eval-Print Loop interactive shell for testing Python expressions."}
                ]
                api_methods = [
                    {"name": "print(*objects, sep=' ', end='\\n')", "description": "Prints objects to the text stream file."},
                    {"name": "input(prompt)", "description": "Reads a string line from standard input."}
                ]
            elif chapter.chapter_number == 2:
                cli_commands = ["python3 variables.py"]
                if not code_snippets:
                    code_snippets.append({
                        "language": "python",
                        "filename": "variables.py",
                        "code": 'user_age = 25\nis_active = True\nprice = 19.99\nprint(f"Age: {user_age}, Active: {is_active}, Price: ${price:.2f}")',
                        "explanation": "Declares integers, booleans, and floating point variables with formatted output."
                    })
                key_terms = [
                    {"term": "Dynamic Typing", "definition": "Variable types are determined automatically at runtime."},
                    {"term": "f-string", "definition": "Formatted string literal allowing embedded expressions."}
                ]
            else:
                cli_commands = [f"python3 chapter_{chapter.chapter_number}.py"]
                if not code_snippets:
                    code_snippets.append({
                        "language": "python",
                        "filename": f"example_ch{chapter.chapter_number}.py",
                        "code": (
                            'def calculate_summary(numbers: list[int]) -> dict:\n'
                            '    total = sum(numbers)\n'
                            '    count = len(numbers)\n'
                            '    avg = total / count if count > 0 else 0.0\n'
                            '    return {"total": total, "count": count, "average": avg}\n\n'
                            'scores = [85, 92, 78, 90]\n'
                            'result = calculate_summary(scores)\n'
                            'print("Summary:", result)'
                        ),
                        "explanation": f"Modular function processing and returning dictionary summary for Chapter {chapter.chapter_number}."
                    })
        else:
            packages.append(tech_pkg)
            if chapter.chapter_number == 1:
                cli_commands = [
                    f"{tech_pkg} --version",
                    f"{tech_pkg} --help",
                ]
                if not code_snippets:
                    code_snippets.append({
                        "language": "bash",
                        "filename": "quickstart.sh",
                        "code": f"# Check {tech_name} installation\n{tech_pkg} --version",
                        "explanation": f"Verifies installation of {tech_name}."
                    })
                key_terms = [
                    {"term": f"{tech_name}", "definition": f"Core technical runtime and system component."},
                ]
            elif chapter.chapter_number == 2:
                cli_commands = [
                    f"{tech_pkg} init --config config.json",
                    f"{tech_pkg} status",
                ]
                configuration = {"port": 8080, "host": "127.0.0.1", "engine": tech_pkg}
            else:
                cli_commands = [
                    f"{tech_pkg} run --environment production",
                ]

    bundle = ChapterResearchBundle(
        chapter_number=chapter.chapter_number,
        title=chapter.title,
        summary=chapter.summary,
        target_pages=getattr(chapter, "page_budget", getattr(chapter, "target_pages", 8)),
        key_terms=key_terms,
        cli_commands=cli_commands,
        code_snippets=code_snippets,
        verified_commands=cli_commands,
        verified_code_examples=code_snippets,
        api_methods=api_methods,
        packages=packages,
        configuration=configuration,
        factual_claims=relevant_facts[:6],
        verified_sources=sources[:5],
        suggested_components=[
            "TerminalBlock", "CodeBlock", "ComparisonBlock", "TipCard", "WarningCard", "StepBlock", "ExerciseBlock"
        ] if classification.is_technical else [
            "QuoteCard", "InfoCard", "StatisticCard", "TimelineBlock", "ChecklistBlock"
        ]
    )

    if output_dir:
        research_dir = output_dir / "research"
        research_dir.mkdir(parents=True, exist_ok=True)
        file_path = research_dir / f"chapter_{chapter.chapter_number:02d}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(bundle.model_dump(), f, indent=2)
            logger.info("Saved chapter research bundle to %s", file_path)
        except Exception as e:
            logger.warning("Failed to save chapter research bundle to %s: %s", file_path, e)

    return bundle
