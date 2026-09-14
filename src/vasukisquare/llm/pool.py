"""Groq Model Pool abstraction managing multi-model failover, cooldowns, and strategies."""

import asyncio
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("vasukisquare.llm.pool")


def parse_model_list(raw_input: Optional[str], default: str = "openai/gpt-oss-120b") -> List[str]:
    """Parse comma-separated model string into unique, ordered list of trimmed model names."""
    if not raw_input or not raw_input.strip():
        return [default]

    models: List[str] = []
    seen: set[str] = set()
    for item in raw_input.split(","):
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            models.append(cleaned)

    return models if models else [default]


def parse_retry_after(error: Exception) -> Optional[float]:
    """Extract retry-after delay in seconds from response headers or error messages."""
    # Check response headers if available (httpx / Groq exception structure)
    response = getattr(error, "response", None)
    if response is not None:
        headers = getattr(response, "headers", {})
        if "retry-after" in headers:
            try:
                return float(headers["retry-after"])
            except (ValueError, TypeError):
                pass

    err_str = str(error)

    # Regex patterns for retry-after in error descriptions
    patterns = [
        r"try again in\s+([\d\.]+)\s*s",
        r"try again in\s+([\d\.]+)\s*seconds",
        r"retry after\s+([\d\.]+)\s*s",
        r"retry_after[:=]\s*([\d\.]+)",
        r"in\s+([\d\.]+)\s*s",
    ]
    for pattern in patterns:
        match = re.search(pattern, err_str, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1))
                if val > 0:
                    return val
            except (ValueError, IndexError):
                pass

    return None


class GroqErrorClassification(Tuple[bool, bool, Optional[float], bool, bool, bool, bool]):
    """Classified error info for Groq LLM invocations."""

    is_retryable: bool
    is_rate_limit: bool
    retry_after: Optional[float]
    is_model_unavailable: bool
    is_structured_error: bool
    is_impossible_limit: bool
    is_auth_error: bool

    def __new__(
        cls,
        is_retryable: bool,
        is_rate_limit: bool,
        retry_after: Optional[float],
        is_model_unavailable: bool,
        is_structured_error: bool = False,
        is_impossible_limit: bool = False,
        is_auth_error: bool = False,
    ):
        return super().__new__(
            cls,
            (is_retryable, is_rate_limit, retry_after, is_model_unavailable, is_structured_error, is_impossible_limit, is_auth_error),
        )

    @property
    def is_retryable(self) -> bool:
        return self[0]

    @property
    def is_rate_limit(self) -> bool:
        return self[1]

    @property
    def retry_after(self) -> Optional[float]:
        return self[2]

    @property
    def is_model_unavailable(self) -> bool:
        return self[3]

    @property
    def is_structured_error(self) -> bool:
        return self[4]

    @property
    def is_impossible_limit(self) -> bool:
        return self[5]

    @property
    def is_auth_error(self) -> bool:
        return self[6]


