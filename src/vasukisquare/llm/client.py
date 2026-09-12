"""Centralized LangChain LLM client supporting Groq model pool and Ollama backends with structured output."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from langchain_core.messages import HumanMessage, SystemMessage

from vasukisquare.config import Settings, get_settings, EnvironmentConfigurationError
from vasukisquare.llm.metrics import BookGenerationMetrics
from vasukisquare.llm.pool import GroqModelPool, is_retryable_groq_error

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
        
        # Initialize Groq Model Pool
        groq_models = self.settings.get_groq_models()
        self.groq_pool = GroqModelPool(
            models=groq_models,
            strategy=self.settings.groq_model_strategy,
            cooldown_seconds=self.settings.groq_model_cooldown_seconds,
            max_attempts=self.settings.groq_max_model_attempts,
            retries_per_model=self.settings.groq_retries_per_model,
        )

        # Specialized pools for task groups if configured
        self._specialized_pools: Dict[str, GroqModelPool] = {}
        for grp in ("writing", "research", "planning"):
            grp_models = self.settings.get_groq_models(group=grp)
            if grp_models != groq_models:
                self._specialized_pools[grp] = GroqModelPool(
                    models=grp_models,
                    strategy=self.settings.groq_model_strategy,
                    cooldown_seconds=self.settings.groq_model_cooldown_seconds,
                    max_attempts=self.settings.groq_max_model_attempts,
                    retries_per_model=self.settings.groq_retries_per_model,
                )

        # Resolve active provider, model, and reasoning
        self.active_provider, self.active_model, self.provider_reason = self.settings.resolve_llm_provider()
        if self.active_provider == "groq":
            self.active_model = self.groq_pool.current_model
        self.metrics.llm_provider = self.active_provider
        self.metrics.llm_model = self.active_model

    def get_pool_for_stage(self, stage: str) -> GroqModelPool:
        """Get the Groq model pool appropriate for the execution stage."""
        stage_lower = stage.lower()
        if "research" in stage_lower and "research" in self._specialized_pools:
            return self._specialized_pools["research"]
        if ("plan" in stage_lower or "editorial" in stage_lower or "chapter" in stage_lower) and "planning" in self._specialized_pools:
            return self._specialized_pools["planning"]
        if ("write" in stage_lower or "page" in stage_lower) and "writing" in self._specialized_pools:
            return self._specialized_pools["writing"]
        return self.groq_pool

    def log_startup_banner(self) -> None:
        """Print clear startup diagnostic banner for active LLM provider without exposing secrets."""
        lines = [
            "==========================================",
            f"LLM Provider: {self.active_provider.upper()}",
            f"Model: {self.active_model}",
        ]
        if self.active_provider == "groq":
            pool_models = self.groq_pool.models
            if len(pool_models) > 1:
                lines.append(f"Model Pool ({len(pool_models)} models, strategy={self.groq_pool.strategy}): {', '.join(pool_models)}")
        elif self.active_provider == "ollama":
            lines.append(f"Endpoint: {self.settings.ollama_base_url}")
        lines.append(f"Reason: {self.provider_reason}")
        lines.append("==========================================")
        banner_text = "\n".join(lines)
        print(banner_text)
        logger.info("\n" + banner_text)

    def get_chat_model(
        self,
        temperature: Optional[float] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Any:
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
            target_model = model_name or self.groq_pool.current_model
            return ChatGroq(
                api_key=self.settings.groq_api_key,
                model_name=target_model,
                temperature=temp,
                max_retries=0,  # Retries and model failovers are managed explicitly by LLMClient
                timeout=60.0,
            )

        if target_provider == "ollama":
            from langchain_ollama import ChatOllama
            target_model = model_name or self.settings.ollama_model
            return ChatOllama(
                model=target_model,
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

        # Ensure schema name is clear in system prompt to prevent tool name hallucination
        effective_system_prompt = system_prompt
        if schema.__name__ not in effective_system_prompt:
            effective_system_prompt += f"\n\nReturn your structured response using the {schema.__name__} schema."

        # Use direct message objects to avoid template parsing errors with arbitrary braces
        messages = [
            SystemMessage(content=effective_system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # -------------------------------------------------------------
        # GROQ PROVIDER EXECUTION WITH MODEL POOL FAILOVER
        # -------------------------------------------------------------
        if effective_provider == "groq":
            pool = self.get_pool_for_stage(stage)
            pool.advance_for_new_request()
            candidate_models = pool.get_candidate_models()
            errors_by_model: Dict[str, Exception] = {}
            retries_per_model = self.settings.groq_retries_per_model

            for model_candidate in candidate_models:
                for attempt in range(1, retries_per_model + 1):
                    start_time = time.time()
                    try:
                        llm = self.get_chat_model(
                            temperature=temperature,
                            provider="groq",
                            model_name=model_candidate,
                        )
                        structured_llm = llm.with_structured_output(schema)

                        logger.debug(
                            f"[LLM:START] provider=groq model={model_candidate} "
                            f"stage={stage} attempt={attempt}/{retries_per_model}"
                        )
                        result = await structured_llm.ainvoke(messages)
                        duration = time.time() - start_time

                        if not isinstance(result, schema):
                            if isinstance(result, dict):
                                result = schema.model_validate(result)
                            else:
                                raise ValueError(f"LLM returned unexpected type {type(result)}, expected {schema.__name__}")

                        prompt_tokens, completion_tokens = self._extract_tokens_from_response(result)
                        total_tokens = prompt_tokens + completion_tokens
                        tps_str = f"{completion_tokens / duration:.1f} tok/s" if completion_tokens > 0 and duration > 0 else "N/A"

                        # Record model success & telemetry
                        pool.record_success(model_candidate)
                        pool.switch_to_model(model_candidate, reason="successful call")
                        self.active_model = model_candidate

                        self.metrics.record_llm_call(
                            stage=stage,
                            model=model_candidate,
                            duration=duration,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            provider="groq",
                            success=True,
                        )
                        logger.info(
                            f"[LLM] provider=groq model={model_candidate} stage={stage} "
                            f"duration={duration:.2f}s tokens={total_tokens} speed={tps_str} "
                            f"attempt={attempt} success=true"
                        )
                        return result

                    except Exception as e:
                        duration = time.time() - start_time
                        errors_by_model[model_candidate] = e
                        is_retryable, is_rate_limit, retry_after, is_unavailable = is_retryable_groq_error(e)
                        
                        pool.record_failure(
                            model=model_candidate,
                            error=e,
                            is_rate_limit=is_rate_limit,
                            retry_after=retry_after,
                        )

                        if not is_retryable:
                            # Non-retryable error (e.g. 401 Unauthorized / Invalid API Key)
                            # Fail immediately without endlessly switching models
                            logger.error(
                                f"[LLM:NON_RETRYABLE] provider=groq model={model_candidate} stage={stage} "
                                f"non-retryable error: {e}"
                            )
                            self.metrics.record_llm_call(
                                stage=stage,
                                model=model_candidate,
                                duration=duration,
                                provider="groq",
                                success=False,
                            )
                            raise e

                        # Model is retryable (rate limit, quota, server overload, unavailable)
                        reason_type = "rate_limit" if is_rate_limit else ("unavailable" if is_unavailable else "server_error")
                        logger.warning(
                            f"[LLM:MODEL_ERROR] provider=groq model={model_candidate} stage={stage} "
                            f"attempt={attempt}/{retries_per_model} failed ({reason_type}): {e}"
                        )

                        if self.settings.groq_model_fallback and len(candidate_models) > 1:
                            # Switch immediately to next model in pool
                            next_models = [m for m in candidate_models if m != model_candidate and m not in errors_by_model]
                            next_model_name = next_models[0] if next_models else "None"
                            logger.warning(
                                f"[LLM:FAILOVER] Failover triggered: '{model_candidate}' -> '{next_model_name}' "
                                f"for stage='{stage}'"
                            )
                            break
                        else:
                            # Single model or fallback disabled: backoff retry
                            if attempt < retries_per_model:
                                backoff = retry_after if retry_after else (2 ** (attempt - 1))
                                await asyncio.sleep(backoff)

            # All Groq candidate models have failed
            # Check for provider fallback to Ollama if configured
            if self.settings.llm_fallback_on_rate_limit:
                logger.warning(
                    f"[LLM:PROVIDER_FALLBACK] All Groq models ({list(errors_by_model.keys())}) exhausted. "
                    f"Falling back to Ollama model={self.settings.ollama_model} for stage='{stage}'."
                )
                effective_provider = "ollama"
                self.metrics.fallback_occurred = True
                had_rate_limit = any("429" in str(err) or "rate limit" in str(err).lower() or "quota" in str(err).lower() for err in errors_by_model.values())
                self.metrics.fallback_reason = "rate_limit" if had_rate_limit else "groq_pool_exhausted"
            else:
                summary_errs = "; ".join(f"[{m}]: {err}" for m, err in errors_by_model.items())
                self.metrics.record_llm_call(
                    stage=stage,
                    model=self.groq_pool.current_model,
                    duration=0.0,
                    provider="groq",
                    success=False,
                )
                raise LLMGenerationError(
                    f"Groq structured generation failed for stage '{stage}'. All pool models exhausted: {summary_errs}"
                )

        # -------------------------------------------------------------
        # OLLAMA PROVIDER EXECUTION (PRIMARY OR FALLBACK)
        # -------------------------------------------------------------
        if effective_provider == "ollama":
            model_name = self.settings.ollama_model
            last_exception: Optional[Exception] = None

            for attempt in range(1, max_retries + 1):
                start_time = time.time()
                try:
                    llm = self.get_chat_model(temperature=temperature, provider="ollama", model_name=model_name)
                    structured_llm = llm.with_structured_output(schema)

                    logger.debug(
                        f"[LLM:START] provider=ollama model={model_name} "
                        f"stage={stage} attempt={attempt}/{max_retries}"
                    )
                    result = await structured_llm.ainvoke(messages)
                    duration = time.time() - start_time

                    if not isinstance(result, schema):
                        if isinstance(result, dict):
                            result = schema.model_validate(result)
                        else:
                            raise ValueError(f"LLM returned unexpected type {type(result)}, expected {schema.__name__}")

                    prompt_tokens, completion_tokens = self._extract_tokens_from_response(result)
                    total_tokens = prompt_tokens + completion_tokens
                    tps_str = f"{completion_tokens / duration:.1f} tok/s" if completion_tokens > 0 and duration > 0 else "N/A"

                    self.metrics.record_llm_call(
                        stage=stage,
                        model=model_name,
                        duration=duration,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        provider="ollama",
                        success=True,
                    )
                    logger.info(
                        f"[LLM] provider=ollama model={model_name} stage={stage} "
                        f"duration={duration:.2f}s tokens={total_tokens} speed={tps_str} "
                        f"attempt={attempt} success=true"
                    )
                    return result

                except Exception as e:
                    duration = time.time() - start_time
                    last_exception = e
                    err_str = str(e).lower()

                    # For Ollama structured generation parsing errors: execute recovery prompt on attempt 2
                    if attempt < max_retries and (isinstance(e, (ValidationError, ValueError)) or "validation error" in err_str):
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
                        f"[LLM:RETRY] provider=ollama model={model_name} stage={stage} "
                        f"attempt={attempt}/{max_retries} failed in {duration:.2f}s: {e}"
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** (attempt - 1))

            self.metrics.record_llm_call(
                stage=stage,
                model=model_name,
                duration=0.0,
                provider="ollama",
                success=False,
            )
            logger.error(f"[LLM:FAILED] provider=ollama model={model_name} stage={stage} failed after {max_retries} attempts.")
            raise LLMGenerationError(
                f"Ollama structured generation failed for stage '{stage}' after {max_retries} attempts. Cause: {last_exception}"
            ) from last_exception

        raise LLMGenerationError(f"Unsupported provider: {effective_provider}")
