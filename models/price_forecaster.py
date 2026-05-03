"""
Price forecaster — Prophet time-series model for mandi price prediction.
Falls back to ARIMA-style heuristic if Prophet not installed.
"""

from datetime import datetime, timedelta


def forecast_price(commodity: str, current_price: float, days_ahead: int = 14) -> dict:
    """
    Predict commodity price for next N days.
    Uses Prophet if available, else statistical heuristic.

    Returns:
        {
          "commodity": ...,
          "current_price": ...,
          "forecast": [{date, price, lower, upper}],
          "trend": "rising / falling / stable",
          "best_sell_day": "YYYY-MM-DD",
          "recommendation": "..."
        }
    """
    try:
        return _prophet_forecast(commodity, current_price, days_ahead)
    except ImportError:
        return _heuristic_forecast(commodity, current_price, days_ahead)
    except Exception as e:
        return _heuristic_forecast(commodity, current_price, days_ahead)


def _prophet_forecast(commodity: str, current_price: float, days_ahead: int) -> dict:
    """Prophet-based forecast using synthetic historical data + seasonal patterns."""
    from prophet import Prophet
    import pandas as pd
    import numpy as np

    # Build synthetic historical dataset (90 days)
    # In production: replace with real AGMARKNET historical data
    dates  = [datetime.now() - timedelta(days=i) for i in range(90, 0, -1)]
    prices = _generate_historical(commodity, current_price, 90)

    df = pd.DataFrame({"ds": dates, "y": prices})

    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=0.3,
        seasonality_prior_scale=10,
    )
    model.fit(df)

    future    = model.make_future_dataframe(periods=days_ahead)
    forecast  = model.predict(future)
    future_fc = forecast.tail(days_ahead)

    result_fc = []
    best_price = 0
    best_day   = None

    for _, row in future_fc.iterrows():
        entry = {
            "date":  row["ds"].strftime("%Y-%m-%d"),
            "price": round(row["yhat"], 2),
            "lower": round(row["yhat_lower"], 2),
            "upper": round(row["yhat_upper"], 2),
        }
        result_fc.append(entry)
        if entry["price"] > best_price:
            best_price = entry["price"]
            best_day   = entry["date"]

    trend = _detect_trend(result_fc)

    return {
        "commodity":     commodity,
        "current_price": current_price,
        "forecast":      result_fc,
        "trend":         trend,
        "best_sell_day": best_day,
        "best_price":    best_price,
        "recommendation": _sell_recommendation(trend, current_price, best_price, best_day),
    }


def _heuristic_forecast(commodity: str, current_price: float, days_ahead: int) -> dict:
    """Statistical heuristic when Prophet not available."""
    import math, random
    random.seed(hash(commodity) % 1000)

    seasonal_factors = _get_seasonal_factors(commodity)
    result_fc = []
    price     = current_price

    for i in range(1, days_ahead + 1):
        d       = (datetime.now() + timedelta(days=i))
        doy     = d.timetuple().tm_yday
        season  = seasonal_factors[doy % len(seasonal_factors)]
        noise   = random.uniform(-0.02, 0.02)
        price   = price * (1 + season + noise)
        result_fc.append({
            "date":  d.strftime("%Y-%m-%d"),
            "price": round(price, 2),
            "lower": round(price * 0.95, 2),
            "upper": round(price * 1.05, 2),
        })

    best = max(result_fc, key=lambda x: x["price"])
    trend = _detect_trend(result_fc)

    return {
        "commodity":      commodity,
        "current_price":  current_price,
        "forecast":       result_fc,
        "trend":          trend,
        "best_sell_day":  best["date"],
        "best_price":     best["price"],
        "recommendation": _sell_recommendation(trend, current_price, best["price"], best["date"]),
    }


def _detect_trend(forecast: list) -> str:
    if len(forecast) < 2:
        return "stable"
    first = forecast[0]["price"]
    last  = forecast[-1]["price"]
    diff  = (last - first) / first
    if diff > 0.03:
        return "rising"
    if diff < -0.03:
        return "falling"
    return "stable"


def _sell_recommendation(trend: str, current: float, best: float, best_day: str) -> str:
    gain = round((best - current) / current * 100, 1) if current else 0
    if trend == "rising" and gain > 5:
        return (f"📈 WAIT to sell. Prices expected to rise. Best day: {best_day} "
                f"(estimated ₹{best}/quintal, +{gain}% gain).")
    if trend == "falling":
        return "📉 SELL NOW. Prices are trending downward. Don't wait."
    return f"📊 Prices stable. Sell within next 3 days at current price (₹{current}/quintal)."


def _get_seasonal_factors(commodity: str) -> list:
    """Commodity-specific seasonal price drift per day (fraction)."""
    factors = {
        "onion":    [0.001] * 180 + [-0.001] * 185,
        "tomato":   [0.002, 0.002, -0.001, -0.001] * 91,
        "wheat":    [-0.0005] * 120 + [0.001] * 245,
        "potato":   [0.0008] * 200 + [-0.0008] * 165,
    }
    return factors.get(commodity.lower(), [0.0005, -0.0003, 0.0001, -0.0002] * 91)


def _generate_historical(commodity: str, current: float, days: int) -> list:
    """Synthetic but realistic historical prices."""
    import random
    prices = []
    p = current * 0.9
    for _ in range(days):
        p = p * (1 + random.uniform(-0.015, 0.018))
        prices.append(round(p, 2))
    return prices