def is_retryable_groq_error(error: Exception) -> GroqErrorClassification:
    """Classify an exception to determine if it should trigger a key/model failover, wait, or retry.
    
    Returns:
        GroqErrorClassification named 7-tuple
    """
    err_str = str(error).lower()
    retry_after = parse_retry_after(error)

    # 1. Impossible model limits (prompt exceeds model max context / OTPM limit -> skip model immediately without waiting)
    impossible_limit_indicators = [
        "request too large",
        "otpm limit",
        "maximum context length",
        "context_length_exceeded",
        "exceeds maximum token",
        "tokens per minute (tpm): limit",
    ]
    if any(ind in err_str for ind in impossible_limit_indicators):
        return GroqErrorClassification(
            is_retryable=True,
            is_rate_limit=False,
            retry_after=None,
            is_model_unavailable=False,
            is_structured_error=False,
            is_impossible_limit=True,
            is_auth_error=False,
        )

    # 2. Authentication / access errors (invalid credentials -> rotatable across keys if other keys exist)
    auth_errors = [
        "invalid_api_key",
        "invalid api key",
        "unauthorized",
        "401",
        "forbidden",
        "403",
        "authentication failed",
    ]
    if any(ind in err_str for ind in auth_errors):
        return GroqErrorClassification(
            is_retryable=False,
            is_rate_limit=False,
            retry_after=None,
            is_model_unavailable=False,
            is_structured_error=False,
            is_impossible_limit=False,
            is_auth_error=True,
        )

    # 3. Tool calling / schema validation failures (model capability failure -> retryable on same model / across models without cooldown)
    tool_failures = [
        "tool_use_failed",
        "failed to call a function",
        "attempted to call tool",
        "tool call validation failed",
        "failed to parse tool call arguments",
        "tool_error",
        "failed_generation",
        "validation error",
        "validationerror",
        "value error",
        "valueerror",
        "jsondecodeerror",
        "output parsing error",
        "did not return a valid json",
    ]
    if any(ind in err_str for ind in tool_failures):
        return GroqErrorClassification(
            is_retryable=True,
            is_rate_limit=False,
            retry_after=None,
            is_model_unavailable=False,
            is_structured_error=True,
            is_impossible_limit=False,
            is_auth_error=False,
        )

    # 4. Model unavailable / decommissioned / not found error (retryable across models)
    model_unavailable_indicators = [
        "model_not_found",
        "model not found",
        "model_decommissioned",
        "model is decommissioned",
        "decommissioned",
        "decommission",
        "model_unavailable",
        "model is unavailable",
        "unavailable",
        "does not exist or you do not have access",
        "unknown model",
        "unsupported model",
    ]
    if any(ind in err_str for ind in model_unavailable_indicators):
        return GroqErrorClassification(
            is_retryable=True,
            is_rate_limit=False,
            retry_after=None,
            is_model_unavailable=True,
            is_structured_error=False,
            is_impossible_limit=False,
            is_auth_error=False,
        )

    # 5. Rate Limit / Quota errors
    rate_limit_indicators = [
        "429",
        "rate_limit_exceeded",
        "rate limit",
        "tokens per minute",
        "requests per minute",
        "requests per day",
        "tpm",
        "rpm",
        "rpd",
        "quota exceeded",
        "resource has been exhausted",
        "too many requests",
    ]
    if any(ind in err_str for ind in rate_limit_indicators):
        return GroqErrorClassification(
            is_retryable=True,
            is_rate_limit=True,
            retry_after=retry_after,
            is_model_unavailable=False,
            is_structured_error=False,
            is_impossible_limit=False,
            is_auth_error=False,
        )

    # 6. Server overload / transient network errors / bad request from model generation
    server_error_indicators = [
        "500",
        "502",
        "503",
        "504",
        "400",
        "server overloaded",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "internal server error",
        "connection reset",
        "connection error",
        "timeout",
        "timed out",
        "overloaded",
    ]
    if any(ind in err_str for ind in server_error_indicators):
        return GroqErrorClassification(
            is_retryable=True,
            is_rate_limit=False,
            retry_after=retry_after,
            is_model_unavailable=False,
            is_structured_error=False,
            is_impossible_limit=False,
            is_auth_error=False,
        )

    # Check for known network or validation exception types
    type_name = type(error).__name__.lower()
    if any(t in type_name for t in ["timeout", "connectionerror", "ratelimit", "internalserver", "validationerror", "valueerror", "badrequesterror"]):
        return GroqErrorClassification(
            is_retryable=True,
            is_rate_limit="ratelimit" in type_name,
            retry_after=retry_after,
            is_model_unavailable=False,
            is_structured_error="validationerror" in type_name or "valueerror" in type_name,
            is_impossible_limit=False,
            is_auth_error=False,
        )

    return GroqErrorClassification(
        is_retryable=True,
        is_rate_limit=False,
        retry_after=None,
        is_model_unavailable=False,
        is_structured_error=False,
        is_impossible_limit=False,
        is_auth_error=False,
    )


