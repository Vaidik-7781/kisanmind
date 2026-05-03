"""
Crop Planning Agent — recommends what to grow next season
based on soil, location, season, water availability, and profit potential.
"""

from openai import OpenAI
from tools.rag_tool import search_knowledge
from tools.weather_tool import get_current_weather
from memory.farmer_profile import get_profile
from config.settings import GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL
from datetime import datetime

client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)


# Crop profit + water requirement reference table
CROP_REFERENCE = {
    "wheat":     {"season": "rabi",   "water": "medium", "profit_acre": 20000, "duration_days": 120},
    "rice":      {"season": "kharif", "water": "high",   "profit_acre": 18000, "duration_days": 150},
    "maize":     {"season": "kharif", "water": "medium", "profit_acre": 16000, "duration_days": 90},
    "soybean":   {"season": "kharif", "water": "low",    "profit_acre": 22000, "duration_days": 100},
    "mustard":   {"season": "rabi",   "water": "low",    "profit_acre": 19000, "duration_days": 110},
    "tomato":    {"season": "both",   "water": "medium", "profit_acre": 45000, "duration_days": 110},
    "onion":     {"season": "both",   "water": "medium", "profit_acre": 38000, "duration_days": 120},
    "potato":    {"season": "rabi",   "water": "medium", "profit_acre": 35000, "duration_days": 90},
    "cotton":    {"season": "kharif", "water": "medium", "profit_acre": 28000, "duration_days": 180},
    "sugarcane": {"season": "both",   "water": "high",   "profit_acre": 55000, "duration_days": 365},
    "groundnut": {"season": "kharif", "water": "low",    "profit_acre": 25000, "duration_days": 120},
    "chickpea":  {"season": "rabi",   "water": "low",    "profit_acre": 18000, "duration_days": 100},
    "moong":     {"season": "kharif", "water": "low",    "profit_acre": 15000, "duration_days": 70},
}


def run(telegram_id: int, user_request: str = "") -> dict:
    """
    Generate crop planning recommendations.

    Returns:
        {"recommendations": [...], "response_text": "..."}
    """
    profile  = get_profile(telegram_id)
    season   = _get_current_season()
    soil     = profile.get("soil_type", "unknown")
    acres    = profile.get("land_acres", 1)
    loc      = profile.get("location")
    history  = profile.get("crop_history", [])
    current  = profile.get("current_crops", [])

    # Fetch weather for the location
    weather_summary = ""
    if loc:
        w = get_current_weather(lat=loc["lat"], lon=loc["lon"])
        if "error" not in w:
            weather_summary = f"Current temp: {w['temperature']}°C, humidity: {w['humidity']}%"

    # Filter suitable crops for this season
    suitable = _get_suitable_crops(season, soil, history, current)

    # RAG lookup for crop planning
    rag_docs = search_knowledge(
        f"best crop {season} season {soil} soil India",
        n_results=3,
        category="crop_planning"
    )
    rag_text = "\n".join(r["text"] for r in rag_docs if r.get("score", 0) > 0.3)

    # LLM for personalized recommendation
    prompt = f"""
Farmer needs crop planning advice for upcoming season.

Season: {season}
Soil type: {soil}
Land: {acres} acres
Location: {loc.get('city') if loc else 'North India'}
Water availability: medium (assume unless stated)
{f'Weather: {weather_summary}' if weather_summary else ''}
{f'Previous crops: {", ".join(c["name"] for c in (history[-3:] if history else []))}' if history else ''}
{f'Current crops: {", ".join(c["name"] for c in current)}' if current else ''}
Additional request: {user_request if user_request else 'General recommendation'}

Suitable crops data: {str(suitable[:5])}
Knowledge base: {rag_text[:500]}

Provide TOP 3 crop recommendations with:
1. Why this crop suits the farmer
2. Expected profit per acre (₹)
3. Water requirement
4. Key success tips (2-3 points)
5. Best local variety name

Format clearly with emojis. Keep concise (Telegram-friendly).
"""

    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert Indian agricultural advisor. Give practical, profitable crop advice for Indian farmers."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=700,
            temperature=0.4,
        )
        llm_response = resp.choices[0].message.content.strip()
    except Exception as e:
        llm_response = _fallback_recommendations(suitable, season, acres)

    header = f"🌱 *Crop Planning — {season.title()} Season*\n\n"
    return {
        "recommendations": suitable[:3],
        "response_text":   header + llm_response,
    }


def _get_suitable_crops(season: str, soil: str, history: list, current: list) -> list[dict]:
    """Filter and rank crops by suitability."""
    current_names = {c["name"].lower() for c in current}
    history_names = {c["name"].lower() if isinstance(c, dict) else c.lower() for c in history[-2:]}

    results = []
    for crop, info in CROP_REFERENCE.items():
        if crop in current_names:
            continue
        if crop in history_names:
            continue  # Avoid repeating last 2 crops

        season_match = info["season"] in (season, "both")
        soil_match   = _soil_match(soil, crop)
        score        = (2 if season_match else 0) + (1 if soil_match else 0)

        results.append({
            "crop":         crop,
            "season_match": season_match,
            "soil_match":   soil_match,
            "score":        score,
            **info,
        })

    return sorted(results, key=lambda x: (-x["score"], -x["profit_acre"]))


def _soil_match(soil: str, crop: str) -> bool:
    soil_crop_map = {
        "black":  {"cotton", "soybean", "wheat", "jowar", "sunflower"},
        "red":    {"groundnut", "ragi", "maize", "cotton", "soybean"},
        "loamy":  {"wheat", "rice", "maize", "potato", "sugarcane", "onion", "tomato"},
        "sandy":  {"groundnut", "moong", "watermelon", "potato"},
        "clay":   {"rice", "sugarcane", "wheat"},
    }
    matched = soil_crop_map.get(soil.lower(), set())
    return crop in matched if matched else True  # Unknown soil → allow all


def _get_current_season() -> str:
    month = datetime.now().month
    if month in (6, 7, 8, 9, 10):
        return "kharif"
    elif month in (11, 12, 1, 2, 3):
        return "rabi"
    else:
        return "zaid"  # Summer crop season


def _fallback_recommendations(suitable: list, season: str, acres: float) -> str:
    top3 = suitable[:3]
    lines = [f"*Top crops for {season.title()} season:*\n"]
    for i, c in enumerate(top3, 1):
        lines.append(
            f"{i}. *{c['crop'].title()}*\n"
            f"   💰 Expected profit: ₹{int(c['profit_acre'] * acres):,}\n"
            f"   💧 Water: {c['water'].title()}\n"
            f"   📅 Duration: {c['duration_days']} days\n"
        )
    return "\n".join(lines)
