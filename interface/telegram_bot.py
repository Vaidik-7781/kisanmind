"""
Telegram Bot — main interface handler.
Handles: text, photo, voice messages + all commands.
"""

import logging
from telegram import Update, Message
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode, ChatAction

from agents.orchestrator import route
from interface.message_formatter import (
    format_for_telegram,
    split_long_message,
    should_respond_with_voice,
    prepare_voice_response,
    format_escalation_message,
)
from config.settings import TELEGRAM_BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── Handlers ────────────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    msg       = update.message
    telegram_id = msg.from_user.id
    text      = msg.text or ""

    await msg.reply_chat_action(ChatAction.TYPING)

    result = route(telegram_id=telegram_id, message=text)
    await _send_response(msg, telegram_id, text, result)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle crop/soil photos for disease detection."""
    msg         = update.message
    telegram_id = msg.from_user.id
    caption     = msg.caption or ""

    await msg.reply_chat_action(ChatAction.TYPING)
    await msg.reply_text("🔍 Analysing your crop photo... please wait.")

    # Download largest photo size
    photo_file  = await msg.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()

    # Determine if soil or crop image
    image_type = "soil" if any(w in caption.lower() for w in ["soil", "mitti", "zameen"]) else "crop"

    result = route(
        telegram_id = telegram_id,
        message     = caption or "Analyse this crop image",
        image_bytes = bytes(image_bytes),
    )

    # Add escalation message if needed
    if result.get("needs_escalation"):
        result["response_text"] += "\n\n" + format_escalation_message({})

    await _send_response(msg, telegram_id, caption, result)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages — transcribe then process."""
    msg         = update.message
    telegram_id = msg.from_user.id

    await msg.reply_chat_action(ChatAction.TYPING)
    await msg.reply_text("🎤 Processing your voice message...")

    # Download voice
    voice_file  = await msg.voice.get_file()
    voice_bytes = await voice_file.download_as_bytearray()

    result = route(
        telegram_id = telegram_id,
        message     = "",
        voice_bytes = bytes(voice_bytes),
    )

    # Always send voice reply for voice inputs
    result["needs_voice"] = True
    await _send_response(msg, telegram_id, "", result)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads (e.g. land record PDFs)."""
    msg = update.message
    await msg.reply_text(
        "📄 Document received!\n\n"
        "Currently I can process:\n"
        "• 📸 Crop photos → disease detection\n"
        "• 🎤 Voice messages → any question\n\n"
        "For documents, please contact your local agriculture office."
    )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle shared location for weather/market localization."""
    msg         = update.message
    telegram_id = msg.from_user.id
    lat         = msg.location.latitude
    lon         = msg.location.longitude

    from memory.farmer_profile import set_location
    import requests
    from config.settings import OPENWEATHER_API_KEY, OPENWEATHER_URL

    try:
        resp = requests.get(
            f"{OPENWEATHER_URL}/weather",
            params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY},
            timeout=10
        )
        city = resp.json().get("name", f"{lat:.2f},{lon:.2f}")
    except Exception:
        city = f"{lat:.2f},{lon:.2f}"

    set_location(telegram_id, city, lat, lon)
    await msg.reply_text(
        f"✅ Location set to *{city}*\n\n"
        "Now you'll get:\n"
        "• 🌤️ Local weather forecasts\n"
        "• 💰 Nearby mandi prices\n"
        "• 🌾 Region-specific crop advice",
        parse_mode=ParseMode.MARKDOWN,
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler."""
    logger.error("Exception:", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "⚠️ Something went wrong. Please try again.\n"
            "If problem persists, contact: 1800-180-1551"
        )


# ─── Response sender ─────────────────────────────────────────────────────────

async def _send_response(
    msg: Message,
    telegram_id: int,
    user_text: str,
    result: dict,
):
    """Send text + optional voice response."""
    response_text = result.get("response_text", "⚠️ No response generated.")
    formatted     = format_for_telegram(response_text)
    chunks        = split_long_message(formatted)

    # Send text chunks
    for i, chunk in enumerate(chunks):
        try:
            await msg.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            # Fallback: send without markdown if parse error
            try:
                clean = chunk.replace("*", "").replace("_", "").replace("`", "")
                await msg.reply_text(clean)
            except Exception as e:
                logger.error(f"Failed to send message: {e}")

    # Send voice response if requested
    if result.get("needs_voice") or should_respond_with_voice(telegram_id, user_text):
        try:
            await msg.reply_chat_action(ChatAction.RECORD_VOICE)
            voice_audio = prepare_voice_response(response_text, telegram_id)
            if voice_audio:
                await msg.reply_voice(voice=voice_audio)
        except Exception as e:
            logger.warning(f"Voice response failed: {e}")


# ─── App setup ───────────────────────────────────────────────────────────────

def create_app() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN not set in .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Photos
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Voice
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Documents
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Location
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    # Commands (routed through text handler via orchestrator)
    for cmd in ["start", "help", "weather", "price", "plan", "schemes",
                "setlocation", "addcrop", "setlang", "profile", "reset"]:
        app.add_handler(CommandHandler(cmd, handle_text))

    # Error handler
    app.add_error_handler(error_handler)

    return app
