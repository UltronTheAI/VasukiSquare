"""Centralized LangChain LLM client supporting Groq and Ollama backends with structured output."""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from langchain_core.messages import HumanMessage, SystemMessage

from vasukisquare.config import Settings, get_settings, EnvironmentConfigurationError
from vasukisquare.llm.metrics import BookGenerationMetrics

logger = logging.getLogger("vasukisquare.llm")

T = TypeVar("T", bound=BaseModel)


class LLMGenerationError(Exception):
    """Raised when an LLM generation call fails in production mode."""
    pass


class GroqGenerationError(LLMGenerationError):
    """Backwards-compatible alias for Groq generation failures."""
    pass


class LLMClient:
    """Wrapper around LangChain ChatGroq and ChatOllama with structured logging, retries, and telemetry."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        metrics: Optional[BookGenerationMetrics] = None,
    ):
        self.settings = settings or get_settings()
        self.metrics = metrics or BookGenerationMetrics()
        
        # Resolve active provider, model, and reasoning
        self.active_provider, self.active_model, self.provider_reason = self.settings.resolve_llm_provider()
        self.metrics.llm_provider = self.active_provider
        self.metrics.llm_model = self.active_model

    def log_startup_banner(self) -> None:
        """Print clear startup diagnostic banner for active LLM provider without exposing secrets."""
        lines = [
            "==========================================",
            f"LLM Provider: {self.active_provider.upper()}",
            f"Model: {self.active_model}",
        ]
        if self.active_provider == "ollama":
            lines.append(f"Endpoint: {self.settings.ollama_base_url}")
        lines.append(f"Reason: {self.provider_reason}")
        lines.append("==========================================")
        banner_text = "\n".join(lines)
        print(banner_text)
        logger.info("\n" + banner_text)

    def get_chat_model(self, temperature: Optional[float] = None, provider: Optional[str] = None) -> Any:
        """Instantiate and return the appropriate LangChain chat model."""
        target_provider = provider or self.active_provider
        temp = temperature if temperature is not None else self.settings.llm_temperature

        if target_provider == "groq":
            if not self.settings.groq_api_key or not self.settings.groq_api_key.strip():
                raise GroqGenerationError(
                    "Cannot initialize Groq LLM: GROQ_API_KEY is missing or empty. "
                    "Set GROQ_API_KEY in .env/.env.local or set LLM_PROVIDER=auto / LLM_PROVIDER=ollama."
                )
            from langchain_groq import ChatGroq
            return ChatGroq(
                api_key=self.settings.groq_api_key,
                model_name=self.settings.groq_model,
                temperature=temp,
                max_retries=2,
                timeout=60.0,
            )

        if target_provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=self.settings.ollama_model,
                base_url=self.settings.ollama_base_url,
                temperature=temp,
                num_ctx=self.settings.ollama_num_ctx,
            )

        raise LLMGenerationError(f"Unsupported provider: {target_provider}")

    def _extract_tokens_from_response(self, result: Any) -> tuple[int, int]:
        """Safely extract prompt and completion token counts from response metadata if available."""
        prompt_tokens = 0
        completion_tokens = 0
        
        raw_meta = getattr(result, "response_metadata", None) or getattr(result, "usage_metadata", None)
        if isinstance(raw_meta, dict):
            # Groq format / standard LangChain
            usage = raw_meta.get("token_usage") or raw_meta.get("usage") or raw_meta
            if isinstance(usage, dict):
                prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
                completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
            # Ollama native metadata format
            if not prompt_tokens and "prompt_eval_count" in raw_meta:
                prompt_tokens = raw_meta.get("prompt_eval_count", 0)
            if not completion_tokens and "eval_count" in raw_meta:
                completion_tokens = raw_meta.get("eval_count", 0)

        return prompt_tokens, completion_tokens

    async def invoke_structured(
        self,
        schema: Type[T],
        system_prompt: str,
        user_prompt: str,
        stage: str,
        temperature: Optional[float] = None,
        max_retries: int = 3,
    ) -> T:
        """Execute a structured LLM request returning an instance of Pydantic schema T."""
        effective_provider = self.active_provider
        model_name = self.active_model
        last_exception: Optional[Exception] = None

        # Ensure schema name is clear in system prompt to prevent tool name hallucination
        effective_system_prompt = system_prompt
        if schema.__name__ not in effective_system_prompt:
            effective_system_prompt += f"\n\nReturn your structured response using the {schema.__name__} schema."

        # Use direct message objects to avoid template parsing errors with arbitrary braces
        messages = [
            SystemMessage(content=effective_system_prompt),
            HumanMessage(content=user_prompt),
        ]

        for attempt in range(1, max_retries + 1):
            start_time = time.time()
            try:
                llm = self.get_chat_model(temperature=temperature, provider=effective_provider)
                structured_llm = llm.with_structured_output(schema)

                logger.debug(
                    f"[LLM:START] provider={effective_provider} model={model_name} "
                    f"stage={stage} attempt={attempt}/{max_retries}"
                )
                result = await structured_llm.ainvoke(messages)
                duration = time.time() - start_time

                if not isinstance(result, schema):
                    # Attempt manual Pydantic parsing if raw dict was returned
                    if isinstance(result, dict):
                        result = schema.model_validate(result)
                    else:
                        raise ValueError(f"LLM returned unexpected type {type(result)}, expected {schema.__name__}")

                prompt_tokens, completion_tokens = self._extract_tokens_from_response(result)
                total_tokens = prompt_tokens + completion_tokens
                tps_str = f"{completion_tokens / duration:.1f} tok/s" if completion_tokens > 0 and duration > 0 else "N/A"

                # Record metrics and log observability
                self.metrics.record_llm_call(
                    stage=stage,
                    model=model_name,
                    duration=duration,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    provider=effective_provider,
                    success=True,
                )
                logger.info(
                    f"[LLM] provider={effective_provider} model={model_name} stage={stage} "
                    f"duration={duration:.2f}s tokens={total_tokens} speed={tps_str} "
                    f"attempt={attempt} success=true"
                )
                return result

            except Exception as e:
                duration = time.time() - start_time
                last_exception = e
                err_str = str(e).lower()

                # Check for rate limit fallback to Ollama if configured
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "quota" in err_str
                if effective_provider == "groq" and is_rate_limit and self.settings.llm_fallback_on_rate_limit:
                    logger.warning(
                        f"[LLM:FALLBACK] from=groq to=ollama reason=rate_limit "
                        f"ollama_model={self.settings.ollama_model}"
                    )
                    effective_provider = "ollama"
                    model_name = self.settings.ollama_model
                    self.metrics.fallback_occurred = True
                    self.metrics.fallback_reason = "rate_limit"
                    # Retry immediately with Ollama
                    continue

                # For Ollama structured generation parsing errors: execute a recovery prompt on attempt 2
                if effective_provider == "ollama" and attempt < max_retries:
                    if isinstance(e, (ValidationError, ValueError)) or "validation error" in err_str:
                        logger.warning(
                            f"[LLM:OLLAMA_RECOVERY] Attempting schema recovery for stage={stage} due to: {e}"
                        )
                        correction_prompt = (
                            f"{effective_system_prompt}\n\n"
                            f"CRITICAL: Your previous response failed schema validation with error: {e}.\n"
                            f"You must strictly output valid JSON matching this schema: {schema.model_json_schema()}"
                        )
                        messages = [
                            SystemMessage(content=correction_prompt),
                            HumanMessage(content=user_prompt),
                        ]

                logger.warning(
                    f"[LLM:RETRY] provider={effective_provider} model={model_name} stage={stage} "
                    f"attempt={attempt}/{max_retries} failed in {duration:.2f}s: {e}"
                )
                if attempt < max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))

        # All retries failed
        self.metrics.record_llm_call(
            stage=stage,
            model=model_name,
            duration=0.0,
            provider=effective_provider,
            success=False,
        )
        logger.error(f"[LLM:FAILED] provider={effective_provider} model={model_name} stage={stage} failed after {max_retries} attempts.")
        raise LLMGenerationError(
            f"{effective_provider.upper()} structured generation failed for stage '{stage}' after {max_retries} attempts. Cause: {last_exception}"
        ) from last_exception

