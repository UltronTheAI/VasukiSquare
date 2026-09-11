"""Base interfaces and typing for pipeline agents."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypeVar
from pydantic import BaseModel

StateType = TypeVar("StateType", bound=BaseModel)
ResultType = TypeVar("ResultType")


class BaseAgent(ABC, Generic[StateType, ResultType]):
    """Abstract base agent for pipeline stages."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def run(self, state: StateType) -> ResultType:
        """Execute the agent step."""
        pass


class PipelineState(BaseModel):
    """Common state container passed across generation stages."""

    topic: str
    user_prompt: str
    metadata: Dict[str, Any] = {}

