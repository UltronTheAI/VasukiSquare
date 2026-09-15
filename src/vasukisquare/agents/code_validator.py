"""Language-independent and language-aware code completeness validation and repair utilities."""

import ast
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("vasukisquare.code_validator")

# Universal Language Name Normalization Map
LANGUAGE_ALIASES: Dict[str, str] = {
    "python": "python",
    "py": "python",
    "python3": "python",
    "py3": "python",
    "javascript": "javascript",
    "js": "javascript",
    "node": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "jsx": "jsx",
    "tsx": "tsx",
    "cpp": "cpp",
    "c++": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "hpp": "cpp",
    "h++": "cpp",
    "c": "c",
    "h": "c",
    "rust": "rust",
    "rs": "rust",
    "go": "go",
    "golang": "go",
    "csharp": "csharp",
    "cs": "csharp",
    "c#": "csharp",
    "java": "java",
    "kotlin": "kotlin",
    "kt": "kotlin",
    "kts": "kotlin",
    "swift": "swift",
    "php": "php",
    "php5": "php",
    "php7": "php",
    "php8": "php",
    "ruby": "ruby",
    "rb": "ruby",
    "bash": "bash",
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "sql": "sql",
    "mysql": "sql",
    "postgres": "sql",
    "postgresql": "sql",
    "sqlite": "sql",
    "tsql": "sql",
    "plsql": "sql",
    "html": "html",
    "htm": "html",
    "xml": "html",
    "css": "css",
    "scss": "css",
    "sass": "css",
    "less": "css",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "markdown": "markdown",
    "md": "markdown",
}


def normalize_code_language(lang: Optional[str]) -> str:
    """Normalize common programming language aliases into canonical language identifiers."""
    if not lang:
        return "text"
    cleaned = str(lang).strip().lower()
    return LANGUAGE_ALIASES.get(cleaned, cleaned)


# Prose prefixes indicating conversational text rather than code
PROSE_PREFIXES: List[str] = [
    "here is",
    "the following",
    "in this example",
    "below is",
    "to implement",
    "you can use",
    "this snippet",
    "we can write",
    "as shown",
    "let us look",
    "consider the",
]

# Patterns for abrupt, unfinished line endings
DANGLING_OPERATORS = [
    "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
    "+", "-", "*", "/", "%", "==", "!=", "<=", ">=", "&&", "||",
    "<<", ">>", "->", "=>", "|", "&", "^",
]


def _is_rust_lifetime(code: str, pos: int) -> bool:
    """Check if single quote at pos in Rust code represents a lifetime rather than a char literal."""
    if pos + 1 >= len(code):
        return False
    if not (code[pos + 1].isalpha() or code[pos + 1] == "_"):
        return False
    # Check if preceded by char literal start (e.g. '= ', '<', '&', ' ', '(', ',')
    prev_char = code[pos - 1] if pos > 0 else " "
    if prev_char in ("&", "<", " ", "(", ",", ":", "[", "\n", "\t"):
        # Match lifetime identifier
        m = re.match(r"'[a-zA-Z_][a-zA-Z0-9_]*", code[pos:])
        if m:
            end_idx = pos + len(m.group(0))
            if end_idx >= len(code) or code[end_idx] in (",", ">", " ", ":", ")", "]", "\n", "\t", ";", "{"):
                return True
    return False


