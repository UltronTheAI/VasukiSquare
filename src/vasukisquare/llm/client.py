"""Centralized LangChain + Groq LLM client with structured outputs and observability logging."""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from vasukisquare.config import Settings, get_settings
from vasukisquare.llm.metrics import BookGenerationMetrics

logger = logging.getLogger("vasukisquare.llm")

T = TypeVar("T", bound=BaseModel)


class GroqGenerationError(Exception):
    """Raised when a Groq LLM generation call fails in production mode."""
    pass


class LLMClient:
    """Wrapper around LangChain ChatGroq with structured logging, retries, and telemetry."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        metrics: Optional[BookGenerationMetrics] = None,
    ):
        self.settings = settings or get_settings()
        self.metrics = metrics or BookGenerationMetrics()
        self._llm_instance: Optional[ChatGroq] = None

    def get_chat_model(self, temperature: float = 0.2) -> ChatGroq:
        """Instantiate and return ChatGroq with configured settings."""
        if not self.settings.groq_api_key:
            raise GroqGenerationError(
                "Cannot initialize Groq LLM: GROQ_API_KEY is missing or empty. "
                "Set GROQ_API_KEY in .env or .env.local, or set VASUKISQUARE_MOCK_MODE=true for offline mock runs."
            )

        return ChatGroq(
            api_key=self.settings.groq_api_key,
            model_name=self.settings.groq_model,
            temperature=temperature,
            max_retries=2,
            timeout=60.0,
        )

    async def invoke_structured(
        self,
        schema: Type[T],
        system_prompt: str,
        user_prompt: str,
        stage: str,
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> T:
        """Execute a structured LLM request returning an instance of Pydantic schema T."""
        model_name = self.settings.groq_model
        last_exception: Optional[Exception] = None

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_prompt),
        ])

        for attempt in range(1, max_retries + 1):
            start_time = time.time()
            try:
                llm = self.get_chat_model(temperature=temperature)
                structured_llm = llm.with_structured_output(schema)
                chain = prompt_template | structured_llm

                logger.debug(f"[LLM:START] provider=groq model={model_name} stage={stage} attempt={attempt}/{max_retries}")
                result = await chain.ainvoke({})

                duration = time.time() - start_time

                if not isinstance(result, schema):
                    raise ValueError(f"LLM returned unexpected type {type(result)}, expected {schema.__name__}")

                # Record metrics and log observability
                self.metrics.record_llm_call(
                    stage=stage,
                    model=model_name,
                    duration=duration,
                    success=True,
                )
                logger.info(
                    f"[LLM] provider=groq model={model_name} stage={stage} "
                    f"duration={duration:.2f}s attempt={attempt} success=true"
                )
                return result

            except Exception as e:
                duration = time.time() - start_time
                last_exception = e
                logger.warning(
                    f"[LLM:RETRY] provider=groq model={model_name} stage={stage} "
                    f"attempt={attempt}/{max_retries} failed in {duration:.2f}s: {e}"
                )
                if attempt < max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))

        # All retries failed
        self.metrics.record_llm_call(
            stage=stage,
            model=model_name,
            duration=0.0,
            success=False,
        )
        logger.error(f"[LLM:FAILED] provider=groq model={model_name} stage={stage} failed after {max_retries} attempts.")
        raise GroqGenerationError(
            f"Groq structured generation failed for stage '{stage}' after {max_retries} attempts. Cause: {last_exception}"
        ) from last_exception

