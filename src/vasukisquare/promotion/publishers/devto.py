"""DEV Community / Forem API publisher implementation."""

import asyncio
import logging
from typing import Any, Dict, Optional
import httpx

from vasukisquare.config import Settings, get_settings
from vasukisquare.promotion.models import PromotionPlatform, PromotionPost
from vasukisquare.promotion.publishers.base import PromotionPublisher, PublishResult

logger = logging.getLogger("vasukisquare.promotion.devto")


class DevToPublisher(PromotionPublisher):
    """Publisher adapter for DEV Community (dev.to) and Forem instances."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        publish_live: bool = True,
        settings: Optional[Settings] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.settings = settings or get_settings()
        self.api_key = api_key or self.settings.devto_api_key or ""
        self.base_url = (base_url or self.settings.devto_api_base_url or "https://dev.to/api").rstrip("/")
        self.publish_live = publish_live if publish_live is not None else self.settings.devto_publish
        self.timeout = timeout
        self.max_retries = max_retries

    def platform_name(self) -> str:
        return PromotionPlatform.DEVTO.value

    def _sanitize_tags(self, tags: list[str]) -> list[str]:
        """Normalize tags for DEV API: max 4, lowercase, alphanumeric or hyphens, no hashes."""
        clean_tags: list[str] = []
        for t in tags:
            tag = str(t).strip().lower().lstrip("#")
            # Keep alphanumeric and hyphens/underscores
            tag = "".join(c for c in tag if c.isalnum() or c in ("-", "_"))
            if tag and tag not in clean_tags:
                clean_tags.append(tag)
            if len(clean_tags) >= 4:
                break
        return clean_tags

    async def publish(self, post: PromotionPost) -> PublishResult:
        """Publish an article to DEV Community via POST /api/articles."""
        if not self.api_key or not self.api_key.strip():
            logger.error("[DEVTO] Publication failed: DEVTO_API_KEY is not configured.")
            return PublishResult(
                success=False,
                error_message="DEVTO_API_KEY is missing or empty. Please set DEVTO_API_KEY in environment or .env.",
            )

        endpoint = f"{self.base_url}/articles"
        headers = {
            "api-key": self.api_key.strip(),
            "Content-Type": "application/json",
            "User-Agent": "VasukiSquare-Promotion/1.0",
        }

        payload: Dict[str, Any] = {
            "article": {
                "title": post.title,
                "body_markdown": post.body_markdown,
                "published": self.publish_live,
                "tags": self._sanitize_tags(post.tags),
                "canonical_url": post.canonical_url,
            }
        }

        logger.info(
            f"[DEVTO:START] Publishing article for book_slug='{post.book_slug}' to {endpoint} "
            f"(published={self.publish_live}, tags={payload['article']['tags']})"
        )

        last_error_msg = ""
        last_response_data: Optional[Dict[str, Any]] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)

                status = response.status_code
                try:
                    data = response.json()
                    last_response_data = data if isinstance(data, dict) else {"raw": data}
                except Exception:
                    data = {}
                    last_response_data = {"text": response.text}

                if status in (200, 201):
                    ext_id = str(data.get("id") or "")
                    ext_url = str(data.get("url") or f"https://dev.to/{data.get('path', '')}")
                    logger.info(
                        f"[DEVTO:SUCCESS] Published article successfully! id='{ext_id}' url='{ext_url}' "
                        f"attempt={attempt}/{self.max_retries}"
                    )
                    return PublishResult(
                        success=True,
                        external_post_id=ext_id,
                        external_url=ext_url,
                        raw_response=last_response_data,
                    )

                # Client errors (401, 422, etc.) that shouldn't be retried
                if status == 401:
                    last_error_msg = "DEV API 401 Unauthorized: Invalid or expired DEVTO_API_KEY."
                    logger.error(f"[DEVTO:AUTH_ERROR] {last_error_msg}")
                    break
                elif status == 422:
                    error_detail = data.get("error") or data.get("errors") or response.text
                    last_error_msg = f"DEV API 422 Unprocessable Entity: {error_detail}"
                    logger.error(f"[DEVTO:VALIDATION_ERROR] {last_error_msg}")
                    break
                elif status == 429:
                    retry_after = 5.0
                    try:
                        retry_after = float(response.headers.get("retry-after", "5.0"))
                    except ValueError:
                        pass
                    last_error_msg = f"DEV API 429 Rate Limit exceeded. Retry-After: {retry_after}s"
                    logger.warning(
                        f"[DEVTO:RATE_LIMIT] attempt={attempt}/{self.max_retries}: {last_error_msg}"
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(retry_after)
                        continue
                else:
                    last_error_msg = f"DEV API HTTP {status}: {response.text[:200]}"
                    logger.warning(
                        f"[DEVTO:HTTP_ERROR] attempt={attempt}/{self.max_retries}: {last_error_msg}"
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(2.0 ** attempt)
                        continue

            except httpx.TimeoutException as e:
                last_error_msg = f"Request timeout connecting to DEV API ({endpoint}): {e}"
                logger.warning(f"[DEVTO:TIMEOUT] attempt={attempt}/{self.max_retries}: {last_error_msg}")
                if attempt < self.max_retries:
                    await asyncio.sleep(2.0 ** attempt)
            except Exception as e:
                last_error_msg = f"Unexpected error connecting to DEV API: {e}"
                logger.warning(f"[DEVTO:ERROR] attempt={attempt}/{self.max_retries}: {last_error_msg}")
                if attempt < self.max_retries:
                    await asyncio.sleep(2.0 ** attempt)

        logger.error(f"[DEVTO:FAILED] All {self.max_retries} attempts failed. Last error: {last_error_msg}")
        return PublishResult(
            success=False,
            error_message=last_error_msg,
            raw_response=last_response_data,
        )

