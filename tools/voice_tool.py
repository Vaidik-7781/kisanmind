"""
Voice tool:
- Input:  Whisper (open-source, runs locally, free)
- Output: gTTS (Google TTS, free, no key needed)
Supports Hindi, Marathi, Telugu, Tamil, Punjabi, Kannada, Bengali
"""

import os
import tempfile
import whisper
from gtts import gTTS
from config.settings import WHISPER_MODEL

# Load Whisper model once (downloads on first run ~140MB for 'base')
_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model(WHISPER_MODEL)
    return _whisper_model


# ─── Language map ────────────────────────────────────────────────────────────
LANG_MAP = {
    "hi": "hi",   # Hindi
    "mr": "mr",   # Marathi
    "te": "te",   # Telugu
    "ta": "ta",   # Tamil
    "pa": "pa",   # Punjabi
    "kn": "kn",   # Kannada
    "bn": "bn",   # Bengali
    "en": "en",   # English
}

WHISPER_LANG_MAP = {
    "hi": "hi", "mr": "mr", "te": "te", "ta": "ta",
    "pa": "pa", "kn": "kn", "bn": "bn", "en": "en",
}


def transcribe_audio(audio_bytes: bytes, language: str = "hi") -> dict:
    """
    Convert voice message to text using Whisper.

    Args:
        audio_bytes: OGG/MP3/WAV bytes from Telegram
        language:    ISO 639-1 language code

    Returns:
        {"text": "...", "language": "...", "confidence": 0.9}
    """
    try:
        model = _get_whisper()

        # Write to temp file (Whisper needs file path)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        result = model.transcribe(
            tmp_path,
            language=WHISPER_LANG_MAP.get(language, "hi"),
            task="transcribe",
        )
        os.unlink(tmp_path)

        return {
            "text":     result["text"].strip(),
            "language": result.get("language", language),
            "segments": len(result.get("segments", [])),
        }

    except Exception as e:
        return {"error": str(e), "text": ""}


def text_to_speech(text: str, language: str = "hi") -> bytes:
    """
    Convert text to speech audio bytes using gTTS.

    Args:
        text:     Text to speak
        language: Language code

    Returns:
        MP3 bytes
    """
    try:
        lang = LANG_MAP.get(language, "hi")
        tts  = gTTS(text=text, lang=lang, slow=False)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tts.save(tmp.name)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()

        os.unlink(tmp_path)
        return audio_bytes

    except Exception as e:
        print(f"[TTS Error] {e}")
        return b""


def detect_language_from_text(text: str) -> str:
    """
    Simple heuristic to detect language from script.
    For production: use langdetect library.
    """
    # Devanagari (Hindi/Marathi)
    if any("\u0900" <= c <= "\u097F" for c in text):
        return "hi"
    # Telugu
    if any("\u0C00" <= c <= "\u0C7F" for c in text):
        return "te"
    # Tamil
    if any("\u0B80" <= c <= "\u0BFF" for c in text):
        return "ta"
    # Kannada
    if any("\u0C80" <= c <= "\u0CFF" for c in text):
        return "kn"
    # Bengali/Punjabi (Gurmukhi)
    if any("\u0A00" <= c <= "\u0A7F" for c in text):
        return "pa"
    return "en"
