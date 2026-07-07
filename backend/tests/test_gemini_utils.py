"""
Tests for services/gemini_utils.py — the shared Gemini retry + parse helpers.
"""

from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions

from services.gemini_utils import GeminiCallFailed, generate_content_with_retry, parse_json_response


def _make_response(text: str | None) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# generate_content_with_retry — happy path
# ---------------------------------------------------------------------------


def test_generate_content_with_retry_happy_path():
    client = MagicMock()
    client.models.generate_content.return_value = _make_response("hello")

    response = generate_content_with_retry(client, model="gemini-2.5-flash", contents="hi")

    assert response.text == "hello"
    client.models.generate_content.assert_called_once_with(model="gemini-2.5-flash", contents="hi")


def test_generate_content_with_retry_passes_config_when_given():
    client = MagicMock()
    client.models.generate_content.return_value = _make_response("hello")
    config = MagicMock()

    generate_content_with_retry(client, model="gemini-2.5-flash", contents="hi", config=config)

    client.models.generate_content.assert_called_once_with(model="gemini-2.5-flash", contents="hi", config=config)


# ---------------------------------------------------------------------------
# generate_content_with_retry — transient error then success
# ---------------------------------------------------------------------------


def test_generate_content_with_retry_recovers_after_transient_error():
    client = MagicMock()
    client.models.generate_content.side_effect = [
        google_exceptions.ServiceUnavailable("temporarily down"),
        _make_response("recovered"),
    ]

    with patch("services.gemini_utils.time.sleep"):
        response = generate_content_with_retry(client, model="gemini-2.5-flash", contents="hi", max_retries=2)

    assert response.text == "recovered"
    assert client.models.generate_content.call_count == 2


def test_generate_content_with_retry_recovers_after_empty_response():
    client = MagicMock()
    client.models.generate_content.side_effect = [
        _make_response(""),
        _make_response("second try"),
    ]

    with patch("services.gemini_utils.time.sleep"):
        response = generate_content_with_retry(client, model="gemini-2.5-flash", contents="hi", max_retries=2)

    assert response.text == "second try"
    assert client.models.generate_content.call_count == 2


# ---------------------------------------------------------------------------
# generate_content_with_retry — exhausted retries
# ---------------------------------------------------------------------------


def test_generate_content_with_retry_raises_after_exhausting_transient_errors():
    client = MagicMock()
    client.models.generate_content.side_effect = google_exceptions.ServiceUnavailable("down")

    with patch("services.gemini_utils.time.sleep"):
        with pytest.raises(GeminiCallFailed, match="Gemini call failed after retries"):
            generate_content_with_retry(client, model="gemini-2.5-flash", contents="hi", max_retries=2)

    # max_retries=2 -> 3 total attempts
    assert client.models.generate_content.call_count == 3


def test_generate_content_with_retry_raises_after_exhausting_empty_responses():
    client = MagicMock()
    client.models.generate_content.return_value = _make_response(None)

    with patch("services.gemini_utils.time.sleep"):
        with pytest.raises(GeminiCallFailed, match="Gemini call failed after retries"):
            generate_content_with_retry(client, model="gemini-2.5-flash", contents="hi", max_retries=1)

    assert client.models.generate_content.call_count == 2


def test_generate_content_with_retry_does_not_retry_non_transient_errors():
    """A non-transient error (e.g. a bug/bad request) should propagate immediately."""
    client = MagicMock()
    client.models.generate_content.side_effect = google_exceptions.InvalidArgument("bad request")

    with pytest.raises(google_exceptions.InvalidArgument):
        generate_content_with_retry(client, model="gemini-2.5-flash", contents="hi", max_retries=2)

    client.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# parse_json_response
# ---------------------------------------------------------------------------


def test_parse_json_response_valid_json():
    result = parse_json_response('{"score": 80, "feedback": "ok", "isCorrect": true}')
    assert result == {"score": 80, "feedback": "ok", "isCorrect": True}


def test_parse_json_response_raises_value_error_on_malformed_json():
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_json_response("not json at all {")
