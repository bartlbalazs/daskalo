"""
Tests for utils/llm_utils.py's invoke_with_retry — the shared retry/validation
helper every content-generation node calls around its LangChain structured
model (IMP-CC-08). `structured_model` is always a MagicMock stand-in here — no
real Gemini calls are made anywhere in this module (mirrors the mocking style
of backend/tests/test_gemini_utils.py, adapted to the LangChain-style
`.invoke(prompt)` call signature used in content-cli).
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from utils.llm_utils import invoke_with_retry


class _Widget(BaseModel):
    name: str
    count: int


def test_returns_validated_model_on_first_success():
    model = MagicMock()
    model.invoke.return_value = _Widget(name="a", count=1)

    result = invoke_with_retry(model, "prompt", pydantic_model=_Widget, retries=3, sleep_sec=0)

    assert result == _Widget(name="a", count=1)
    model.invoke.assert_called_once_with("prompt")


def test_validates_a_plain_dict_result():
    """Some LangChain configurations return a dict instead of a model instance."""
    model = MagicMock()
    model.invoke.return_value = {"name": "a", "count": 1}

    result = invoke_with_retry(model, "prompt", pydantic_model=_Widget, retries=3, sleep_sec=0)

    assert result == _Widget(name="a", count=1)


def test_recovers_after_a_validation_error():
    model = MagicMock()
    model.invoke.side_effect = [
        {"name": "a"},  # missing "count" -> pydantic ValidationError on model_validate
        {"name": "a", "count": 2},
    ]

    with patch("utils.llm_utils.time.sleep"):
        result = invoke_with_retry(model, "prompt", pydantic_model=_Widget, retries=3, sleep_sec=0)

    assert result.count == 2
    assert model.invoke.call_count == 2


def test_recovers_after_a_transient_network_error():
    model = MagicMock()
    model.invoke.side_effect = [RuntimeError("network blip"), _Widget(name="a", count=1)]

    with patch("utils.llm_utils.time.sleep"):
        result = invoke_with_retry(model, "prompt", pydantic_model=_Widget, retries=3, sleep_sec=0)

    assert result == _Widget(name="a", count=1)
    assert model.invoke.call_count == 2


def test_raises_runtime_error_after_exhausting_all_retries():
    model = MagicMock()
    model.invoke.return_value = {"name": "a"}  # always missing "count"

    with patch("utils.llm_utils.time.sleep"):
        with pytest.raises(RuntimeError, match="Failed to get valid output"):
            invoke_with_retry(model, "prompt", pydantic_model=_Widget, retries=2, sleep_sec=0)

    assert model.invoke.call_count == 2


def test_returns_raw_markdown_string_when_no_pydantic_model_given():
    """generate_grammar_summary calls invoke_with_retry without pydantic_model —
    it expects the raw string content of the LLM response back.
    """
    model = MagicMock()
    response = MagicMock()
    response.content = "## Some markdown"
    model.invoke.return_value = response

    result = invoke_with_retry(model, "prompt", retries=1, sleep_sec=0)

    assert result == "## Some markdown"


def test_joins_multi_block_content_when_no_pydantic_model_given():
    model = MagicMock()
    response = MagicMock()
    response.content = [{"type": "text", "text": "Hello "}, {"type": "text", "text": "world"}]
    model.invoke.return_value = response

    result = invoke_with_retry(model, "prompt", retries=1, sleep_sec=0)

    assert result == "Hello world"
