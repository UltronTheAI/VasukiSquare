"""Content density, word count, code/command validation, and technical quality validator for book pages."""

import logging
import re
from typing import Any, List, Optional
from pydantic import BaseModel, Field

from vasukisquare.book.models import PageContent
from vasukisquare.book.components import ContentBlock
from vasukisquare.book.layout import TechnicalPageSpec, TechnicalPageType, PAGE_TYPE_SPECS

logger = logging.getLogger(__name__)


class ContentValidationResult(BaseModel):
    """Result of evaluating generated page content density and completeness."""

    is_valid: bool = Field(description="Whether page satisfies quality and density criteria")
    word_count: int = Field(description="Estimated total words in prose and component blocks")
    needs_expansion: bool = Field(default=False, description="True if content is too sparse (< 250 words)")
    issues: List[str] = Field(default_factory=list, description="Specific quality issues detected")
    suggestions: List[str] = Field(default_factory=list, description="Suggested additions for expansion")


COMMON_CLI_BINARIES = {
    "npm", "npx", "yarn", "pnpm", "pip", "pip3", "python", "python3", "docker", "docker-compose",
    "git", "curl", "wget", "node", "cargo", "rustc", "go", "brew", "apt", "apt-get", "apk",
    "yum", "systemctl", "service", "mkdir", "cd", "cat", "echo", "export", "source", "touch",
    "rm", "cp", "mv", "chmod", "chown", "tar", "unzip", "ps", "kill", "grep", "sed", "awk",
    "bash", "sh", "zsh", "sudo", "make", "cmake", "dotnet", "mvn", "gradle", "kubectl", "helm",
    "terraform", "ansible", "psql", "mysql", "mongosh", "redis-cli", "lioran", "liorandb",
    "uvicorn", "gunicorn", "pytest", "ruff", "mypy", "black", "flake8", "eslint", "prettier"
}

PROSE_PREFIXES = (
    "in this example", "first install", "first,", "to install", "you can run", "we will",
    "this command", "here is", "the following", "make sure", "note that", "lioran is",
    "liorandb is", "python is", "docker is", "simply run", "execute the"
)

CODE_SYNTAX_PATTERNS = [
    r"\bdef\s+[a-zA-Z_]\w*\s*\(",
    r"\bclass\s+[a-zA-Z_]\w*",
    r"\bimport\s+[a-zA-Z_]",
    r"\bfrom\s+[a-zA-Z_.]+\s+import\b",
    r"\bconst\s+[a-zA-Z_]",
    r"\blet\s+[a-zA-Z_]",
    r"\bvar\s+[a-zA-Z_]",
    r"\bfunction\s+[a-zA-Z_]*\s*\(",
    r"\breturn\b",
    r"\basync\s+def\b",
    r"\basync\s+function\b",
    r"\bawait\b",
    r"\bSELECT\b.*?\bFROM\b",
    r"\bINSERT\s+INTO\b",
    r"\bCREATE\s+TABLE\b",
    r"\bSELECT\b",
    r"\bfn\s+[a-zA-Z_]",
    r"\bpub\s+fn\b",
    r"\bstruct\s+[a-zA-Z_]",
    r"\bpackage\s+[a-zA-Z_]",
    r"\bfunc\s+[a-zA-Z_]",
    r":=",
    r"->",
    r"=>",
    r"console\.log\(",
    r"print\(",
    r"@[\w.]+",
    r"[{};]",
    r"\b(if|for|while)\s*\(.*?\)\s*\{",
    r"\b(if|for|while|with|try|except|finally)\b.*?:",
]

ZK_CRYPTOGRAPHY_TERMS = [
    "zero-knowledge proof", "zero knowledge proof", "zk-snark", "zk-stark", "zk-rollup",
    "zksnark", "zkstark", "zkrollup", "cryptographic proof", "verifier and prover",
    "succinct non-interactive", "zk proof", "zkproof", "polynomial commitment"
]

GENERIC_BOILERPLATE_PATTERNS = [
    r"When implementing .*, software engineers must balance runtime execution throughput",
    r"The architecture of .* requires evaluating trade-offs between",
    r"In modern software engineering, .* is an essential paradigm that",
]