def validate_code_completeness(code: Optional[str], language: str = "text") -> Tuple[bool, List[str]]:
    """Validate that code represents a complete logical example without truncation, unbalanced delimiters, or syntax cutoff.
    
    Returns:
        (is_complete: bool, issues: List[str])
    """
    if not code or not str(code).strip():
        return False, ["Code is empty or whitespace only."]

    clean = str(code).strip().replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\n")
    lang = normalize_code_language(language)
    issues: List[str] = []

    # 1. Reject Markdown Fences accidentally left inside code
    if "```" in clean:
        issues.append("Code contains leaked markdown code fences ('```').")

    # 2. Reject Conversational Prose
    clean_lower = clean.lower()
    for prefix in PROSE_PREFIXES:
        if clean_lower.startswith(prefix) and not any(k in clean for k in ["def ", "class ", "import ", "const ", "fn ", "{", "public ", "struct "]):
            issues.append(f"Code block begins with conversational prose: '{clean[:40]}...'.")
            return False, issues

    lines = [l.rstrip() for l in clean.split("\n")]
    non_empty_lines = [l.strip() for l in lines if l.strip()]
    if not non_empty_lines:
        return False, ["Code contains no non-empty lines."]

    last_line = non_empty_lines[-1]

    # Strip inline comment from last line for ending checks
    last_line_no_comment = last_line
    if lang in ("python", "bash", "ruby"):
        if "#" in last_line:
            last_line_no_comment = last_line.split("#", 1)[0].strip()
    elif lang == "sql":
        if "--" in last_line:
            last_line_no_comment = last_line.split("--", 1)[0].strip()
    else:
        if "//" in last_line:
            last_line_no_comment = last_line.split("//", 1)[0].strip()

    # 3. Delimiter Balance & Scope Tracking
    delimiter_stack: List[Tuple[str, int, int]] = []  # (char, line_no, col_no)
    in_single_quote = False
    in_double_quote = False
    in_backtick = False
    in_triple_single = False
    in_triple_double = False
    in_block_comment = False
    in_line_comment = False

    i = 0
    n = len(clean)
    line_no = 1
    col_no = 1

    while i < n:
        ch = clean[i]
        
        if ch == "\n":
            line_no += 1
            col_no = 1
            in_line_comment = False
            i += 1
            continue

        # Handle comments
        if not in_single_quote and not in_double_quote and not in_backtick and not in_triple_single and not in_triple_double:
            if not in_block_comment and not in_line_comment:
                # Check block comment start
                if clean[i:i+2] == "/*":
                    in_block_comment = True
                    i += 2
                    col_no += 2
                    continue
                if clean[i:i+4] == "<!--":
                    in_block_comment = True
                    i += 4
                    col_no += 4
                    continue
                # Check line comment start
                if lang in ("python", "bash", "ruby") and ch == "#":
                    in_line_comment = True
                    i += 1
                    col_no += 1
                    continue
                if lang == "sql" and clean[i:i+2] == "--":
                    in_line_comment = True
                    i += 2
                    col_no += 2
                    continue
                if clean[i:i+2] == "//":
                    in_line_comment = True
                    i += 2
                    col_no += 2
                    continue

            elif in_block_comment:
                if clean[i:i+2] == "*/":
                    in_block_comment = False
                    i += 2
                    col_no += 2
                    continue
                if clean[i:i+3] == "-->":
                    in_block_comment = False
                    i += 3
                    col_no += 3
                    continue
                i += 1
                col_no += 1
                continue

            elif in_line_comment:
                i += 1
                col_no += 1
                continue

        # Handle strings
        if not in_block_comment and not in_line_comment:
            # Triple quotes (Python/Kotlin)
            if lang in ("python", "kotlin") and clean[i:i+3] == '"""':
                if not in_single_quote and not in_backtick and not in_triple_single:
                    in_triple_double = not in_triple_double
                    i += 3
                    col_no += 3
                    continue
            if lang == "python" and clean[i:i+3] == "'''":
                if not in_double_quote and not in_backtick and not in_triple_double:
                    in_triple_single = not in_triple_single
                    i += 3
                    col_no += 3
                    continue

            # Rust lifetime check
            if lang == "rust" and ch == "'" and not in_double_quote and not in_backtick:
                if _is_rust_lifetime(clean, i):
                    # Skip lifetime token
                    m = re.match(r"'[a-zA-Z_][a-zA-Z0-9_]*", clean[i:])
                    advance = len(m.group(0)) if m else 1
                    i += advance
                    col_no += advance
                    continue

            # Backticks (JS/TS/Go/Markdown/SQL)
            if ch == "`" and not in_single_quote and not in_double_quote and not in_triple_single and not in_triple_double:
                # Check escape
                if i > 0 and clean[i-1] == "\\":
                    pass
                else:
                    in_backtick = not in_backtick

            # Double quotes
            elif ch == '"' and not in_single_quote and not in_backtick and not in_triple_single and not in_triple_double:
                if i > 0 and clean[i-1] == "\\" and not (i > 1 and clean[i-2] == "\\"):
                    pass
                else:
                    in_double_quote = not in_double_quote

            # Single quotes
            elif ch == "'" and not in_double_quote and not in_backtick and not in_triple_single and not in_triple_double:
                if i > 0 and clean[i-1] == "\\" and not (i > 1 and clean[i-2] == "\\"):
                    pass
                else:
                    in_single_quote = not in_single_quote

            # Delimiters outside strings and comments
            if not in_single_quote and not in_double_quote and not in_backtick and not in_triple_single and not in_triple_double:
                if ch in ("(", "[", "{"):
                    delimiter_stack.append((ch, line_no, col_no))
                elif ch in (")", "]", "}"):
                    matching = {"(": ")", "[": "]", "{": "}"}
                    if not delimiter_stack:
                        issues.append(f"Unexpected closing delimiter '{ch}' at line {line_no}:{col_no} without matching opening delimiter.")
                    else:
                        top_ch, top_l, top_c = delimiter_stack.pop()
                        if matching.get(top_ch) != ch:
                            issues.append(
                                f"Mismatched closing delimiter '{ch}' at line {line_no}:{col_no} (expected '{matching.get(top_ch)}' to match '{top_ch}' at line {top_l}:{top_c})."
                            )

        i += 1
        col_no += 1

    # Check unclosed comment or string states
    if in_block_comment:
        issues.append("Unclosed multiline comment block (missing closing '*/' or '-->').")
    if in_triple_double or in_triple_single:
        issues.append("Unclosed triple-quoted multiline string literal.")
    elif in_double_quote:
        issues.append("Unclosed double-quoted string literal ('\"').")
    elif in_single_quote:
        issues.append("Unclosed single-quoted string literal ('\'').")
    elif in_backtick:
        issues.append("Unclosed template literal or raw string backtick ('`').")

    # Check unclosed delimiters in stack
    if delimiter_stack:
        for d, dl, dc in delimiter_stack:
            issues.append(f"Unclosed opening delimiter '{d}' at line {dl}:{dc}.")

    # 4. Abrupt Line Endings & Incomplete Statements
    if last_line_no_comment:
        # Check dangling trailing operators
        for op in DANGLING_OPERATORS:
            if last_line_no_comment.endswith(op):
                # Allow C++ stream manipulators like std::endl or references in function headers
                if op == "&" and lang in ("cpp", "c", "rust"):
                    continue
                if op == "*" and lang in ("cpp", "c", "rust", "go"):
                    continue
                issues.append(f"Code ends abruptly with trailing operator '{op}' at end of snippet: '{last_line_no_comment[-30:]}'.")
                break

        # Check dangling dot or call opening
        if last_line_no_comment.endswith(".") and not last_line_no_comment.endswith("..."):
            issues.append(f"Code ends abruptly with trailing member access dot: '{last_line_no_comment[-30:]}'.")
        if last_line_no_comment.endswith(",") and lang not in ("python", "json", "yaml", "html"):
            # Dangling comma at end of code snippet is invalid in C/C++/Java/JS/TS/Rust unless multi-item literal
            if not any(last_line_no_comment.startswith(k) for k in ("int ", "let ", "const ", "var ")):
                issues.append(f"Code ends abruptly with trailing comma: '{last_line_no_comment[-30:]}'.")

        # Check unclosed function call / method invocation ending
        incomplete_call_patterns = [
            r"\b[a-zA-Z_]\w*\s*\($",
            r"\bfile\.read\s*\([^)]*$",
            r"\bconsole\.log\s*\([^)]*$",
            r"\bprint\s*\([^)]*$",
            r"\bstd::cout\s*<<$",
            r"\breturn\s*\($",
            r"\bif\s*\($",
            r"\bwhile\s*\($",
            r"\bfor\s*\($",
            r"\.then\s*\($",
            r"=>\s*\{$",
        ]
        for pat in incomplete_call_patterns:
            if re.search(pat, last_line_no_comment):
                issues.append(f"Code ends abruptly with unclosed statement or scope: '{last_line_no_comment[-40:]}'.")
                break

    # 5. Language-Specific Syntactic Checks
    if lang == "python":
        # Parse with Python AST
        lines_no_repl = []
        for line in clean.split("\n"):
            if line.startswith(">>> ") or line.startswith("... "):
                lines_no_repl.append(line[4:])
            else:
                lines_no_repl.append(line)
        code_to_parse = "\n".join(lines_no_repl)
        try:
            ast.parse(code_to_parse)
        except SyntaxError as e:
            issues.append(f"Python syntax error at line {e.lineno}: {e.msg}")
        except Exception as e:
            issues.append(f"Python AST validation error: {e}")

    elif lang in ("cpp", "c", "java", "csharp"):
        # For C/C++/Java/C#, ensure top-level statements generally end with ';' or '}'
        if last_line_no_comment and not last_line_no_comment.startswith("#"):
            last_char = last_line_no_comment[-1]
            if last_char not in (";", "}", ">", "\"", "'", "`", "/"):
                if not any(last_line_no_comment.endswith(k) for k in ("*/", "-->")):
                    # Check if it looks like an unfinished statement
                    if any(w in last_line_no_comment for w in ("read(", "write(", "cout", "printf", "return", "new ", "throw ")):
                        issues.append(f"C/C++/Java statement does not end with semicolon ';' or closing brace '}}': '{last_line_no_comment[-35:]}'")

    elif lang == "bash":
        # Check matching control blocks
        if_count = len(re.findall(r"\bif\b", clean))
        fi_count = len(re.findall(r"\bfi\b", clean))
        if if_count != fi_count:
            issues.append(f"Shell script has unmatched if ({if_count}) and fi ({fi_count}) statements.")

        case_count = len(re.findall(r"\bcase\b", clean))
        esac_count = len(re.findall(r"\besac\b", clean))
        if case_count != esac_count:
            issues.append(f"Shell script has unmatched case ({case_count}) and esac ({esac_count}) statements.")

        do_count = len(re.findall(r"\bdo\b", clean))
        done_count = len(re.findall(r"\bdone\b", clean))
        if do_count != done_count:
            issues.append(f"Shell script has unmatched do ({do_count}) and done ({done_count}) statements.")

    elif lang == "sql":
        sql_dangling = ["SELECT", "FROM", "WHERE", "JOIN", "ON", "GROUP BY", "ORDER BY", "HAVING", "SET", "INSERT INTO", "VALUES", "AND", "OR"]
        for kw in sql_dangling:
            if last_line_no_comment.upper().endswith(kw):
                issues.append(f"SQL query ends abruptly with trailing keyword '{kw}'.")
                break

    is_complete = len(issues) == 0
    return is_complete, issues


