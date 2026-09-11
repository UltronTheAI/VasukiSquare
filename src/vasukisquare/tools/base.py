"""Base interface for external research and data extraction tools."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypeVar
from pydantic import BaseModel

InputSchema = TypeVar("InputSchema", bound=BaseModel)
OutputSchema = TypeVar("OutputSchema")


class BaseTool(ABC, Generic[InputSchema, OutputSchema]):
    """Abstract interface for external tools ensuring consistent execution and error handling."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, params: InputSchema) -> OutputSchema:
        """Execute the tool with validated structured input."""
        pass

