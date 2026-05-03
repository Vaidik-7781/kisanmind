"""
Orchestrator Agent — master router.
Classifies intent and dispatches to the right sub-agent.
Uses Groq LLM for classification + rule-based fallback.
"""

import json
import re
from openai import OpenAI
from config.settings import GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL
from memory.farmer_profile import get_profile

client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)


INTENT_PROMPT = """
Classify the farmer's message into ONE of these intents.
Respond ONLY with a JSON object, no markdown, no explanation.

Intents:
- disease_detection: asking about crop disease, pest, image analysis
- weather: asking about rain, temperature, forecast, weather alerts
- market_price: asking about mandi price, selling price, rate, crop rate
- crop_planning: asking what to grow, crop recommendation, next season, crop rotation
- finance_subsidy: asking about PM-KISAN, PMFBY, KCC, insurance, loan, subsidy, government scheme
- advisory_general: general farming advice, fertilizer, irrigation, pesticide questions
- profile_update: user wants to update their info (location, crop, land, language)
- greeting: hello, hi, help, start, what can you do

Response format:
{"intent": "...", "commodity": "wheat or null", "confidence": 0.9}
"""


INTENT_KEYWORDS = {
    "disease_detection": ["disease", "bimari", "rog", "pest", "keeda", "pattiyan", "leaves", "spots", "fungus", "blight", "rust", "wilting"],
    "weather":           ["weather", "mausam", "rain", "baarish", "temperature", "garmi", "sardi", "barsat", "forecast"],
    "market_price":      ["price", "rate", "bhav", "mandi", "bazar", "sell", "becho", "kharido", "market"],
    "crop_planning":     ["crop", "kya ugaun", "season", "plant", "fasal", "sow", "ugao", "recommend", "next crop", "rotation"],
    "finance_subsidy":   ["kisan", "subsidy", "insurance", "bima", "loan", "kcc", "credit", "pm-kisan", "scheme", "yojana", "sarkar"],
    "greeting":          ["hi", "hello", "help", "start", "namaste", "jai kisan", "kya kar sakte"],
}


def classify_intent(message: str, has_image: bool = False, has_voice: bool = False) -> dict:
    """
    Classify user intent from text message.

    Returns:
        {"intent": "...", "commodity": "...", "confidence": 0.9}
    """
    if has_image:
        return {"intent": "disease_detection", "commodity": None, "confidence": 0.95}

    # Rule-based fast path
    msg_lower = message.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            commodity = _extract_commodity(msg_lower)
            return {"intent": intent, "commodity": commodity, "confidence": 0.8}

    # LLM-based classification
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user",   "content": message},
            ],
            max_tokens=80,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        result = json.loads(raw)
        return result
    except Exception:
        return {"intent": "advisory_general", "commodity": None, "confidence": 0.5}


def route(
    telegram_id: int,
    message: str,
    image_bytes: bytes = None,
    voice_bytes: bytes = None,
) -> dict:
    """
    Main orchestration function.
    Takes user input → returns agent response.

    Returns:
        {
          "intent":        "...",
          "response_text": "...",
          "agent_used":    "...",
          "needs_voice":   bool,
          "needs_escalation": bool,
        }
    """
    # ── Transcribe voice if present ──────────────────────────────────────────
    if voice_bytes:
        from tools.voice_tool import transcribe_audio
        from memory.farmer_profile import get_profile as gp
        lang = gp(telegram_id).get("language", "hi")
        transcription = transcribe_audio(voice_bytes, language=lang)
        message = transcription.get("text", message) or message

    # ── Handle commands ───────────────────────────────────────────────────────
    if message.startswith("/"):
        return _handle_command(telegram_id, message)

    # ── Classify intent ───────────────────────────────────────────────────────
    intent_result = classify_intent(message, has_image=bool(image_bytes))
    intent        = intent_result.get("intent", "advisory_general")
    commodity     = intent_result.get("commodity")

    # ── Route to agent ────────────────────────────────────────────────────────
    result = {"intent": intent, "agent_used": intent, "needs_voice": bool(voice_bytes), "needs_escalation": False}

    if intent == "disease_detection" and image_bytes:
        from agents import vision_agent
        agent_result = vision_agent.run(image_bytes, telegram_id)
        result["response_text"]    = agent_result["response_text"]
        result["needs_escalation"] = agent_result.get("needs_escalation", False)

    elif intent == "disease_detection" and not image_bytes:
        result["response_text"] = (
            "📸 Please send a *photo of your crop* so I can identify the disease.\n\n"
            "Tips for a good photo:\n"
            "• Close-up of affected leaves\n"
            "• Clear lighting\n"
            "• Show both top and bottom of leaf if possible"
        )

    elif intent == "weather":
        from agents import climate_agent
        agent_result = climate_agent.run(telegram_id)
        result["response_text"] = agent_result["response_text"]

    elif intent == "market_price":
        from agents import market_agent
        agent_result = market_agent.run(telegram_id, commodity=commodity)
        result["response_text"] = agent_result["response_text"]

    elif intent == "crop_planning":
        from agents import crop_plan_agent
        agent_result = crop_plan_agent.run(telegram_id, user_request=message)
        result["response_text"] = agent_result["response_text"]

    elif intent == "finance_subsidy":
        from agents import finance_agent
        agent_result = finance_agent.run(telegram_id, query=message)
        result["response_text"] = agent_result["response_text"]

    elif intent == "greeting":
        result["response_text"] = _greeting_message(telegram_id)

    else:  # advisory_general — default
        from agents import advisory_agent
        agent_result = advisory_agent.run(telegram_id, message)
        result["response_text"] = agent_result["response_text"]

    return result


