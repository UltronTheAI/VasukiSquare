"""Unit tests for terminal block completeness validation, rendering guards, and repair."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel

from vasukisquare.book.components import TerminalBlock, TerminalLine
from vasukisquare.design.theme import Theme
from vasukisquare.renderer.components import ComponentRenderer
from vasukisquare.agents.code_validator import (
    terminal_has_meaningful_content,
    repair_incomplete_terminal,
)


class TestTerminalMeaningfulContent:
    """Tests for terminal_has_meaningful_content predicate."""

    def test_valid_bash_command_lines(self):
        block = TerminalBlock(
            title="Verify Storage Engine",
            shell="bash",
            lines=[
                TerminalLine(kind="command", text="python3 -m unittest discover"),
                TerminalLine(kind="output", text="OK (Ran 15 tests)"),
            ],
        )
        assert terminal_has_meaningful_content(block) is True

    def test_valid_powershell_command_lines(self):
        block = TerminalBlock(
            title="Check Services",
            shell="powershell",
            lines=[
                TerminalLine(kind="command", text="Get-Process | Where-Object CPU -gt 10"),
            ],
        )
        assert terminal_has_meaningful_content(block) is True

    def test_empty_lines_array(self):
        block = TerminalBlock(
            title="Empty Terminal",
            shell="bash",
            lines=[],
        )
        assert terminal_has_meaningful_content(block) is False

    def test_whitespace_only_command_lines(self):
        block = TerminalBlock(
            title="Whitespace Terminal",
            shell="bash",
            lines=[
                TerminalLine(kind="command", text="   \n\t  "),
                TerminalLine(kind="output", text="   "),
            ],
        )
        assert terminal_has_meaningful_content(block) is False

    def test_prompt_only_lines(self):
        block = TerminalBlock(
            title="Prompt Only",
            shell="bash",
            lines=[
                TerminalLine(kind="command", text="$"),
                TerminalLine(kind="command", text=">"),
            ],
        )
        assert terminal_has_meaningful_content(block) is False

    def test_none_or_empty_block(self):
        assert terminal_has_meaningful_content(None) is False


class TestTerminalRendererSafetyGuard:
    """Tests for ComponentRenderer.render_terminal safety guards."""

    def test_valid_bash_renders_html(self):
        block = TerminalBlock(
            title="Verify Sector Size",
            shell="bash",
            lines=[
                TerminalLine(kind="command", text="fdisk -l /dev/sda"),
            ],
        )
        html = ComponentRenderer.render_terminal(block, Theme.LIGHT)
        assert html != ""
        assert "component-terminal-window" in html
        assert "Verify Sector Size" in html
        assert "fdisk -l /dev/sda" in html
        assert "BASH" in html

    def test_valid_powershell_renders_html(self):
        block = TerminalBlock(
            title="PowerShell Diagnostics",
            shell="powershell",
            lines=[
                TerminalLine(kind="command", text="Test-NetConnection -ComputerName localhost -Port 8080"),
            ],
        )
        html = ComponentRenderer.render_terminal(block, Theme.LIGHT)
        assert html != ""
        assert "component-terminal-window" in html
        assert "PowerShell Diagnostics" in html
        assert "Test-NetConnection" in html
        assert "POWERSHELL" in html
        assert "PS&gt;" in html or "PS>" in html

    def test_whitespace_only_does_not_render_empty_shell(self):
        block = TerminalBlock(
            title="Verify device sector size and test O_DIRECT",
            shell="bash",
            lines=[
                TerminalLine(kind="command", text="   "),
            ],
        )
        html = ComponentRenderer.render_terminal(block, Theme.LIGHT)
        assert html == ""
        assert "component-terminal-window" not in html
        assert "terminal-header" not in html

    def test_empty_lines_does_not_render_empty_shell(self):
        block = TerminalBlock(
            title="Verify device sector size and test O_DIRECT",
            shell="bash",
            lines=[],
        )
        html = ComponentRenderer.render_terminal(block, Theme.LIGHT)
        assert html == ""
        assert "component-terminal-window" not in html
        assert "terminal-header" not in html


class TestTerminalRepair:
    """Tests for LLM repair of incomplete/empty terminal blocks."""

    @pytest.mark.asyncio
    async def test_repaired_command_renders_normally(self):
        mock_llm = MagicMock()

        class MockTerminalRepair(BaseModel):
            commands: list[str]

        mock_llm.invoke_structured = AsyncMock(
            return_value=MockTerminalRepair(
                commands=["blockdev --getss /dev/sdb", "dd if=/dev/sdb of=/dev/null bs=4k count=1 iflag=direct"]
            )
        )

        repaired_lines = await repair_incomplete_terminal(
            llm_client=mock_llm,
            title="Verify device sector size and test O_DIRECT",
            topic="Linux I/O direct sector verification",
            shell="bash",
            max_attempts=1,
        )

        assert repaired_lines is not None
        assert len(repaired_lines) == 2
        assert repaired_lines[0].text == "blockdev --getss /dev/sdb"

        # Construct and render repaired block
        block = TerminalBlock(
            title="Verify device sector size and test O_DIRECT",
            shell="bash",
            lines=repaired_lines,
        )
        html = ComponentRenderer.render_terminal(block, Theme.LIGHT)
        assert html != ""
        assert "Verify device sector size and test O_DIRECT" in html
        assert "blockdev --getss /dev/sdb" in html

    @pytest.mark.asyncio
    async def test_failed_repair_component_omitted(self):
        mock_llm = MagicMock()

        class MockTerminalRepair(BaseModel):
            commands: list[str]

        # LLM returns empty commands
        mock_llm.invoke_structured = AsyncMock(
            return_value=MockTerminalRepair(commands=[])
        )

        repaired_lines = await repair_incomplete_terminal(
            llm_client=mock_llm,
            title="Verify device sector size and test O_DIRECT",
            topic="Linux I/O direct sector verification",
            shell="bash",
            max_attempts=1,
        )

        assert repaired_lines is None

        # Verify component omission when repair fails
        blocks = []
        if repaired_lines:
            blocks.append(
                TerminalBlock(
                    title="Verify device sector size and test O_DIRECT",
                    shell="bash",
                    lines=repaired_lines,
                )
            )

        assert len(blocks) == 0

