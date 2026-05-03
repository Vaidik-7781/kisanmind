"""
Message formatter — ensures responses are clean for Telegram.
Handles voice response generation, message splitting for long texts.
"""

from tools.voice_tool import text_to_speech
from memory.farmer_profile import get_profile
import re


MAX_TELEGRAM_LENGTH = 4096
VOICE_TRIGGER_KEYWORDS = ["bolo", "sunao", "voice", "awaaz", "bol", "audio"]


def format_for_telegram(text: str) -> str:
    """
    Clean and format text for Telegram MarkdownV2.
    Returns standard Markdown (not V2) for simplicity.
    """
    if not text:
        return "⚠️ No response generated."

    # Ensure text isn't too long (Telegram limit 4096)
    if len(text) > MAX_TELEGRAM_LENGTH:
        text = text[:MAX_TELEGRAM_LENGTH - 100] + "\n\n_...message truncated_"

    return text


def split_long_message(text: str, max_len: int = 4096) -> list[str]:
    """Split long messages into chunks for Telegram."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    lines  = text.split("\n")
    chunk  = ""

    for line in lines:
        if len(chunk) + len(line) + 1 > max_len:
            chunks.append(chunk.strip())
            chunk = line + "\n"
        else:
            chunk += line + "\n"

    if chunk.strip():
        chunks.append(chunk.strip())

    return chunks


def should_respond_with_voice(telegram_id: int, user_message: str) -> bool:
    """
    Determine if we should send a voice response.
    True if: user sent voice OR explicitly requested voice OR user language is not English.
    """
    profile = get_profile(telegram_id)
    lang    = profile.get("language", "hi")

    # Non-English users often prefer voice
    if lang != "en":
        return True

    # Explicit voice request
    msg_lower = user_message.lower()
    if any(kw in msg_lower for kw in VOICE_TRIGGER_KEYWORDS):
        return True

    return False


def prepare_voice_response(text: str, telegram_id: int) -> bytes:
    """Convert response text to voice audio."""
    profile  = get_profile(telegram_id)
    lang     = profile.get("language", "hi")
    clean    = _strip_markdown(text)
    return text_to_speech(clean, language=lang)


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting for TTS."""
    text = re.sub(r"\*([^*]+)\*", r"\1", text)    # bold
    text = re.sub(r"_([^_]+)_",   r"\1", text)    # italic
    text = re.sub(r"`([^`]+)`",   r"\1", text)    # code
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # links
    text = re.sub(r"#{1,6}\s",   "",     text)    # headers
    return text.strip()


def format_escalation_message(analysis: dict) -> str:
    """Format message when confidence is low and human expert needed."""
    return (
        "⚠️ *Low confidence detection*\n\n"
        f"Detected: {analysis.get('issue_name', 'Unknown issue')}\n"
        f"Confidence: {int(analysis.get('confidence', 0) * 100)}%\n\n"
        "Please consult:\n"
        "🏢 *Your nearest KVK* (Krishi Vigyan Kendra)\n"
        "📞 *Kisan Call Centre:* 1800-180-1551 (Free)\n"
        "🌐 *ICAR:* icar.org.in\n\n"
        "_Always verify critical agricultural decisions with a local expert._"
    )