def _handle_command(telegram_id: int, command: str) -> dict:
    """Handle slash commands."""
    parts = command.strip().split(maxsplit=1)
    cmd   = parts[0].lower()
    arg   = parts[1] if len(parts) > 1 else ""

    if cmd == "/start":
        return {"intent": "greeting", "response_text": _greeting_message(telegram_id), "agent_used": "system", "needs_voice": False, "needs_escalation": False}

    elif cmd == "/help":
        return {"intent": "help", "response_text": _help_message(), "agent_used": "system", "needs_voice": False, "needs_escalation": False}

    elif cmd == "/price":
        from agents import market_agent
        result = market_agent.run(telegram_id, commodity=arg or None)
        return {"intent": "market_price", "response_text": result["response_text"], "agent_used": "market_agent", "needs_voice": False, "needs_escalation": False}

    elif cmd == "/weather":
        from agents import climate_agent
        result = climate_agent.run(telegram_id, city=arg or None)
        return {"intent": "weather", "response_text": result["response_text"], "agent_used": "climate_agent", "needs_voice": False, "needs_escalation": False}

    elif cmd == "/plan":
        from agents import crop_plan_agent
        result = crop_plan_agent.run(telegram_id, user_request=arg)
        return {"intent": "crop_planning", "response_text": result["response_text"], "agent_used": "crop_agent", "needs_voice": False, "needs_escalation": False}

    elif cmd == "/schemes":
        from agents.finance_agent import get_all_schemes_summary
        return {"intent": "finance_subsidy", "response_text": get_all_schemes_summary(), "agent_used": "finance_agent", "needs_voice": False, "needs_escalation": False}

    elif cmd == "/setlocation":
        return _set_location_handler(telegram_id, arg)

    elif cmd == "/addcrop":
        return _add_crop_handler(telegram_id, arg)

    elif cmd == "/setlang":
        return _set_lang_handler(telegram_id, arg)

    elif cmd == "/profile":
        return {"intent": "profile", "response_text": _format_profile(telegram_id), "agent_used": "system", "needs_voice": False, "needs_escalation": False}

    elif cmd == "/reset":
        from memory.conversation import clear_history
        clear_history(telegram_id)
        return {"intent": "reset", "response_text": "✅ Conversation history cleared.", "agent_used": "system", "needs_voice": False, "needs_escalation": False}

    return {"intent": "unknown", "response_text": f"Unknown command: {cmd}\nSend /help for available commands.", "agent_used": "system", "needs_voice": False, "needs_escalation": False}


def _set_location_handler(telegram_id: int, city: str) -> dict:
    from memory.farmer_profile import set_location
    import requests
    from config.settings import OPENWEATHER_API_KEY, OPENWEATHER_URL

    if not city:
        return {"intent": "profile_update", "response_text": "Usage: /setlocation [city name]\nExample: /setlocation Varanasi", "agent_used": "system", "needs_voice": False, "needs_escalation": False}

    try:
        resp = requests.get(f"{OPENWEATHER_URL}/weather", params={"q": city, "appid": OPENWEATHER_API_KEY}, timeout=10)
        data = resp.json()
        lat  = data["coord"]["lat"]
        lon  = data["coord"]["lon"]
        name = data["name"]
        set_location(telegram_id, name, lat, lon)
        msg = f"✅ Location set to *{name}* (lat: {lat}, lon: {lon})\nWeather and market data will now be localized."
    except Exception:
        msg = f"⚠️ Could not verify city '{city}'. Try a well-known city name.\nLocation saved as-is."

    return {"intent": "profile_update", "response_text": msg, "agent_used": "system", "needs_voice": False, "needs_escalation": False}