def validate_terminal_command(command: str) -> bool:
    """Validate that command contains real shell/CLI commands and not conversational prose."""
    if not command or not command.strip():
        return False

    clean = command.strip()
    clean_lower = clean.lower()

    # Reject if it starts with obvious prose introductions
    for prefix in PROSE_PREFIXES:
        if clean_lower.startswith(prefix) and not any(flag in clean for flag in ["--", " -", "http", "$", "/"]):
            return False

    # Check lines
    lines = [line.strip() for line in clean.split("\n") if line.strip()]
    if not lines:
        return False

    valid_command_lines = 0
    for line in lines:
        if line.startswith("#"):
            continue

        line_clean = re.sub(r'^\$\s*', '', line).strip()
        if not line_clean:
            continue

        first_token = line_clean.split()[0].lower()
        if first_token == "sudo" and len(line_clean.split()) > 1:
            first_token = line_clean.split()[1].lower()

        has_cli_flag = bool(re.search(r'(?:^|\s)-{1,2}[a-zA-Z0-9]', line_clean))
        has_cli_operators = any(c in line_clean for c in ["|", ">", "<", "&&", ";", "$", "/", "\\", "="])
        is_known_binary = first_token in COMMON_CLI_BINARIES or first_token.startswith("./") or first_token.startswith("http")

        # Prose indicators: English sentences with verbs and periods
        has_prose_phrase = any(w in line_clean.lower() for w in [" is a ", " are ", " was ", " designed for ", " allows you ", " can be "])
        is_prose_sentence = (
            (len(line_clean.split()) >= 5 and line_clean.endswith(".") and not (has_cli_flag or has_cli_operators))
            or has_prose_phrase
        )

        if (is_known_binary or has_cli_flag or has_cli_operators) and not is_prose_sentence:
            valid_command_lines += 1

    return valid_command_lines > 0


def validate_code_block(code: str, language: str = "python") -> bool:
    """Validate that code contains actual source code and not English prose."""
    if not code or not code.strip():
        return False

    clean = code.strip()
    clean_lower = clean.lower()

    # Reject prose introductions
    for prefix in PROSE_PREFIXES:
        if clean_lower.startswith(prefix) and not any(k in clean for k in ["def ", "class ", "import ", "const ", "{", "print("]):
            return False

    matches = 0
    for pat in CODE_SYNTAX_PATTERNS:
        if re.search(pat, clean, re.IGNORECASE):
            matches += 1

    has_assignment = bool(re.search(r'[\w\s]+=\s*[\w\d"\'{\[]+', clean))
    has_brackets = "{" in clean or "(" in clean or "[" in clean

    lines = [l.strip() for l in clean.split("\n") if l.strip()]
    if len(lines) == 1 and len(lines[0].split()) > 10 and not (has_assignment or has_brackets or matches > 0):
        return False

    return matches >= 1 or (has_assignment and has_brackets)


def detect_topic_drift(text: str, primary_subject: str, is_beginner: bool = False) -> List[str]:
    """Detect topic drift such as hallucinated zero-knowledge cryptography or repeated boilerplate."""
    issues = []
    if not text:
        return issues

    text_lower = text.lower()
    subject_lower = primary_subject.lower()

    is_actual_zk_subject = any(zk in subject_lower for zk in ["zero-knowledge", "zero knowledge", "zk-", "cryptography"])

    if not is_actual_zk_subject:
        for term in ZK_CRYPTOGRAPHY_TERMS:
            if term in text_lower:
                issues.append(f"Detected topic drift: Hallucinated zero-knowledge cryptography concept '{term}' for unrelated subject '{primary_subject}' (Title 'From Zero Knowledge' denotes beginner level, not ZK cryptography).")
                break

    for pat in GENERIC_BOILERPLATE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            issues.append(f"Detected repetitive generic boilerplate matching pattern: {pat}")

    return issues


