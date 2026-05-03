"""
Weather tool — OpenWeatherMap free tier.
1000 calls/day free. No credit card needed.
"""

import requests
from config.settings import OPENWEATHER_API_KEY, OPENWEATHER_URL


def get_current_weather(city: str = None, lat: float = None, lon: float = None) -> dict:
    """
    Returns current weather + 5-day forecast for a location.
    Pass either city name OR lat/lon.
    """
    if not OPENWEATHER_API_KEY:
        return {"error": "OPENWEATHER_API_KEY not set"}

    # ── Current weather ──────────────────────────────────────
    if lat and lon:
        params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "en"}
    else:
        params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "en"}

    try:
        curr_resp = requests.get(f"{OPENWEATHER_URL}/weather", params=params, timeout=10)
        curr_resp.raise_for_status()
        curr = curr_resp.json()

        # ── 5-day forecast ───────────────────────────────────
        fore_resp = requests.get(f"{OPENWEATHER_URL}/forecast", params=params, timeout=10)
        fore_resp.raise_for_status()
        fore = fore_resp.json()

        # Summarise forecast into daily buckets
        daily = _summarise_forecast(fore)

        return {
            "city":        curr.get("name", city or f"{lat},{lon}"),
            "temperature": curr["main"]["temp"],
            "feels_like":  curr["main"]["feels_like"],
            "humidity":    curr["main"]["humidity"],
            "description": curr["weather"][0]["description"],
            "wind_speed":  curr["wind"]["speed"],
            "rainfall_1h": curr.get("rain", {}).get("1h", 0),
            "forecast_5d": daily,
            "alerts":      _generate_farm_alerts(curr, daily),
        }

    except requests.RequestException as e:
        return {"error": str(e)}


def _summarise_forecast(fore_data: dict) -> list[dict]:
    """Collapse 3-hour forecast into daily summaries."""
    from collections import defaultdict
    days = defaultdict(lambda: {"temps": [], "rain": 0, "descriptions": []})

    for item in fore_data.get("list", []):
        date = item["dt_txt"].split(" ")[0]
        days[date]["temps"].append(item["main"]["temp"])
        days[date]["rain"] += item.get("rain", {}).get("3h", 0)
        days[date]["descriptions"].append(item["weather"][0]["main"])

    result = []
    for date, data in sorted(days.items())[:5]:
        result.append({
            "date":    date,
            "min":     round(min(data["temps"]), 1),
            "max":     round(max(data["temps"]), 1),
            "rain_mm": round(data["rain"], 1),
            "condition": max(set(data["descriptions"]), key=data["descriptions"].count),
        })
    return result


def _generate_farm_alerts(current: dict, forecast: list) -> list[str]:
    """Generate actionable farm alerts from weather data."""
    alerts = []

    humidity = current["main"]["humidity"]
    temp     = current["main"]["temp"]

    if humidity > 85:
        alerts.append("⚠️ HIGH HUMIDITY: Risk of fungal disease. Avoid irrigation today.")
    if temp > 40:
        alerts.append("🌡️ HEATWAVE: Irrigate early morning or evening only.")
    if temp < 5:
        alerts.append("❄️ FROST RISK: Cover sensitive crops tonight.")

    for day in forecast:
        if day["rain_mm"] > 20:
            alerts.append(f"🌧️ HEAVY RAIN expected on {day['date']} ({day['rain_mm']}mm). Delay sowing/spraying.")
        if day["rain_mm"] > 0 and day["rain_mm"] <= 20:
            alerts.append(f"🌦️ Light rain on {day['date']} ({day['rain_mm']}mm). Good for soil moisture.")

    return alerts