def _add_crop_handler(telegram_id: int, crop: str) -> dict:
    from memory.farmer_profile import add_crop
    if not crop:
        return {"intent": "profile_update", "response_text": "Usage: /addcrop [crop name]\nExample: /addcrop wheat", "agent_used": "system", "needs_voice": False, "needs_escalation": False}
    add_crop(telegram_id, crop.strip().lower())
    return {"intent": "profile_update", "response_text": f"✅ Added *{crop.title()}* to your crops.\nI'll now give you personalized advice for this crop.", "agent_used": "system", "needs_voice": False, "needs_escalation": False}


def _set_lang_handler(telegram_id: int, lang: str) -> dict:
    from memory.farmer_profile import update_profile
    supported = {"hi": "Hindi", "en": "English", "mr": "Marathi", "te": "Telugu", "ta": "Tamil", "pa": "Punjabi", "kn": "Kannada", "bn": "Bengali"}
    if lang not in supported:
        return {"intent": "profile_update", "response_text": f"Supported languages:\n" + "\n".join(f"  /setlang {k} → {v}" for k, v in supported.items()), "agent_used": "system", "needs_voice": False, "needs_escalation": False}
    update_profile(telegram_id, {"language": lang})
    return {"intent": "profile_update", "response_text": f"✅ Language set to *{supported[lang]}*.", "agent_used": "system", "needs_voice": False, "needs_escalation": False}


def _format_profile(telegram_id: int) -> str:
    profile = get_profile(telegram_id)
    loc     = profile.get("location")
    crops   = profile.get("current_crops", [])
    lines   = [
        "👤 *Your Profile*",
        f"Name: {profile.get('name', 'Not set')}",
        f"Location: {loc.get('city', 'Not set') if loc else 'Not set'}",
        f"Land: {profile.get('land_acres', 'Not set')} acres",
        f"Soil: {profile.get('soil_type', 'Not set')}",
        f"Language: {profile.get('language', 'hi')}",
        f"Crops: {', '.join(c['name'] for c in crops) if crops else 'None added'}",
    ]
    return "\n".join(lines)


def _greeting_message(telegram_id: int) -> str:
    profile = get_profile(telegram_id)
    name    = profile.get("name", "Kisan ji")
    return (
        f"🌾 *Namaste {name}!*\n\n"
        "I am *KisanMind* — your AI farming assistant.\n\n"
        "I can help you with:\n"
        "📸 *Crop disease* — Send a photo\n"
        "🌤️ *Weather alerts* — /weather\n"
        "💰 *Mandi prices* — /price wheat\n"
        "🌱 *Crop planning* — /plan\n"
        "💸 *Govt schemes* — /schemes\n"
        "💬 *Any farming question* — Just ask!\n\n"
        "📍 Set your location: /setlocation Varanasi\n"
        "🌿 Add your crop: /addcrop wheat\n\n"
        "📞 *Kisan Helpline: 1800-180-1551* (Free)"
    )


def _help_message() -> str:
    return (
        "🌾 *KisanMind Commands*\n\n"
        "/start — Welcome message\n"
        "/weather — Today's weather + farm alerts\n"
        "/price [crop] — Mandi price + forecast\n"
        "/plan — Crop planning for this season\n"
        "/schemes — Govt subsidies + schemes\n"
        "/setlocation [city] — Set your location\n"
        "/addcrop [name] — Add crop you're growing\n"
        "/setlang [hi/en/mr/te] — Change language\n"
        "/profile — View your profile\n"
        "/reset — Clear conversation history\n\n"
        "📸 *Send a photo* → Disease detection\n"
        "🎤 *Send a voice note* → Ask in your language\n\n"
        "📞 Helpline: *1800-180-1551* (Free)"
    )


def _extract_commodity(text: str) -> str | None:
    commodities = [
        "wheat", "rice", "maize", "onion", "tomato", "potato", "soybean",
        "cotton", "sugarcane", "mustard", "groundnut", "chickpea", "moong",
        "gehu", "chawal", "pyaaz", "aloo", "tamatar", "sarson",
    ]
    # Hindi→English map
    hindi_map = {"gehu": "wheat", "chawal": "rice", "pyaaz": "onion", "aloo": "potato", "tamatar": "tomato", "sarson": "mustard"}
    for c in commodities:
        if c in text:
            return hindi_map.get(c, c)
    return None
