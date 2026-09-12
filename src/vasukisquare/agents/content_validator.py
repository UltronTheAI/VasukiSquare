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


class PageQualityScore(BaseModel):
    """Holistic quality evaluation score measuring pedagogical rigor, density, and layout balance."""

    educational_quality: float = Field(description="Educational depth and concept clarity score (0.0 to 1.0)")
    technical_validity: float = Field(description="Accuracy and validity of code, CLI, and facts (0.0 to 1.0)")
    page_utilization: float = Field(description="Physical A4 vertical height fill ratio (0.0 to 1.0)")
    layout_balance: float = Field(description="Visual rhythm, component diversity, and readability (0.0 to 1.0)")
    duplication_score: float = Field(description="Similarity to recent pages / boilerplate repetition (0.0 = unique, 1.0 = duplicate)")
    is_accepted: bool = Field(description="Whether the page meets all production publication criteria")


def compute_page_similarity(text_or_page_a: Any, text_or_page_b: Any) -> float:
    """Calculate n-gram Jaccard similarity between two pages of text to detect duplication."""
    def extract_text(obj: Any) -> str:
        if isinstance(obj, str):
            return obj
        content = getattr(obj, "content", obj)
        return f"{getattr(content, 'headline', '') or ''} {getattr(content, 'body', '') or ''} " + " ".join(
            getattr(b, "text", "") or getattr(b, "content", "") or "" for b in getattr(content, "blocks", [])
        )

    text_a = extract_text(text_or_page_a)
    text_b = extract_text(text_or_page_b)
    if not text_a or not text_b:
        return 0.0
    
    words_a = re.findall(r'\b[a-zA-Z0-9_]{3,}\b', text_a.lower())
    words_b = re.findall(r'\b[a-zA-Z0-9_]{3,}\b', text_b.lower())
    
    if not words_a or not words_b:
        return 0.0

    # Trigram shingles
    def get_shingles(words: List[str], k: int = 3) -> set:
        if len(words) < k:
            return set(words)
        return set(" ".join(words[i : i + k]) for i in range(len(words) - k + 1))

    shingles_a = get_shingles(words_a, 3)
    shingles_b = get_shingles(words_b, 3)

    union = shingles_a.union(shingles_b)
    if not union:
        return 0.0

    intersection = shingles_a.intersection(shingles_b)
    return round(len(intersection) / len(union), 3)


def detect_repeated_sentence_boilerplate(text_or_pages: Any, seen_sentences: Optional[set] = None) -> List[str]:
    """Detect sentences repeated across different pages in the book."""
    if isinstance(text_or_pages, list):
        seen = seen_sentences if seen_sentences is not None else set()
        all_issues = []
        for p in text_or_pages:
            content = getattr(p, "content", p)
            p_text = f"{getattr(content, 'headline', '') or ''} {getattr(content, 'body', '') or ''} " + " ".join(
                getattr(b, "text", "") or getattr(b, "content", "") or "" for b in getattr(content, "blocks", [])
            )
            all_issues.extend(detect_repeated_sentence_boilerplate(p_text, seen))
        return all_issues

    text = text_or_pages or ""
    issues = []
    if not text or seen_sentences is None:
        return issues

    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip().split()) >= 6]
    for s in sentences:
        s_norm = re.sub(r'\s+', ' ', s.lower())
        if s_norm in seen_sentences:
            issues.append(f"Detected duplicate sentence across pages: '{s[:60]}...'")
        else:
            seen_sentences.add(s_norm)

    return issues


def evaluate_page_quality_score(
    page: PageContent,
    spec: TechnicalPageSpec,
    primary_subject: str = "technical topic",
    is_beginner: bool = False,
    previous_page_text: Optional[str] = None,
) -> PageQualityScore:
    """Calculate composite page quality score across educational value, technical validity, utilization, and uniqueness."""
    from vasukisquare.renderer.overflow import estimate_page_utilization

    # 1. Technical validation
    tech_val = evaluate_technical_page(page, spec, primary_subject=primary_subject, is_beginner=is_beginner)
    tech_score = 1.0 if tech_val.is_valid else max(0.2, 1.0 - (len(tech_val.issues) * 0.25))

    # 2. Page utilization
    util = estimate_page_utilization(page)
    util_ratio = util.estimated_ratio

    # Optimal range is 0.65 to 0.90
    if 0.65 <= util_ratio <= 0.92:
        util_score = 0.95
    elif util_ratio < 0.50:
        util_score = max(0.3, util_ratio / 0.70)
    elif util_ratio > 0.95:
        util_score = 0.60
    else:
        util_score = 0.80

    # 3. Educational quality
    words = count_page_words(page)
    edu_score = min(1.0, max(0.4, words / 300.0))
    if any("hallucinated" in issue.lower() for issue in tech_val.issues):
        edu_score = 0.1

    # 4. Duplication
    page_text = f"{page.headline or ''} {page.body or ''} " + " ".join(
        getattr(b, "text", "") or getattr(b, "content", "") or "" for b in getattr(page, "blocks", [])
    )
    dup_score = compute_page_similarity(page_text, previous_page_text or "") if previous_page_text else 0.0

    # 5. Layout balance (variety of component types)
    block_types = set(getattr(b, "type", "") for b in getattr(page, "blocks", []))
    layout_balance = min(1.0, 0.5 + (len(block_types) * 0.15))

    is_accepted = (
        tech_score >= 0.70
        and util_ratio >= 0.60
        and util_ratio <= 0.95
        and dup_score < 0.80
        and len(tech_val.issues) == 0
    )

    return PageQualityScore(
        educational_quality=round(edu_score, 2),
        technical_validity=round(tech_score, 2),
        page_utilization=round(util_ratio, 2),
        layout_balance=round(layout_balance, 2),
        duplication_score=round(dup_score, 2),
        is_accepted=is_accepted,
    )