class GroqKeyState:
    """State tracking for a single Groq API Key."""

    def __init__(self, index: int, api_key: str):
        self.index: int = index  # 1-indexed (e.g., 1 for Key #1)
        self.api_key: str = api_key
        self.cooldown_until: float = 0.0
        self.is_invalid: bool = False  # Set to True on 401 Unauthorized
        self.requests: int = 0
        self.successes: int = 0
        self.rate_limits: int = 0
        self.failures: int = 0
        self.consecutive_rate_limits: int = 0
        self.last_used_at: float = 0.0
        self.last_success_at: float = 0.0

    @property
    def label(self) -> str:
        """Safe human-readable label for logging without leaking the secret."""
        return f"Groq Key #{self.index}"

    def is_in_cooldown(self) -> bool:
        """Check whether this key is currently in temporary cooldown."""
        return time.time() < self.cooldown_until

    def get_cooldown_remaining(self) -> float:
        """Return remaining cooldown seconds for this key."""
        return max(0.0, self.cooldown_until - time.time())

    def is_available(self) -> bool:
        """Check if this key is valid and not in cooldown."""
        return not self.is_invalid and not self.is_in_cooldown()

    def __repr__(self) -> str:
        status = "invalid" if self.is_invalid else ("cooldown" if self.is_in_cooldown() else "available")
        return f"<GroqKeyState {self.label} status={status}>"


class GroqKeyPool:
    """Centralized Groq API Key pool managing rotation, cooldowns, invalidation, and safety."""

    def __init__(
        self,
        api_keys: List[str],
        strategy: str = "preferred",
        cooldown_seconds: float = 60.0,
    ):
        clean_keys: List[str] = []
        seen: set[str] = set()
        for k in api_keys:
            c = k.strip()
            if c and c not in seen:
                seen.add(c)
                clean_keys.append(c)

        self.strategy: str = (strategy or "preferred").strip().lower()
        if self.strategy not in ("preferred", "round_robin", "rotate"):
            self.strategy = "preferred"

        self.cooldown_seconds: float = float(cooldown_seconds)
        self.current_index: int = 0
        self._lock = asyncio.Lock()

        self.keys: List[GroqKeyState] = [
            GroqKeyState(index=i + 1, api_key=k)
            for i, k in enumerate(clean_keys)
        ]

        logger.info(
            f"[GroqKeyPool] Configured {len(self.keys)} API keys (strategy={self.strategy})"
        )

    def has_keys(self) -> bool:
        """Check if the pool has any configured keys."""
        return len(self.keys) > 0

    def active_key_count(self) -> int:
        """Return count of keys that are not permanently invalid."""
        return sum(1 for k in self.keys if not k.is_invalid)

    def get_candidate_keys(self) -> List[GroqKeyState]:
        """Return an ordered list of candidate keys to attempt for a request failover cycle."""
        valid_keys = [k for k in self.keys if not k.is_invalid]
        if not valid_keys:
            return []

        if self.strategy in ("round_robin", "rotate"):
            num_keys = len(valid_keys)
            base_candidates: List[GroqKeyState] = []
            for i in range(num_keys):
                idx = (self.current_index + i) % num_keys
                base_candidates.append(valid_keys[idx])
        else:
            # "preferred" strategy: always try Key #1 first, then Key #2, Key #3
            base_candidates = list(valid_keys)

        # Prioritize available keys (not in cooldown); then keys in cooldown sorted by remaining time
        available = [k for k in base_candidates if not k.is_in_cooldown()]
        in_cooldown = [k for k in base_candidates if k.is_in_cooldown()]
        in_cooldown.sort(key=lambda k: k.get_cooldown_remaining())

        return available + in_cooldown

    def advance_for_new_request(self) -> Optional[GroqKeyState]:
        """Prepare key selection at the start of a new logical request (for round_robin)."""
        valid_keys = [k for k in self.keys if not k.is_invalid]
        if not valid_keys:
            return None
        if self.strategy in ("round_robin", "rotate") and len(valid_keys) > 1:
            self.current_index = (self.current_index + 1) % len(valid_keys)
        return valid_keys[self.current_index % len(valid_keys)]

    def mark_rate_limited(self, key_state: GroqKeyState, retry_after: Optional[float] = None) -> None:
        """Mark a key in temporary cooldown following HTTP 429 rate limit."""
        key_state.last_used_at = time.time()
        key_state.requests += 1
        key_state.rate_limits += 1
        key_state.failures += 1
        key_state.consecutive_rate_limits += 1

        cd = retry_after if retry_after is not None and retry_after > 0 else self.cooldown_seconds
        key_state.cooldown_until = time.time() + cd
        logger.warning(
            f"[GroqKeyPool] {key_state.label} rate limited. Marked in cooldown for {cd:.1f}s."
        )

    def mark_invalid(self, key_state: GroqKeyState) -> None:
        """Permanently mark a key as invalid (e.g. 401 Unauthorized)."""
        key_state.last_used_at = time.time()
        key_state.requests += 1
        key_state.failures += 1
        key_state.is_invalid = True
        logger.error(
            f"[GroqKeyPool] {key_state.label} marked permanently invalid (401 Unauthorized / Invalid API Key)."
        )

    def mark_success(self, key_state: GroqKeyState) -> None:
        """Record a successful invocation using this key."""
        key_state.last_used_at = time.time()
        key_state.last_success_at = time.time()
        key_state.requests += 1
        key_state.successes += 1
        key_state.consecutive_rate_limits = 0
        key_state.cooldown_until = 0.0

    def get_earliest_cooldown_wait(self) -> Tuple[Optional[GroqKeyState], float]:
        """Find the key among valid keys with the earliest availability and return (key, wait_seconds)."""
        valid_keys = [k for k in self.keys if not k.is_invalid]
        if not valid_keys:
            return None, 0.0
        earliest_key = min(valid_keys, key=lambda k: k.cooldown_until)
        wait = max(0.0, earliest_key.cooldown_until - time.time())
        return earliest_key, wait

    def get_summary(self) -> str:
        """Format an execution summary of API key usage without leaking key values."""
        lines = [
            "Groq API Key Usage:",
        ]
        for k in self.keys:
            status = "INVALID (401)" if k.is_invalid else ("cooldown" if k.is_in_cooldown() else "healthy")
            lines.append(
                f"  {k.label}: {k.requests} requests, {k.successes} successes, "
                f"{k.rate_limits} rate limits ({status})"
            )
        return "\n".join(lines)


