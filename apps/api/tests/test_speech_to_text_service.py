import sys
from types import SimpleNamespace

import pytest

from app.services.speech_to_text_service import transcribe_audio


class FakeAudioFile:
    def __init__(self, _: object, duration: float = 2.0) -> None:
        self.DURATION = duration

    def __enter__(self) -> "FakeAudioFile":
        return self

    def __exit__(self, *_: object) -> None:
        return None


class FakeRecognizer:
    def record(self, _: FakeAudioFile) -> object:
        return object()

    def recognize_google(self, _: object, language: str) -> str:
        assert language == "en-IE"
        return "hello from voice"


class FakeSpeechRecognition:
    UnknownValueError = ValueError
    RequestError = RuntimeError
    Recognizer = FakeRecognizer

    def __init__(self, duration: float = 2.0) -> None:
        self.duration = duration

    def AudioFile(self, audio_file: object) -> FakeAudioFile:
        return FakeAudioFile(audio_file, duration=self.duration)


def test_transcribe_audio_rejects_recordings_longer_than_20_seconds(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "speech_recognition", FakeSpeechRecognition(duration=20.1))

    with pytest.raises(ValueError, match="20 seconds or shorter"):
        transcribe_audio(b"audio", language="en-IE")


def test_transcribe_audio_allows_recordings_up_to_20_seconds(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "speech_recognition", FakeSpeechRecognition(duration=20.0))

    assert transcribe_audio(b"audio", language="en-IE") == "hello from voice"
