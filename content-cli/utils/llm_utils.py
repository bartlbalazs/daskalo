"""
Utility functions for interacting with LLMs in the LangGraph pipeline.
"""

import json
import logging
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def invoke_with_retry(
    structured_model: Any,
    prompt: str,
    pydantic_model: type[T] | None = None,
    retries: int = 3,
    sleep_sec: int = 2,
    log_prefix: str = "LLM Call",
) -> T | str:
    """
    Centralized utility to invoke a LangChain structured model with retries,
    detailed execution time logging, and robust error handling.

    If `pydantic_model` is provided, ensures the result is validated against it.
    If not, assumes the model returns a raw string.
    """
    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            logger.info("[%s] Attempt %d/%d: Sending request to Gemini...", log_prefix, attempt, retries)
            start_time = time.time()

            result = structured_model.invoke(prompt)

            elapsed = time.time() - start_time
            logger.info("[%s] Attempt %d: Received response in %.2f seconds", log_prefix, attempt, elapsed)

            # If expecting a structured Pydantic model
            if pydantic_model is not None:
                if not isinstance(result, pydantic_model):
                    # LangChain sometimes returns dicts instead of instances depending on the model/method
                    result = pydantic_model.model_validate(result)
                return result

            # If expecting a raw string (e.g., Markdown generation)
            if hasattr(result, "content"):
                if isinstance(result.content, list):
                    return "".join(
                        block.get("text", "")
                        for block in result.content
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                return str(result.content)
            return str(result)

        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
            elapsed = time.time() - start_time
            logger.warning(
                "[%s] Attempt %d/%d failed after %.2fs: Parsing/Validation Error: %s",
                log_prefix,
                attempt,
                retries,
                elapsed,
                exc,
            )
            if attempt < retries:
                logger.info("[%s] Sleeping for %d seconds before retrying...", log_prefix, sleep_sec)
                time.sleep(sleep_sec)

        except Exception as exc:
            # Catch network timeouts, API errors, etc.
            last_exc = exc
            elapsed = time.time() - start_time
            logger.error(
                "[%s] Attempt %d/%d failed after %.2fs: API/Network Error: %s",
                log_prefix,
                attempt,
                retries,
                elapsed,
                exc,
            )
            if attempt < retries:
                logger.info("[%s] Sleeping for %d seconds before retrying...", log_prefix, sleep_sec)
                time.sleep(sleep_sec)

    logger.error("[%s] All %d attempts failed.", log_prefix, retries)
    raise RuntimeError(f"[{log_prefix}] Failed to get valid output after {retries} attempts") from last_exc