class GroqModelPool:
    """Centralized Groq model pool managing failover, selection strategies, cooldowns, and telemetry."""

    def __init__(
        self,
        models: List[str],
        strategy: str = "ordered",
        cooldown_seconds: float = 60.0,
        max_attempts: int = 0,
        retries_per_model: int = 1,
    ):
        if not models:
            models = ["openai/gpt-oss-120b"]

        # Normalize and deduplicate models list
        clean_models: List[str] = []
        seen: set[str] = set()
        for m in models:
            c = m.strip()
            if c and c not in seen:
                seen.add(c)
                clean_models.append(c)

        self.models: List[str] = clean_models if clean_models else ["openai/gpt-oss-120b"]
        self.strategy: str = (strategy or "ordered").strip().lower()
        if self.strategy not in ("ordered", "random", "rotate"):
            self.strategy = "ordered"

        # Apply random strategy shuffle once at initialization
        if self.strategy == "random":
            shuffled = self.models.copy()
            random.shuffle(shuffled)
            self.models = shuffled

        self.cooldown_seconds: float = float(cooldown_seconds)
        self.max_attempts: int = max_attempts if max_attempts > 0 else len(self.models)
        self.retries_per_model: int = max(1, retries_per_model)

        self.current_index: int = 0
        self.available_at: Dict[str, float] = {m: 0.0 for m in self.models}
        self.cooldown_until: Dict[str, float] = self.available_at  # Alias for backwards compatibility
        self.model_stats: Dict[str, Dict[str, int]] = {
            m: {"requests": 0, "successes": 0, "rate_limits": 0, "failures": 0}
            for m in self.models
        }
        self.model_switches: int = 0
        self._lock = asyncio.Lock()

        logger.info(
            f"[GroqPool] Configured {len(self.models)} models (strategy={self.strategy}): "
            f"{', '.join(self.models)}"
        )

    @property
    def current_model(self) -> str:
        """Return the currently selected model name."""
        return self.models[self.current_index % len(self.models)]

    def is_in_cooldown(self, model: str) -> bool:
        """Check whether a model is currently in temporary cooldown."""
        until = self.available_at.get(model, 0.0)
        return time.time() < until

    def get_cooldown_remaining(self, model: str) -> float:
        """Return remaining cooldown seconds for a model."""
        until = self.available_at.get(model, 0.0)
        return max(0.0, until - time.time())

    def get_earliest_available_wait(self, candidate_models: Optional[List[str]] = None) -> Tuple[Optional[str], float]:
        """Find the model among candidates with the earliest availability and return (model, wait_seconds)."""
        candidates = candidate_models if candidate_models is not None else self.models
        if not candidates:
            return None, 0.0
        earliest_model = min(candidates, key=lambda m: self.available_at.get(m, 0.0))
        wait = max(0.0, self.available_at.get(earliest_model, 0.0) - time.time())
        return earliest_model, wait

    def get_candidate_models(self) -> List[str]:
        """Return an ordered list of candidate models to attempt for a single request failover cycle."""
        num_models = len(self.models)
        base_candidates: List[str] = []

        # Start from current index and wrap around
        for i in range(num_models):
            idx = (self.current_index + i) % num_models
            m = self.models[idx]
            if m not in base_candidates:
                base_candidates.append(m)

        # Prioritize models not in cooldown; then models in cooldown sorted by remaining time
        available = [m for m in base_candidates if not self.is_in_cooldown(m)]
        in_cooldown = [m for m in base_candidates if self.is_in_cooldown(m)]
        in_cooldown.sort(key=lambda m: self.get_cooldown_remaining(m))

        ordered = available + in_cooldown
        # Respect max_attempts limit
        return ordered[:self.max_attempts]

    def advance_for_new_request(self) -> str:
        """Prepare model selection at the start of a new logical request."""
        if self.strategy == "rotate" and len(self.models) > 1:
            self.current_index = (self.current_index + 1) % len(self.models)
        return self.current_model

    def switch_to_model(self, model: str, reason: str = "") -> None:
        """Switch active model pointer to the specified model."""
        if model in self.models:
            old_model = self.current_model
            if old_model != model:
                self.current_index = self.models.index(model)
                self.model_switches += 1
                reason_str = f" ({reason})" if reason else ""
                logger.info(f"[GroqPool] Switching model: {old_model} -> {model}{reason_str}")

    def record_success(self, model: str) -> None:
        """Record successful invocation on model and reset cooldown."""
        if model not in self.model_stats:
            self.model_stats[model] = {"requests": 0, "successes": 0, "rate_limits": 0, "failures": 0}
        self.model_stats[model]["requests"] += 1
        self.model_stats[model]["successes"] += 1
        self.available_at[model] = 0.0

    def record_failure(
        self,
        model: str,
        error: Exception,
        is_rate_limit: bool = False,
        retry_after: Optional[float] = None,
        is_structured_error: bool = False,
    ) -> None:
        """Record model failure and set cooldown (only if not a structured parsing error)."""
        if model not in self.model_stats:
            self.model_stats[model] = {"requests": 0, "successes": 0, "rate_limits": 0, "failures": 0}
        self.model_stats[model]["requests"] += 1
        self.model_stats[model]["failures"] += 1
        if is_rate_limit:
            self.model_stats[model]["rate_limits"] += 1

        if is_structured_error:
            # Do NOT mark model in cooldown for structured JSON output formatting errors
            logger.warning(
                f"[GroqPool] Model '{model}' encountered structured output parsing error (cooldown skipped)."
            )
            return

        cd_time = retry_after if retry_after is not None and retry_after > 0 else self.cooldown_seconds
        self.available_at[model] = time.time() + cd_time
        logger.warning(
            f"[GroqPool] Model '{model}' marked in cooldown for {cd_time:.1f}s "
            f"(reason: {'rate_limit' if is_rate_limit else 'error'})"
        )

    def get_summary(self) -> str:
        """Format an execution summary of all models used in the pool."""
        lines = [
            "==========================================",
            "LLM Generation Summary",
            "Provider: Groq",
            "",
            "Models used:",
        ]
        for m in self.models:
            st = self.model_stats.get(m, {"requests": 0, "successes": 0, "rate_limits": 0, "failures": 0})
            lines.append(f"{m}")
            lines.append(f"  Requests: {st['requests']}")
            lines.append(f"  Successes: {st['successes']}")
            if st["rate_limits"] > 0:
                lines.append(f"  Rate limits: {st['rate_limits']}")
            if st["failures"] > 0 and st["failures"] != st["rate_limits"]:
                lines.append(f"  Other failures: {st['failures'] - st['rate_limits']}")
            lines.append("")

        lines.append(f"Model switches: {self.model_switches}")
        lines.append("==========================================")
        return "\n".join(lines)
