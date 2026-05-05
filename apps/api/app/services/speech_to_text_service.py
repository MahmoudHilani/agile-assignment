from io import BytesIO

MAX_AUDIO_DURATION_SECONDS = 20.0
MAX_AUDIO_DURATION_ERROR = "Audio must be 20 seconds or shorter"


def transcribe_audio(
    audio_bytes: bytes,
    language: str = "en-US",
    max_duration_seconds: float = MAX_AUDIO_DURATION_SECONDS,
) -> str:
    if not audio_bytes:
        raise ValueError("Audio file is empty")

    try:
        import speech_recognition as sr
    except ImportError as exc:
        raise RuntimeError("Speech recognition support is not installed") from exc

    recognizer = sr.Recognizer()

    try:
        with sr.AudioFile(BytesIO(audio_bytes)) as source:
            if source.DURATION > max_duration_seconds:
                raise ValueError(MAX_AUDIO_DURATION_ERROR)
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio, language=language)
    except ValueError as exc:
        if str(exc) == MAX_AUDIO_DURATION_ERROR:
            raise
        raise ValueError("Unsupported or invalid audio file") from exc
    except sr.UnknownValueError as exc:
        raise ValueError("Could not understand the audio") from exc
    except sr.RequestError as exc:
        raise RuntimeError("Speech recognition service request failed") from exc
