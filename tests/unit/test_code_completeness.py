"""Unit tests for language-aware code completeness validation, splitting, and repair."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel

from vasukisquare.agents.code_validator import (
    normalize_code_language,
    validate_code_completeness,
    repair_incomplete_code,
)
from vasukisquare.book.components import CodeBlock
from vasukisquare.renderer.overflow import split_code_block, find_safe_page_split
from vasukisquare.book.models import Page, PageContent, PageStyle


class TestLanguageNormalization:
    """Tests for canonical programming language alias normalization."""

    def test_common_language_aliases(self):
        assert normalize_code_language("c++") == "cpp"
        assert normalize_code_language("C++") == "cpp"
        assert normalize_code_language("rs") == "rust"
        assert normalize_code_language("Rust") == "rust"
        assert normalize_code_language("js") == "javascript"
        assert normalize_code_language("ts") == "typescript"
        assert normalize_code_language("py") == "python"
        assert normalize_code_language("python3") == "python"
        assert normalize_code_language("golang") == "go"
        assert normalize_code_language("c#") == "csharp"
        assert normalize_code_language("cs") == "csharp"
        assert normalize_code_language("sh") == "bash"
        assert normalize_code_language("shell") == "bash"
        assert normalize_code_language("zsh") == "bash"
        assert normalize_code_language("postgresql") == "sql"
        assert normalize_code_language("md") == "markdown"
        assert normalize_code_language(None) == "text"
        assert normalize_code_language("") == "text"
        assert normalize_code_language("unknown_lang") == "unknown_lang"


class TestCodeCompletenessValidation:
    """Tests for validating complete vs incomplete/truncated code across languages."""

    # 1. Complete Code Examples
    def test_complete_python(self):
        code = (
            "def calculate_metrics(values: list[float]) -> dict[str, float]:\n"
            "    total = sum(values)\n"
            "    count = len(values)\n"
            "    return {'mean': total / count if count else 0.0}\n"
        )
        is_complete, issues = validate_code_completeness(code, "python")
        assert is_complete is True
        assert issues == []

    def test_complete_cpp(self):
        code = (
            "#include <iostream>\n"
            "#include <fstream>\n\n"
            "struct BTreeNode {\n"
            "    int keys[3];\n"
            "    bool is_leaf;\n"
            "};\n\n"
            "void read_node(std::ifstream& file, BTreeNode& node) {\n"
            "    file.read(reinterpret_cast<char*>(&node), sizeof(node));\n"
            "}\n"
        )
        is_complete, issues = validate_code_completeness(code, "cpp")
        assert is_complete is True
        assert issues == []

    def test_complete_rust(self):
        code = (
            "pub struct Node {\n"
            "    pub key: u64,\n"
            "    pub value: Vec<u8>,\n"
            "}\n\n"
            "impl Node {\n"
            "    pub fn new(key: u64, value: Vec<u8>) -> Self {\n"
            "        Self { key, value }\n"
            "    }\n"
            "}\n"
        )
        is_complete, issues = validate_code_completeness(code, "rust")
        assert is_complete is True
        assert issues == []

    def test_complete_javascript_typescript(self):
        code = (
            "export async function fetchRecord(id: string): Promise<Record | null> {\n"
            "    const response = await fetch(`/api/records/${id}`);\n"
            "    if (!response.ok) {\n"
            "        return null;\n"
            "    }\n"
            "    return await response.json();\n"
            "}\n"
        )
        is_complete, issues = validate_code_completeness(code, "typescript")
        assert is_complete is True
        assert issues == []

    def test_complete_go(self):
        code = (
            "package storage\n\n"
            "import \"fmt\"\n\n"
            "func ReadBlock(offset int64) ([]byte, error) {\n"
            "    buf := make([]byte, 4096)\n"
            "    fmt.Println(\"Reading block at\", offset)\n"
            "    return buf, nil\n"
            "}\n"
        )
        is_complete, issues = validate_code_completeness(code, "go")
        assert is_complete is True
        assert issues == []

    def test_complete_java(self):
        code = (
            "public class IndexManager {\n"
            "    private final int blockSize;\n\n"
            "    public IndexManager(int blockSize) {\n"
            "        this.blockSize = blockSize;\n"
            "    }\n"
            "}\n"
        )
        is_complete, issues = validate_code_completeness(code, "java")
        assert is_complete is True
        assert issues == []

    def test_complete_bash(self):
        code = (
            "if [ -f \"config.json\" ]; then\n"
            "    echo \"Loading configuration...\"\n"
            "    python3 main.py --config config.json\n"
            "else\n"
            "    echo \"Configuration not found.\"\n"
            "fi\n"
        )
        is_complete, issues = validate_code_completeness(code, "bash")
        assert is_complete is True
        assert issues == []

    def test_complete_sql(self):
        code = (
            "SELECT user_id, email, created_at\n"
            "FROM accounts\n"
            "WHERE is_active = true\n"
            "ORDER BY created_at DESC;\n"
        )
        is_complete, issues = validate_code_completeness(code, "sql")
        assert is_complete is True
        assert issues == []

    # 2. Incomplete / Truncated Code Examples
    def test_incomplete_cpp_mid_call(self):
        # Exact reproduction of screenshot bug:
        # file.read(reinterpret_cast<char*>(&node), sizeof(node)
        code = (
            "struct BTreeNode {\n"
            "    int keys[3];\n"
            "};\n\n"
            "void read_node(std::ifstream& file, BTreeNode& node) {\n"
            "    file.read(reinterpret_cast<char*>(&node), sizeof(node)"
        )
        is_complete, issues = validate_code_completeness(code, "cpp")
        assert is_complete is False
        assert any("Unclosed opening delimiter" in i or "does not end with semicolon" in i for i in issues)

    def test_incomplete_unclosed_braces_rust(self):
        code = (
            "pub fn process_event(event: Event) {\n"
            "    match event {\n"
            "        Event::Start => println!(\"Starting\"),\n"
            "        Event::Stop => println!(\"Stopping\"),\n"
        )
        is_complete, issues = validate_code_completeness(code, "rust")
        assert is_complete is False
        assert any("Unclosed opening delimiter '{'" in i for i in issues)

    def test_incomplete_dangling_operator(self):
        code = (
            "const totalScore =\n"
            "    baseScore + bonusScore +\n"
        )
        is_complete, issues = validate_code_completeness(code, "javascript")
        assert is_complete is False
        assert any("trailing operator '+'" in i for i in issues)

    def test_incomplete_python_syntax_error(self):
        code = (
            "def calculate(items):\n"
            "    return sum([item.val for item in"
        )
        is_complete, issues = validate_code_completeness(code, "python")
        assert is_complete is False
        assert any("Python syntax error" in i or "Unclosed opening delimiter" in i for i in issues)

    def test_incomplete_bash_unclosed_if(self):
        code = (
            "if [ \"$STATUS\" == \"ready\" ]; then\n"
            "    echo \"System is operational\"\n"
        )
        is_complete, issues = validate_code_completeness(code, "bash")
        assert is_complete is False
        assert any("unmatched if" in i for i in issues)

    def test_incomplete_sql_trailing_keyword(self):
        code = "SELECT id, name FROM users WHERE"
        is_complete, issues = validate_code_completeness(code, "sql")
        assert is_complete is False
        assert any("trailing keyword 'WHERE'" in i for i in issues)

    def test_leaked_markdown_fences_rejected(self):
        code = "```python\ndef run():\n    pass\n```"
        is_complete, issues = validate_code_completeness(code, "python")
        assert is_complete is False
        assert any("markdown code fences" in i for i in issues)

    def test_conversational_prose_rejected(self):
        code = "Here is the implementation of the binary search algorithm in Python:"
        is_complete, issues = validate_code_completeness(code, "python")
        assert is_complete is False
        assert any("conversational prose" in i for i in issues)

    # 3. Rust Lifetime Handling
    def test_rust_lifetimes_not_false_positives(self):
        code = (
            "pub struct RefHolder<'a> {\n"
            "    pub data: &'a str,\n"
            "}\n\n"
            "pub fn get_str<'a>(holder: &'a RefHolder<'a>) -> &'a str {\n"
            "    holder.data\n"
            "}\n"
        )
        is_complete, issues = validate_code_completeness(code, "rust")
        assert is_complete is True
        assert issues == []


class TestCodeBlockSplitting:
    """Tests for safe code splitting across page boundaries."""

    def test_split_code_block_exact_reconstruction(self):
        original_lines = [
            "// Line 1: Header",
            "function processBatch(items) {",
            "    const results = [];",
            "    for (const item of items) {",
            "        if (item.isValid) {",
            "            results.push(transform(item));",
            "        }",
            "    }",
            "    return results;",
            "}",
            "export default processBatch;",
        ]
        original_code = "\n".join(original_lines)
        block = CodeBlock(
            code=original_code,
            language="javascript",
            filename="batch_processor.js",
            caption="Listing 2.1: Batch Processor Implementation",
            line_numbers=True,
        )

        b1, b2 = split_code_block(block, available_height_mm=45.0)

        # Invariant 1: No lines lost or duplicated
        reconstructed_code = f"{b1.code}\n{b2.code}"
        assert reconstructed_code == original_code
        assert b1.code.split("\n") + b2.code.split("\n") == original_lines

        # Invariant 2: Metadata preservation
        assert b1.language == "javascript"
        assert b2.language == "javascript"
        assert b1.filename == "batch_processor.js"
        assert b2.filename == "batch_processor.js"
        assert b1.caption == "Listing 2.1: Batch Processor Implementation"
        assert "(Cont.)" in b2.caption

    def test_find_safe_page_split_with_code_block(self):
        code_lines = [f"int var_{i} = {i * 10};" for i in range(40)]
        code_block = CodeBlock(
            code="\n".join(code_lines),
            language="cpp",
            filename="data_structures.cpp",
            caption="Large Data Listing",
            line_numbers=True,
        )
        page = Page(
            book_id="test_book",
            page_number=3,
            chapter_number=1,
            chapter_name="Storage Internals",
            content=PageContent(
                headline="Large Code Listing",
                blocks=[code_block],
            ),
            style=PageStyle(),
        )

        fit_content, overflow_content = find_safe_page_split(page)
        assert len(fit_content.blocks) == 1
        assert len(overflow_content.blocks) == 1

        fit_b = fit_content.blocks[0]
        over_b = overflow_content.blocks[0]

        assert isinstance(fit_b, CodeBlock)
        assert isinstance(over_b, CodeBlock)
        assert fit_b.code.split("\n") + over_b.code.split("\n") == code_lines


class TestCodeRepair:
    """Tests for LLM code repair integration."""

    @pytest.mark.asyncio
    async def test_repair_incomplete_code_success(self):
        truncated_code = (
            "void write_data(std::ofstream& out, const Record& r) {\n"
            "    out.write(reinterpret_cast<const char*>(&r), sizeof(r)"
        )
        repaired_code = (
            "void write_data(std::ofstream& out, const Record& r) {\n"
            "    out.write(reinterpret_cast<const char*>(&r), sizeof(r));\n"
            "}\n"
        )

        class MockLLMResult(BaseModel):
            completed_code: str

        mock_llm = MagicMock()
        mock_llm.invoke_structured = AsyncMock(
            return_value=MockLLMResult(completed_code=repaired_code)
        )

        result = await repair_incomplete_code(
            llm_client=mock_llm,
            code=truncated_code,
            language="cpp",
            topic="Binary File Writing",
            max_attempts=1,
        )

        assert result is not None
        assert result.strip() == repaired_code.strip()
        is_valid, issues = validate_code_completeness(result, "cpp")
        assert is_valid is True