async def repair_incomplete_code(
    llm_client: Any,
    code: str,
    language: str,
    topic: Optional[str] = None,
    max_attempts: int = 2,
) -> Optional[str]:
    """Send incomplete code to LLM for a strict, syntax-completing repair pass without altering purpose."""
    lang = normalize_code_language(language)
    current_code = code

    for attempt in range(1, max_attempts + 1):
        is_valid, issues = validate_code_completeness(current_code, lang)
        if is_valid:
            return current_code

        issue_summary = "; ".join(issues[:3])
        logger.warning(
            f"[code-validation] incomplete code detected language={lang} attempt={attempt}/{max_attempts}: {issue_summary}"
        )

        repair_system_prompt = (
            f"You are a principal software architect and compiler engineer specializing in {lang}.\n"
            f"You will be given an incomplete or truncated {lang} code snippet that fails syntax validation.\n\n"
            f"YOUR TASK:\n"
            f"Complete ONLY this code example so it is 100% syntactically valid, self-contained, and complete.\n\n"
            f"CRITICAL REQUIREMENTS:\n"
            f"1. Preserve the original purpose, logic, and topic ({topic or 'technical implementation'}).\n"
            f"2. Preserve existing code wherever possible.\n"
            f"3. Finish all incomplete statements, calls, expressions, and loops.\n"
            f"4. Close all open scopes, braces '{{}}', brackets '[]', parentheses '()', quotes, and template literals.\n"
            f"5. Return ONE complete, concise, self-contained example.\n"
            f"6. Do NOT add markdown backtick fences (no ```).\n"
            f"7. Do NOT include explanations, preamble, or commentary.\n"
            f"8. Return strictly the raw {lang} code."
        )

        repair_user_prompt = (
            f"Language: {lang}\n"
            f"Validation issues found: {issue_summary}\n\n"
            f"TRUNCATED CODE TO COMPLETE:\n"
            f"{current_code}\n\n"
            f"Return the complete, syntactically valid {lang} code only:"
        )

        try:
            from pydantic import BaseModel, Field

            class CodeRepairResult(BaseModel):
                completed_code: str = Field(description="Complete, syntactically valid source code example")

            res: CodeRepairResult = await llm_client.invoke_structured(
                schema=CodeRepairResult,
                system_prompt=repair_system_prompt,
                user_prompt=repair_user_prompt,
                stage=f"repair_code_{lang}_att{attempt}",
                temperature=0.1,
            )

            if res and res.completed_code and res.completed_code.strip():
                candidate = res.completed_code.strip()
                # Strip any markdown fences if model hallucinated them
                if candidate.startswith("```"):
                    candidate = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", candidate)
                    candidate = re.sub(r"\n?```$", "", candidate).strip()

                cand_valid, cand_issues = validate_code_completeness(candidate, lang)
                if cand_valid:
                    logger.info(f"[code-repair] attempt={attempt} success=true language={lang}")
                    return candidate
                else:
                    logger.warning(
                        f"[code-repair] attempt={attempt} candidate still had issues: {'; '.join(cand_issues[:2])}"
                    )
                    current_code = candidate
        except Exception as e:
            logger.warning(f"[code-repair] attempt={attempt} failed with error: {e}")

    # If all repair attempts fail, re-check final candidate
    final_valid, _ = validate_code_completeness(current_code, lang)
    if final_valid:
        return current_code

    logger.error(f"[code-repair] exhausted {max_attempts} repair attempts for {lang} code. Rejecting truncated snippet.")
    return None


