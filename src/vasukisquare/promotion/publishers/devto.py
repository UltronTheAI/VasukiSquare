"""DEV Community / Forem API publisher implementation."""

import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx

from vasukisquare.config import Settings, get_settings
from vasukisquare.promotion.models import PromotionPlatform, PromotionPost
from vasukisquare.promotion.publishers.base import PromotionPublisher, PublishResult

logger = logging.getLogger("vasukisquare.promotion.devto")

MAX_DEVTO_TAG_LENGTH = 30
MAX_DEVTO_TAGS_COUNT = 4


def sanitize_devto_tag(tag: Any, max_length: int = MAX_DEVTO_TAG_LENGTH) -> Optional[str]:
    """Sanitize a single tag according to strict DEV.to requirements.
    
    Rules:
    - Convert to lowercase
    - Trim leading/trailing whitespace
    - Remove leading '#'
    - Strip all non-ASCII lowercase alphanumeric characters (removes spaces, hyphens, underscores, punctuation, unicode)
    - Enforce maximum tag length (default: 30 chars)
    - Discard if empty
    
    Examples:
    - 'urban-gardening' -> 'urbangardening'
    - 'design-patterns' -> 'designpatterns'
    - 'Web Development' -> 'webdevelopment'
    - '#Python' -> 'python'
    - 'system_design' -> 'systemdesign'
    """
    if not tag:
        return None

    t_str = str(tag).strip().lower().lstrip("#")
    # Keep strictly lowercase ASCII letters (a-z) and digits (0-9)
    cleaned = "".join(c for c in t_str if ("a" <= c <= "z") or ("0" <= c <= "9"))

    if not cleaned:
        return None

    return cleaned[:max_length]


def sanitize_devto_tags(
    tags: Optional[List[Any]],
    max_tags: int = MAX_DEVTO_TAGS_COUNT,
    max_length: int = MAX_DEVTO_TAG_LENGTH,
    fallback_category: Optional[str] = None,
) -> List[str]:
    """Sanitize and validate a list of tags for DEV.to API submission.
    
    Ensures:
    - Each tag contains strictly [a-z0-9] with max_length
    - Empty or invalid tags are discarded
    - Duplicates removed while preserving order
    - List length capped at max_tags (default 4)
    - Fallback guaranteed if all tags become empty
    """
    clean_tags: List[str] = []
    seen: set[str] = set()

    if tags:
        for t in tags:
            clean = sanitize_devto_tag(t, max_length=max_length)
            if clean and clean not in seen:
                seen.add(clean)
                clean_tags.append(clean)
            if len(clean_tags) >= max_tags:
                break

    if not clean_tags:
        # Generate safe fallback tag from fallback_category or default
        fallback = sanitize_devto_tag(fallback_category, max_length=max_length) if fallback_category else None
        if fallback and fallback not in seen:
            clean_tags.append(fallback)
        else:
            clean_tags = ["programming", "tech"]

    return clean_tags[:max_tags]


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
        self.api_key = api_key if api_key is not None else (self.settings.devto_api_key or "")
        self.base_url = (base_url if base_url is not None else (self.settings.devto_api_base_url or "https://dev.to/api")).rstrip("/")
        self.publish_live = publish_live if publish_live is not None else self.settings.devto_publish
        self.timeout = timeout
        self.max_retries = max_retries

    def platform_name(self) -> str:
        return PromotionPlatform.DEVTO.value

    def _sanitize_tags(self, tags: list[str]) -> list[str]:
        """Normalize tags for DEV API using centralized sanitizer."""
        return sanitize_devto_tags(tags)

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

        # Centralized sanitization ensures invalid tags never reach DEV API
        final_tags = sanitize_devto_tags(post.tags, fallback_category=post.book_slug)

        payload: Dict[str, Any] = {
            "article": {
                "title": post.title,
                "body_markdown": post.body_markdown,
                "published": self.publish_live,
                "tags": final_tags,
                "canonical_url": post.canonical_url,
            }
        }

        logger.info(
            f"[DEVTO:START] Publishing article for book_slug='{post.book_slug}' to {endpoint} "
            f"(published={self.publish_live}, tags={final_tags})"
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

                # Client errors (401, 422, 400, etc.) that shouldn't be retried
                if status == 401:
                    last_error_msg = f"DEV API 401 Unauthorized: Invalid or expired DEVTO_API_KEY. (Submitted tags: {final_tags})"
                    logger.error(f"[DEVTO:AUTH_ERROR] status=401 response={response.text} tags={final_tags}")
                    break
                elif status == 422:
                    error_detail = data.get("error") or data.get("errors") or response.text
                    last_error_msg = f"DEV API 422 Unprocessable Entity: {error_detail} (Submitted tags: {final_tags})"
                    logger.error(
                        f"[DEVTO:VALIDATION_ERROR] status=422 error={error_detail} tags={final_tags} response={response.text}"
                    )
                    break
                elif status == 400:
                    error_detail = data.get("error") or data.get("errors") or response.text
                    last_error_msg = f"DEV API 400 Bad Request: {error_detail} (Submitted tags: {final_tags})"
                    logger.error(
                        f"[DEVTO:BAD_REQUEST] status=400 error={error_detail} tags={final_tags} response={response.text}"
                    )
                    break
                elif status == 429:
                    retry_after = 5.0
                    try:
                        retry_after = float(response.headers.get("retry-after", "5.0"))
                    except ValueError:
                        pass
                    last_error_msg = f"DEV API 429 Rate Limit exceeded. Retry-After: {retry_after}s"
                    logger.warning(
                        f"[DEVTO:RATE_LIMIT] attempt={attempt}/{self.max_retries}: {last_error_msg} tags={final_tags}"
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(retry_after)
                        continue
                else:
                    last_error_msg = f"DEV API HTTP {status}: {response.text[:200]} (Submitted tags: {final_tags})"
                    logger.warning(
                        f"[DEVTO:HTTP_ERROR] attempt={attempt}/{self.max_retries} status={status}: {last_error_msg}"
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

