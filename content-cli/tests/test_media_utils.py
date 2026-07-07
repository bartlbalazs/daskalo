"""
Tests for utils/media_utils.py (IMP-CC-08 + IMP-CC-04).

Both the real texttospeech.TextToSpeechClient and google.genai.Client
constructors are always patched out here — no credentials/network are ever
touched. Covers:
  - _get_tts_client() / _get_genai_client() constructing their client exactly
    once per thread and reusing it (IMP-CC-04's whole point — avoid building a
    brand-new client per individual TTS/image task).
  - synthesize_speech() / generate_image() still behaving correctly (write the
    right bytes on success, return False on failure) after the client-caching
    refactor.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

import utils.media_utils as media_utils


@pytest.fixture(autouse=True)
def _reset_thread_local():
    """Every test starts with a clean thread-local client cache — this state is
    genuinely global-per-thread by design, so it can't be parametrised away.
    """
    media_utils._thread_local = threading.local()
    yield
    media_utils._thread_local = threading.local()


class TestGetTtsClient:
    def test_constructs_client_once_and_reuses_it_across_calls(self):
        with patch("utils.media_utils.texttospeech.TextToSpeechClient") as mock_ctor:
            mock_ctor.return_value = "client-instance"

            first = media_utils._get_tts_client()
            second = media_utils._get_tts_client()

        assert first == "client-instance"
        assert first is second
        mock_ctor.assert_called_once()

    def test_separate_threads_get_separate_client_instances(self):
        seen: dict[str, object] = {}

        def _run(name: str) -> None:
            with patch("utils.media_utils.texttospeech.TextToSpeechClient") as mock_ctor:
                mock_ctor.return_value = object()
                seen[name] = media_utils._get_tts_client()

        t1 = threading.Thread(target=_run, args=("t1",))
        t2 = threading.Thread(target=_run, args=("t2",))
        t1.start()
        t1.join()
        t2.start()
        t2.join()

        assert seen["t1"] is not seen["t2"]


class TestGetGenaiClient:
    def test_constructs_client_once_and_reuses_it_across_calls(self):
        with patch("utils.media_utils.genai.Client") as mock_ctor:
            mock_ctor.return_value = "genai-client-instance"

            first = media_utils._get_genai_client("test-project")
            second = media_utils._get_genai_client("test-project")

        assert first == "genai-client-instance"
        assert first is second
        mock_ctor.assert_called_once()
        assert mock_ctor.call_args.kwargs["project"] == "test-project"
        assert mock_ctor.call_args.kwargs["vertexai"] is True


class TestSynthesizeSpeech:
    def test_writes_audio_bytes_to_output_path_on_success(self, tmp_path):
        with patch("utils.media_utils.texttospeech.TextToSpeechClient") as mock_ctor:
            client = mock_ctor.return_value
            client.synthesize_speech.return_value.audio_content = b"mp3-bytes"

            out_path = tmp_path / "out.mp3"
            ok = media_utils.synthesize_speech("Γεια σου", media_utils.VOICE_FEMALE, str(out_path))

        assert ok is True
        assert out_path.read_bytes() == b"mp3-bytes"

    def test_returns_false_and_does_not_raise_on_client_exception(self, tmp_path):
        with patch("utils.media_utils.texttospeech.TextToSpeechClient") as mock_ctor:
            mock_ctor.return_value.synthesize_speech.side_effect = RuntimeError("quota exceeded")

            ok = media_utils.synthesize_speech("Γεια σου", media_utils.VOICE_FEMALE, str(tmp_path / "out.mp3"))

        assert ok is False


class TestGenerateImage:
    def test_writes_image_bytes_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

        with patch("utils.media_utils.genai.Client") as mock_ctor:
            client = mock_ctor.return_value
            part = MagicMock()
            part.inline_data.data = b"jpeg-bytes"
            response = MagicMock()
            response.candidates = [MagicMock(content=MagicMock(parts=[part]))]
            client.models.generate_content.return_value = response

            out_path = tmp_path / "out.jpg"
            ok = media_utils.generate_image("a scene", str(out_path))

        assert ok is True
        assert out_path.read_bytes() == b"jpeg-bytes"

    def test_returns_false_when_response_has_no_image_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

        with patch("utils.media_utils.genai.Client") as mock_ctor:
            client = mock_ctor.return_value
            part = MagicMock()
            part.inline_data = None
            response = MagicMock()
            response.candidates = [MagicMock(content=MagicMock(parts=[part]))]
            client.models.generate_content.return_value = response

            ok = media_utils.generate_image("a scene", str(tmp_path / "out.jpg"))

        assert ok is False

    def test_returns_false_and_does_not_raise_on_client_exception(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

        with patch("utils.media_utils.genai.Client") as mock_ctor:
            mock_ctor.return_value.models.generate_content.side_effect = RuntimeError("quota exceeded")

            ok = media_utils.generate_image("a scene", str(tmp_path / "out.jpg"))

        assert ok is False
