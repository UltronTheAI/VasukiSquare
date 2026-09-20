"""Base interface and resiliency utilities for external research tools."""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, List, TypeVar
from pydantic import BaseModel

if TYPE_CHECKING:
    from vasukisquare.research.models import SourceDocument

InputSchema = TypeVar("InputSchema", bound=BaseModel)
OutputSchema = TypeVar("OutputSchema")


class BaseTool(ABC, Generic[InputSchema, OutputSchema]):
    """Abstract interface for external tools ensuring consistent execution and error handling."""

    def __init__(self, name: str, description: str, timeout_seconds: float = 15.0):
        self.name = name
        self.description = description
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def _run(self, params: InputSchema) -> OutputSchema:
        """Internal execution method implemented by subclasses."""
        pass

    async def execute(self, params: InputSchema) -> OutputSchema:
        """Execute the tool with timeout and exception containment."""
        try:
            return await asyncio.wait_for(self._run(params), timeout=self.timeout_seconds)
        except asyncio.TimeoutError as e:
            raise TimeoutError(f"Tool '{self.name}' timed out after {self.timeout_seconds}s") from e


class SearchProvider(ABC):
    """Abstract search provider interface allowing pluggable search backends."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SourceDocument]:
        """Perform search and return uniform SourceDocuments."""
        pass
