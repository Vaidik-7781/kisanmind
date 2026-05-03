"""
Climate Agent — weather data + farm-specific actionable alerts.
"""

from tools.weather_tool import get_current_weather
from memory.farmer_profile import get_profile


def run(telegram_id: int, city: str = None) -> dict:
    """
    Get weather data and generate farm-specific advice.

    Returns:
        {"weather": {...}, "response_text": "...", "alerts": [...]}
    """
    profile = get_profile(telegram_id)
    loc     = profile.get("location")
    crops   = profile.get("current_crops", [])
    lang    = profile.get("language", "hi")

    # Determine location
    if city:
        weather = get_current_weather(city=city)
    elif loc:
        weather = get_current_weather(lat=loc["lat"], lon=loc["lon"])
    else:
        return {
            "weather":       None,
            "response_text": "📍 Please share your location first so I can give accurate weather info.\nSend: /setlocation [your city name]",
            "alerts":        [],
        }

    if "error" in weather:
        return {
            "weather":       weather,
            "response_text": f"❌ Weather data unavailable: {weather['error']}",
            "alerts":        [],
        }

    crop_names = [c["name"] for c in crops]
    advice     = _generate_crop_specific_advice(weather, crop_names)
    response   = _format_response(weather, advice, lang)

    return {
        "weather":       weather,
        "response_text": response,
        "alerts":        weather.get("alerts", []),
    }


def _generate_crop_specific_advice(weather: dict, crops: list) -> list[str]:
    """Generate crop-specific advice based on weather conditions."""
    advice    = []
    temp      = weather.get("temperature", 25)
    humidity  = weather.get("humidity", 60)
    forecast  = weather.get("forecast_5d", [])

    rain_days = [d for d in forecast if d.get("rain_mm", 0) > 5]

    for crop in crops:
        crop = crop.lower()

        if crop == "wheat":
            if temp > 35:
                advice.append("🌾 WHEAT: High temp reduces grain filling. Irrigate immediately if possible.")
            if humidity > 80:
                advice.append("🌾 WHEAT: High humidity = rust risk. Inspect leaves for orange/yellow spots.")
            if rain_days:
                advice.append(f"🌾 WHEAT: Rain expected. Delay fungicide spray to {rain_days[0]['date']}.")

        elif crop in ("tomato", "potato", "brinjal"):
            if humidity > 85:
                advice.append(f"🍅 {crop.upper()}: High humidity = blight risk. Apply preventive copper spray.")
            if temp > 38:
                advice.append(f"🍅 {crop.upper()}: Heat stress causes flower drop. Shade net recommended.")

        elif crop == "rice":
            if temp < 15:
                advice.append("🌾 RICE: Cold stress risk. Maintain 2-3 inch water in field for insulation.")

        elif crop in ("onion", "garlic"):
            if rain_days:
                advice.append("🧅 ONION: Rain coming. Ensure field drainage to prevent bulb rot.")

        elif crop == "cotton":
            if humidity > 80:
                advice.append("🌿 COTTON: High humidity favors boll rot. Increase plant spacing/pruning.")

    if not advice:
        if rain_days:
            advice.append("🌧️ Rain expected. Good time to plan field drainage and hold off on irrigation.")
        elif temp > 38:
            advice.append("🌡️ Hot days ahead. Irrigate early morning before 7 AM.")
        else:
            advice.append("✅ Weather conditions are generally favorable for farming this week.")

    return advice


def _format_response(weather: dict, advice: list, lang: str) -> str:
    forecast = weather.get("forecast_5d", [])
    alerts   = weather.get("alerts", [])

    lines = [
        f"🌤️ *Weather — {weather.get('city', 'Your Location')}*",
        f"🌡️ Temp: *{weather.get('temperature')}°C* (feels {weather.get('feels_like')}°C)",
        f"💧 Humidity: *{weather.get('humidity')}%*",
        f"💨 Wind: *{weather.get('wind_speed')} m/s*",
        f"☁️ Condition: *{weather.get('description', '').title()}*",
        f"🌧️ Rainfall (last 1hr): *{weather.get('rainfall_1h', 0)} mm*",
        "",
        "*5-Day Forecast:*",
    ]

    for day in forecast:
        rain_str = f"🌧️{day['rain_mm']}mm" if day["rain_mm"] > 0 else "☀️"
        lines.append(f"  {day['date']}: {day['min']}–{day['max']}°C {rain_str}")

    if alerts:
        lines += ["", "⚠️ *Farm Alerts:*"]
        lines += [f"  {a}" for a in alerts]

    if advice:
        lines += ["", "🌾 *Crop Advice:*"]
        lines += [f"  {a}" for a in advice]

    return "\n".join(lines)
