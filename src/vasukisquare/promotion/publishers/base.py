"""Abstract base classes and result types for promotion platform publishers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from vasukisquare.promotion.models import PromotionPost


class PublishResult(BaseModel):
    """Result of attempting to publish a promotion post to an external platform."""

    success: bool
    external_post_id: Optional[str] = None
    external_url: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class PromotionPublisher(ABC):
    """Abstract interface for external article publishing adapters."""

    @abstractmethod
    def platform_name(self) -> str:
        """Return the unique identifier string for this platform."""
        pass

    @abstractmethod
    async def publish(self, post: PromotionPost) -> PublishResult:
        """Publish the given post to the target platform.
        
        Args:
            post: The generated PromotionPost ready for publishing.
            
        Returns:
            PublishResult indicating success/failure and external identifiers.
        """
        pass