def terminal_has_meaningful_content(block: Any) -> bool:
    """Check if a TerminalBlock contains at least one meaningful, non-whitespace command or line."""
    if not block:
        return False

    lines = getattr(block, "lines", None)
    if lines is not None:
        meaningful_count = 0
        for line in lines:
            if hasattr(line, "text"):
                txt = getattr(line, "text", "")
            elif isinstance(line, dict):
                txt = line.get("text", "")
            else:
                txt = str(line)

            clean_txt = txt.strip()
            # Ignore whitespace or standalone prompt characters
            if clean_txt and clean_txt not in ("$", ">", "#", ">>>", "PS>", "PS >"):
                meaningful_count += 1
        return meaningful_count > 0

    for attr in ("command", "content", "terminal_command"):
        val = getattr(block, attr, None)
        if val and str(val).strip() and str(val).strip() not in ("$", ">", "#", ">>>", "PS>", "PS >"):
            return True

    return False


async def repair_incomplete_terminal(
    llm_client: Any,
    title: Optional[str],
    topic: Optional[str],
    shell: str = "bash",
    context: Optional[str] = None,
    max_attempts: int = 2,
) -> Optional[List[Any]]:
    """Send empty or missing terminal block to LLM for targeted repair to generate executable CLI commands."""
    from vasukisquare.book.components import TerminalLine
    from vasukisquare.agents.content_validator import validate_terminal_command
    from pydantic import BaseModel, Field

    class TerminalRepairResult(BaseModel):
        commands: List[str] = Field(
            default_factory=list,
            description="List of 1-3 realistic, executable shell commands for this title and topic without markdown fences or explanations",
        )

    clean_title = title or topic or "Terminal Execution"
    clean_topic = topic or clean_title

    repair_system_prompt = (
        f"You are a principal systems engineer generating executable {shell} terminal commands.\n"
        f"Generate ONLY the realistic command-line commands for the terminal window titled '{clean_title}'.\n\n"
        f"CRITICAL REQUIREMENTS:\n"
        f"1. Commands must be directly relevant to: '{clean_topic}'.\n"
        f"2. Return 1 to 3 realistic, executable {shell} commands.\n"
        f"3. Do NOT include markdown backtick fences (no ```).\n"
        f"4. Do NOT include commentary, prose, explanations, or conversational text.\n"
        f"5. Return strictly the executable command strings."
    )

    repair_user_prompt = (
        f"Terminal Title: {clean_title}\n"
        f"Section Topic: {clean_topic}\n"
        f"Shell: {shell}\n"
        f"{f'Context: {context}' if context else ''}\n\n"
        f"Return the executable command(s) for this terminal block:"
    )

    for attempt in range(1, max_attempts + 1):
        try:
            res: TerminalRepairResult = await llm_client.invoke_structured(
                schema=TerminalRepairResult,
                system_prompt=repair_system_prompt,
                user_prompt=repair_user_prompt,
                stage=f"repair_terminal_att{attempt}",
                temperature=0.1,
            )

            if res and res.commands:
                valid_cmds = []
                for cmd in res.commands:
                    clean_cmd = str(cmd).strip()
                    if clean_cmd.startswith("```"):
                        clean_cmd = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", clean_cmd)
                        clean_cmd = re.sub(r"\n?```$", "", clean_cmd).strip()
                    clean_cmd = re.sub(r"^[\$#>]\s*", "", clean_cmd).strip()
                    if clean_cmd and validate_terminal_command(clean_cmd):
                        valid_cmds.append(clean_cmd)

                if valid_cmds:
                    logger.info(f"[terminal-repair] attempt={attempt} success=true title='{clean_title}' cmds={valid_cmds}")
                    return [TerminalLine(kind="command", text=c) for c in valid_cmds]
        except Exception as e:
            logger.warning(f"[terminal-repair] attempt={attempt} failed with error: {e}")

    logger.warning(f"[terminal-repair] exhausted {max_attempts} attempts for title='{clean_title}'. Omitting TerminalBlock.")
    return None