def count_page_words(page: PageContent) -> int:
    """Calculate total word count across prose paragraphs and all component blocks."""
    total_words = 0

    if page.headline:
        total_words += len(re.findall(r'\b\w+\b', page.headline))
    if page.body:
        total_words += len(re.findall(r'\b\w+\b', page.body))

    if hasattr(page, "sections") and page.sections:
        for s in page.sections:
            if hasattr(s, "heading") and s.heading:
                total_words += len(re.findall(r'\b\w+\b', s.heading))
            if hasattr(s, "body") and s.body:
                total_words += len(re.findall(r'\b\w+\b', s.body))
            if hasattr(s, "content") and s.content:
                total_words += len(re.findall(r'\b\w+\b', s.content))

    for block in getattr(page, "blocks", []):
        if hasattr(block, "text") and block.text:
            total_words += len(re.findall(r'\b\w+\b', str(block.text)))
        if hasattr(block, "title") and block.title:
            total_words += len(re.findall(r'\b\w+\b', str(block.title)))
        if hasattr(block, "paragraphs") and block.paragraphs:
            for p in block.paragraphs:
                total_words += len(re.findall(r'\b\w+\b', str(p)))
        if hasattr(block, "content") and block.content:
            total_words += len(re.findall(r'\b\w+\b', str(block.content)))
        if hasattr(block, "code") and block.code:
            total_words += len(re.findall(r'\b\w+\b', str(block.code)))
        if hasattr(block, "caption") and block.caption:
            total_words += len(re.findall(r'\b\w+\b', str(block.caption)))
        if hasattr(block, "lines") and block.lines:
            for line in block.lines:
                txt = getattr(line, "text", str(line))
                total_words += len(re.findall(r'\b\w+\b', txt))
        if hasattr(block, "quote") and block.quote:
            total_words += len(re.findall(r'\b\w+\b', str(block.quote)))
        if hasattr(block, "steps") and block.steps:
            for step in block.steps:
                if isinstance(step, dict):
                    for v in step.values():
                        total_words += len(re.findall(r'\b\w+\b', str(v)))
                else:
                    total_words += len(re.findall(r'\b\w+\b', str(step)))
        if hasattr(block, "instructions") and block.instructions:
            for inst in block.instructions:
                total_words += len(re.findall(r'\b\w+\b', str(inst)))
        if hasattr(block, "columns") and block.columns:
            for col in block.columns:
                total_words += len(re.findall(r'\b\w+\b', str(col)))
        if hasattr(block, "rows") and block.rows:
            for row in block.rows:
                for cell in row:
                    total_words += len(re.findall(r'\b\w+\b', str(cell)))
        if hasattr(block, "left_items") and block.left_items:
            for item in block.left_items:
                total_words += len(re.findall(r'\b\w+\b', str(item)))
        if hasattr(block, "right_items") and block.right_items:
            for item in block.right_items:
                total_words += len(re.findall(r'\b\w+\b', str(item)))

    return total_words


