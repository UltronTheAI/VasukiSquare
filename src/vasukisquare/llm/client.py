"""Centralized LangChain LLM client supporting Groq model pool and Ollama backends with structured output."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from langchain_core.messages import HumanMessage, SystemMessage

from vasukisquare.config import Settings, get_settings
from vasukisquare.llm.metrics import BookGenerationMetrics
from vasukisquare.llm.pool import (
    GroqKeyPool,
    GroqKeyState,
    GroqModelPool,
    is_retryable_groq_error,
)

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

        # Initialize Groq API Key Pool
        groq_api_keys = self.settings.get_groq_api_keys()
        self.groq_key_pool = GroqKeyPool(
            api_keys=groq_api_keys,
            strategy=self.settings.groq_key_strategy,
            cooldown_seconds=self.settings.groq_key_cooldown_seconds,
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
            if len(self.groq_key_pool.keys) > 1:
                lines.append(f"API Key Pool: {len(self.groq_key_pool.keys)} keys configured (strategy={self.groq_key_pool.strategy})")
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
        api_key: Optional[str] = None,
    ) -> Any:
        """Instantiate and return the appropriate LangChain chat model."""
        target_provider = provider or self.active_provider
        temp = temperature if temperature is not None else self.settings.llm_temperature

        if target_provider == "groq":
            resolved_key = api_key or self.settings.groq_api_key
            if not resolved_key or not resolved_key.strip():
                raise GroqGenerationError(
                    "Cannot initialize Groq LLM: GROQ_API_KEY is missing or empty. "
                    "Set GROQ_API_KEY in .env/.env.local or set LLM_PROVIDER=auto / LLM_PROVIDER=ollama."
                )
            from langchain_groq import ChatGroq
            target_model = model_name or self.groq_pool.current_model
            return ChatGroq(
                api_key=resolved_key,
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
        # GROQ PROVIDER EXECUTION WITH MODEL POOL & KEY POOL ROTATION
        # -------------------------------------------------------------
        if effective_provider == "groq":
            if not self.groq_key_pool.has_keys():
                if self.settings.llm_fallback_on_rate_limit:
                    logger.warning(
                        f"[LLM:PROVIDER_FALLBACK] No Groq API keys available. "
                        f"Falling back to Ollama model={self.settings.ollama_model} for stage='{stage}'."
                    )
                    effective_provider = "ollama"
                else:
                    raise GroqGenerationError(
                        "Cannot initialize Groq LLM: GROQ_API_KEY is missing or empty. "
                        "Set GROQ_API_KEY in .env/.env.local or set LLM_PROVIDER=auto / LLM_PROVIDER=ollama."
                    )

        if effective_provider == "groq":
            pool = self.get_pool_for_stage(stage)
            pool.advance_for_new_request()
            self.groq_key_pool.advance_for_new_request()

            candidate_models = pool.get_candidate_models()
            errors_by_attempt: Dict[str, Exception] = {}
            retries_per_model = self.settings.groq_retries_per_model
            structured_retries_attempted: set[str] = set()

            async def _try_invoke_model_with_key(
                model_name: str,
                key_state: GroqKeyState,
                msgs: List[Any],
                is_recovery: bool = False,
            ) -> Optional[T]:
                start_time = time.time()
                try:
                    try:
                        llm = self.get_chat_model(
                            temperature=temperature,
                            provider="groq",
                            model_name=model_name,
                            api_key=key_state.api_key,
                        )
                    except TypeError:
                        llm = self.get_chat_model(
                            temperature=temperature,
                            provider="groq",
                            model_name=model_name,
                        )
                    structured_llm = llm.with_structured_output(schema)

                    logger.debug(
                        f"[LLM:START] provider=groq model={model_name} key={key_state.label} "
                        f"stage={stage} recovery={is_recovery}"
                    )
                    raw_res = await structured_llm.ainvoke(msgs)
                    duration = time.time() - start_time

                    if not isinstance(raw_res, schema):
                        if isinstance(raw_res, dict):
                            raw_res = schema.model_validate(raw_res)
                        else:
                            raise ValueError(f"LLM returned unexpected type {type(raw_res)}, expected {schema.__name__}")

                    prompt_tokens, completion_tokens = self._extract_tokens_from_response(raw_res)
                    total_tokens = prompt_tokens + completion_tokens
                    tps_str = f"{completion_tokens / duration:.1f} tok/s" if completion_tokens > 0 and duration > 0 else "N/A"

                    # Record success & telemetry for BOTH key and model
                    self.groq_key_pool.mark_success(key_state)
                    pool.record_success(model_name)
                    pool.switch_to_model(model_name, reason="successful call")
                    self.active_model = model_name

                    self.metrics.record_llm_call(
                        stage=stage,
                        model=model_name,
                        duration=duration,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        provider="groq",
                        success=True,
                    )
                    logger.info(
                        f"[LLM] provider=groq model={model_name} key={key_state.label} stage={stage} "
                        f"duration={duration:.2f}s tokens={total_tokens} speed={tps_str} "
                        f"success=true"
                    )
                    return raw_res

                except Exception as e:
                    duration = time.time() - start_time
                    err_info = is_retryable_groq_error(e)
                    errors_by_attempt[f"{model_name}:{key_state.label}"] = e

                    # Auth error (401 / Invalid API Key) -> mark this specific key invalid
                    if err_info.is_auth_error:
                        self.groq_key_pool.mark_invalid(key_state)
                        logger.error(
                            f"[LLM:AUTH_ERROR] provider=groq model={model_name} key={key_state.label} "
                            f"stage={stage} invalid API key (401). Rotating to next key if available."
                        )
                        if self.groq_key_pool.active_key_count() == 0:
                            raise e
                        return None

                    # Impossible limit (e.g. context length exceeded) -> skip model immediately
                    if err_info.is_impossible_limit:
                        logger.warning(
                            f"[LLM:IMPOSSIBLE_LIMIT] provider=groq model={model_name} key={key_state.label} "
                            f"stage={stage} prompt exceeds model context/OTPM limit: {e}"
                        )
                        pool.record_failure(model=model_name, error=e, is_rate_limit=False)
                        raise e

                    # Structured output parsing error -> check if failed_generation has valid payload first
                    if err_info.is_structured_error:
                        try:
                            extracted_args = None
                            body = getattr(e, "body", None)
                            if isinstance(body, dict):
                                err_dict = body.get("error", {})
                                if isinstance(err_dict, dict) and "failed_generation" in err_dict:
                                    raw_gen = err_dict["failed_generation"]
                                    import json
                                    gen_obj = json.loads(raw_gen) if isinstance(raw_gen, str) else raw_gen
                                    if isinstance(gen_obj, dict):
                                        extracted_args = gen_obj.get("arguments", gen_obj)
                                        if isinstance(extracted_args, str):
                                            extracted_args = json.loads(extracted_args)
                            if extracted_args:
                                validated = schema.model_validate(extracted_args)
                                logger.info(
                                    f"[LLM:RECOVERED_FAILED_GENERATION] provider=groq model={model_name} key={key_state.label} "
                                    f"stage={stage} successfully recovered structured output from failed_generation."
                                )
                                self.groq_key_pool.mark_success(key_state)
                                pool.record_success(model_name)
                                return validated
                        except Exception:
                            pass

                        pool.record_failure(model=model_name, error=e, is_structured_error=True)
                        logger.warning(
                            f"[LLM:STRUCTURED_ERROR] provider=groq model={model_name} key={key_state.label} "
                            f"stage={stage}: {e}"
                        )
                        if not is_recovery and model_name not in structured_retries_attempted:
                            structured_retries_attempted.add(model_name)
                            recovery_sys = (
                                f"{effective_system_prompt}\n\n"
                                f"CRITICAL: Output strictly valid JSON matching the schema with no preamble or commentary."
                            )
                            recovery_msgs = [
                                SystemMessage(content=recovery_sys),
                                HumanMessage(content=user_prompt),
                            ]
                            logger.info(f"[LLM:SAME_MODEL_RETRY] Retrying structured prompt on {model_name} with {key_state.label}...")
                            return await _try_invoke_model_with_key(model_name, key_state, recovery_msgs, is_recovery=True)
                        return None

                    # Rate limit (429) -> mark key rate-limited and model failure with retry_after
                    if err_info.is_rate_limit:
                        self.groq_key_pool.mark_rate_limited(key_state, retry_after=err_info.retry_after)
                        pool.record_failure(
                            model=model_name,
                            error=e,
                            is_rate_limit=True,
                            retry_after=err_info.retry_after,
                        )
                        logger.warning(
                            f"[LLM:RATE_LIMIT] provider=groq model={model_name} key={key_state.label} "
                            f"stage={stage} rate limited (429). Rotating key/model."
                        )
                        return None

                    # Non-retryable error other than auth error
                    if not err_info.is_retryable:
                        logger.error(
                            f"[LLM:NON_RETRYABLE] provider=groq model={model_name} key={key_state.label} "
                            f"stage={stage} non-retryable error: {e}"
                        )
                        self.metrics.record_llm_call(
                            stage=stage,
                            model=model_name,
                            duration=duration,
                            provider="groq",
                            success=False,
                        )
                        raise e

                    # Server error / transient network error
                    pool.record_failure(
                        model=model_name,
                        error=e,
                        is_rate_limit=False,
                        retry_after=err_info.retry_after,
                    )
                    logger.warning(
                        f"[LLM:SERVER_ERROR] provider=groq model={model_name} key={key_state.label} "
                        f"stage={stage} server error: {e}"
                    )
                    return None

            # 1. Iterate through candidate models and candidate keys
            for model_candidate in candidate_models:
                candidate_keys = self.groq_key_pool.get_candidate_keys()
                if not candidate_keys:
                    logger.error("[GroqKeyPool] All configured API keys are invalid (401).")
                    break

                for key_state in candidate_keys:
                    for attempt in range(max(1, retries_per_model)):
                        if attempt > 0:
                            await asyncio.sleep(min(1.5 ** attempt, 5.0))
                        try:
                            res = await _try_invoke_model_with_key(model_candidate, key_state, messages)
                            if res is not None:
                                return res
                            if key_state.is_in_cooldown() or pool.is_in_cooldown(model_candidate):
                                break
                        except Exception as err:
                            err_info = is_retryable_groq_error(err)
                            if err_info.is_impossible_limit:
                                break
                            if not err_info.is_retryable and not err_info.is_auth_error:
                                raise err
                            if err_info.is_auth_error and self.groq_key_pool.active_key_count() == 0:
                                raise err
                            break

                if not self.settings.groq_model_fallback:
                    break

            # 2. If all candidate models & keys failed, check if rate-limited and smart wait is eligible
            rate_limited_keys = [k for k in self.groq_key_pool.keys if k.is_in_cooldown() and not k.is_invalid]
            rate_limited_models = [m for m in candidate_models if pool.is_in_cooldown(m)]
            if (rate_limited_keys or rate_limited_models) and self.settings.groq_wait_for_rate_limit:
                earliest_key, key_wait = self.groq_key_pool.get_earliest_cooldown_wait() if rate_limited_keys else (None, 0.0)
                earliest_model, model_wait = pool.get_earliest_available_wait(candidate_models) if rate_limited_models else (None, 0.0)

                wait_sec = 0.0
                if rate_limited_keys and rate_limited_models:
                    wait_sec = max(key_wait, model_wait)
                elif rate_limited_keys:
                    wait_sec = key_wait
                elif rate_limited_models:
                    wait_sec = model_wait

                retry_key = earliest_key or (self.groq_key_pool.keys[0] if self.groq_key_pool.keys else None)
                retry_model = earliest_model or candidate_models[0]

                if wait_sec <= self.settings.groq_max_rate_limit_wait_seconds:
                    total_wait = wait_sec + self.settings.groq_rate_limit_buffer_seconds
                    logger.info(
                        f"[GroqPool] All candidates temporarily rate-limited. Earliest available in {wait_sec:.1f}s. "
                        f"Waiting {total_wait:.1f}s to retry..."
                    )
                    await asyncio.sleep(total_wait)
                    if retry_key:
                        for model_candidate in candidate_models:
                            retry_res = await _try_invoke_model_with_key(model_candidate, retry_key, messages)
                            if retry_res is not None:
                                return retry_res

            # 3. Check for provider fallback to Ollama if configured
            if self.settings.llm_fallback_on_rate_limit:
                logger.warning(
                    f"[LLM:PROVIDER_FALLBACK] All Groq keys/models ({list(errors_by_attempt.keys())}) exhausted. "
                    f"Falling back to Ollama model={self.settings.ollama_model} for stage='{stage}'."
                )
                effective_provider = "ollama"
                self.metrics.fallback_occurred = True
                had_rate_limit = any(
                    "429" in str(err) or "rate limit" in str(err).lower() or "quota" in str(err).lower()
                    for err in errors_by_attempt.values()
                )
                self.metrics.fallback_reason = "rate_limit" if had_rate_limit else "groq_pool_exhausted"
            else:
                summary_errs = "; ".join(f"[{k}]: {err}" for k, err in errors_by_attempt.items())
                self.metrics.record_llm_call(
                    stage=stage,
                    model=self.groq_pool.current_model,
                    duration=0.0,
                    provider="groq",
                    success=False,
                )
                raise LLMGenerationError(
                    f"Groq structured generation failed for stage '{stage}'. All pool keys/models exhausted: {summary_errs}"
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
