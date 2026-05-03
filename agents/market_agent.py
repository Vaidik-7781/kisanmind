"""
Market Agent — mandi prices + price forecasting + optimal sell window.
"""

from tools.mandi_tool import get_mandi_prices, get_price_trend
from models.price_forecaster import forecast_price
from memory.farmer_profile import get_profile


def run(telegram_id: int, commodity: str = None) -> dict:
    """
    Get mandi prices + price forecast for farmer's crops.

    Returns:
        {"prices": {...}, "forecast": {...}, "response_text": "..."}
    """
    profile = get_profile(telegram_id)
    crops   = profile.get("current_crops", [])
    loc     = profile.get("location")
    state   = loc.get("city", None) if loc else None

    # Determine commodity to check
    if not commodity:
        if crops:
            commodity = crops[0]["name"]  # default to first crop
        else:
            return {
                "prices":        None,
                "response_text": "📦 Please tell me which crop price to check.\nExample: /price wheat\nOr add your crop: /addcrop wheat",
            }

    # ── Fetch prices ─────────────────────────────────────────────────────────
    prices   = get_mandi_prices(commodity, state=state)
    trend    = get_price_trend(commodity, days=7)
    forecast = {}

    current_price = prices.get("avg_price", 0)
    if current_price > 0:
        forecast = forecast_price(commodity, current_price, days_ahead=14)

    response = _format_response(commodity, prices, forecast, trend)

    return {"prices": prices, "forecast": forecast, "trend": trend, "response_text": response}


def run_multi_crop(telegram_id: int) -> dict:
    """Get price summary for all of farmer's current crops."""
    profile = get_profile(telegram_id)
    crops   = profile.get("current_crops", [])

    if not crops:
        return {"response_text": "No crops registered. Add crops: /addcrop wheat"}

    responses = []
    for crop in crops[:3]:  # Limit to 3 crops
        result = run(telegram_id, commodity=crop["name"])
        responses.append(result["response_text"])

    return {"response_text": "\n\n─────────────\n\n".join(responses)}


def _format_response(commodity: str, prices: dict, forecast: dict, trend: list) -> str:
    if "error" in prices and not prices.get("avg_price"):
        return f"❌ Could not fetch prices for {commodity}. Try again later."

    lines = [
        f"💰 *{commodity.title()} — Market Price*",
        f"📅 Date: {prices.get('date', 'Today')}",
        f"",
        f"📊 *Current Prices (₹/quintal)*",
        f"  Average:  ₹{prices.get('avg_price', 'N/A')}",
        f"  Minimum:  ₹{prices.get('min_price', 'N/A')}",
        f"  Maximum:  ₹{prices.get('max_price', 'N/A')}",
    ]

    # Top markets
    markets = prices.get("markets", [])[:5]
    if markets:
        lines += ["", "*Top Markets:*"]
        for m in markets:
            modal = m.get("modal_price") or m.get("Modal_x0020_Price", "N/A")
            name  = m.get("market") or m.get("Market", "N/A")
            lines.append(f"  • {name}: ₹{modal}")

    # 7-day price trend
    if trend:
        prices_7d = [t["price"] for t in trend]
        trend_dir = "📈 Rising" if prices_7d[-1] > prices_7d[0] else "📉 Falling"
        lines += ["", f"*7-Day Trend:* {trend_dir}"]

    # Forecast
    if forecast and not forecast.get("error"):
        lines += [
            "",
            f"*14-Day Forecast:*",
            f"  Trend: {forecast.get('trend', 'N/A').upper()}",
            f"  Best sell day: {forecast.get('best_sell_day', 'N/A')}",
            f"  Expected price: ₹{forecast.get('best_price', 'N/A')}/quintal",
            "",
            f"💡 *Recommendation:*",
            f"  {forecast.get('recommendation', prices.get('recommendation', ''))}",
        ]
    else:
        rec = prices.get("recommendation", "")
        if rec:
            lines += ["", f"💡 {rec}"]

    if prices.get("note"):
        lines += ["", f"ℹ️ _{prices['note']}_"]

    return "\n".join(lines)