def evaluate_technical_page(
    page: PageContent,
    spec: TechnicalPageSpec,
    primary_subject: str = "technical topic",
    is_beginner: bool = False,
    research: Optional[Any] = None,
) -> ContentValidationResult:
    """Evaluate technical page against strict component contracts, code/command validity, and topic drift."""
    issues = []
    suggestions = []

    words = count_page_words(page)

    # 1. Topic drift check on all prose
    full_text = f"{page.headline or ''} {page.body or ''}"
    for b in getattr(page, "blocks", []):
        if hasattr(b, "text"):
            full_text += f" {b.text}"
        if hasattr(b, "content"):
            full_text += f" {b.content}"
    drift_issues = detect_topic_drift(full_text, primary_subject, is_beginner)
    issues.extend(drift_issues)

    # 2. Check blocks
    blocks = getattr(page, "blocks", [])
    has_terminal = False
    has_code = False
    has_table = False
    has_callout = False
    has_diagram = False
    has_step = False

    for b in blocks:
        b_type = getattr(b, "type", "")
        if b_type == "terminal":
            lines = getattr(b, "lines", [])
            cmd_text = "\n".join([line.text for line in lines if getattr(line, "kind", "") == "command" or getattr(line, "type", "") == "command"])
            if not cmd_text:
                cmd_text = getattr(b, "command", "") or getattr(b, "content", "")
            if validate_terminal_command(cmd_text):
                has_terminal = True
            else:
                issues.append(f"TerminalBlock command failed validation: contains prose instead of shell command ('{cmd_text[:60]}...')")
        elif b_type == "code":
            code_text = getattr(b, "code", "")
            code_lang = getattr(b, "language", "python")
            if validate_code_block(code_text, code_lang):
                has_code = True
            else:
                issues.append(f"CodeBlock failed validation: contains prose instead of source code ('{code_text[:60]}...')")
        elif b_type == "table":
            has_table = True
        elif b_type == "callout":
            has_callout = True
        elif b_type == "diagram":
            has_diagram = True
        elif b_type == "step":
            has_step = True

    # 3. Spec requirements
    if spec.requires_terminal and not has_terminal:
        issues.append(f"Page type '{spec.page_type.value}' requires a valid TerminalBlock with executable CLI command.")
        suggestions.append("Inject a verified TerminalBlock with valid installation or execution commands.")

    if spec.requires_code and not has_code:
        issues.append(f"Page type '{spec.page_type.value}' requires a valid CodeBlock with syntactically valid code.")
        suggestions.append("Inject a verified CodeBlock with working runnable code.")

    if spec.requires_table and not has_table:
        issues.append(f"Page type '{spec.page_type.value}' requires a structured TableBlock.")
        suggestions.append("Add a TableBlock summarizing parameters or comparisons.")

    if words < spec.target_word_count_min:
        issues.append(f"Page word count ({words}) is below spec minimum ({spec.target_word_count_min})")

    is_valid = len(issues) == 0
    return ContentValidationResult(
        is_valid=is_valid,
        word_count=words,
        needs_expansion=words < spec.target_word_count_min,
        issues=issues,
        suggestions=suggestions,
    )


def validate_page_content(
    page: PageContent,
    page_type: str = "content",
    is_technical: bool = True,
    min_words: int = 150,
    target_words: int = 350,
    primary_subject: str = "technical topic",
    is_beginner: bool = False,
) -> ContentValidationResult:
    """Validate page against density, structure, and technical requirements."""
    if page_type in ("chapter_opener", "cover", "toc", "copyright", "title", "half_title"):
        return ContentValidationResult(
            is_valid=True,
            word_count=50,
            needs_expansion=False,
            issues=[],
            suggestions=[],
        )

    words = count_page_words(page)
    issues = []
    suggestions = []

    # Check for placeholder text
    full_text_str = str(page.model_dump() if hasattr(page, "model_dump") else page)
    placeholder_patterns = [r"lorem ipsum", r"\[todo\]", r"\[placeholder\]", r"insert text here", r"sample text"]
    for pat in placeholder_patterns:
        if re.search(pat, full_text_str, re.IGNORECASE):
            issues.append(f"Detected placeholder text matching '{pat}'")

    # Topic drift check
    drift = detect_topic_drift(full_text_str, primary_subject, is_beginner)
    issues.extend(drift)

    # Word count check
    needs_expansion = False
    if words < min_words:
        needs_expansion = True
        issues.append(f"Page word count ({words}) is below minimum density threshold ({min_words} words)")
        suggestions.append("Add detailed explanations, concrete examples, or technical component blocks (Terminal/Code/Callout)")

    # Technical check
    if is_technical and page_type == "content":
        has_technical_block = False
        for b in getattr(page, "blocks", []):
            b_type = getattr(b, "type", "")
            if b_type in ("code", "terminal", "table", "step", "exercise", "comparison", "diagram"):
                has_technical_block = True
                break
        if not has_technical_block and words < target_words:
            suggestions.append("Add a practical CodeBlock, Terminal command, or StepBlock to enhance technical teaching.")

    is_valid = len(issues) == 0 and not needs_expansion

    return ContentValidationResult(
        is_valid=is_valid,
        word_count=words,
        needs_expansion=needs_expansion,
        issues=issues,
        suggestions=suggestions,
    )

