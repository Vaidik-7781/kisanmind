"""
Mandi price tool — scrapes AGMARKNET (free govt data).
Also calls data.gov.in commodity price API if key available.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from config.settings import DATA_GOV_API_KEY


# ─── data.gov.in API (free with registration) ───────────────────────────────

DATA_GOV_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
# ^ Commodity prices dataset from data.gov.in


def get_mandi_prices(commodity: str, state: str = None, limit: int = 20) -> dict:
    """
    Fetch latest mandi prices for a commodity.
    Falls back to mock data if API unavailable.
    """
    if DATA_GOV_API_KEY:
        return _fetch_from_data_gov(commodity, state, limit)
    return _fetch_from_agmarknet_scrape(commodity, state)


def _fetch_from_data_gov(commodity: str, state: str, limit: int) -> dict:
    params = {
        "api-key":  DATA_GOV_API_KEY,
        "format":   "json",
        "limit":    limit,
        "filters[commodity]": commodity.title(),
    }
    if state:
        params["filters[state]"] = state.title()

    try:
        resp = requests.get(DATA_GOV_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        records = data.get("records", [])
        return _parse_records(commodity, records)
    except Exception as e:
        return {"error": str(e), "commodity": commodity}


def _fetch_from_agmarknet_scrape(commodity: str, state: str) -> dict:
    """
    Lightweight scrape of AGMARKNET public search page.
    Returns best-effort results.
    """
    today  = datetime.now()
    date_s = today.strftime("%d-%b-%Y")
    url    = "https://agmarknet.gov.in/SearchCmmMkt.aspx"
    params = {
        "Tx_Commodity": commodity,
        "Tx_State":     state or "0",
        "Tx_District":  "0",
        "Tx_Market":    "0",
        "DateFrom":     date_s,
        "DateTo":       date_s,
        "Fr_Date":      date_s,
        "To_Date":      date_s,
        "Tx_Trend":     "0",
        "Tx_CommodityHead": commodity.title(),
        "Tx_StateHead": state or "--Select--",
    }
    headers = {"User-Agent": "Mozilla/5.0 (compatible; KisanMind/1.0)"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"id": "cphBody_GridPriceData"})
        if not table:
            return _fallback_mock(commodity)
        records = []
        rows = table.find_all("tr")[1:]
        for row in rows[:20]:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) >= 8:
                records.append({
                    "state":        cols[0],
                    "district":     cols[1],
                    "market":       cols[2],
                    "commodity":    cols[3],
                    "variety":      cols[4],
                    "min_price":    _safe_float(cols[5]),
                    "max_price":    _safe_float(cols[6]),
                    "modal_price":  _safe_float(cols[7]),
                    "date":         cols[8] if len(cols) > 8 else date_s,
                })
        return _parse_records(commodity, records)
    except Exception as e:
        return _fallback_mock(commodity)


def _parse_records(commodity: str, records: list) -> dict:
    if not records:
        return _fallback_mock(commodity)

    modal_prices = [r.get("modal_price", 0) or r.get("Modal_x0020_Price", 0) for r in records if r.get("modal_price") or r.get("Modal_x0020_Price")]
    modal_prices = [float(p) for p in modal_prices if p]

    result = {
        "commodity":       commodity,
        "date":            datetime.now().strftime("%Y-%m-%d"),
        "markets":         records[:10],
        "avg_price":       round(sum(modal_prices) / len(modal_prices), 2) if modal_prices else 0,
        "min_price":       min(modal_prices) if modal_prices else 0,
        "max_price":       max(modal_prices) if modal_prices else 0,
        "recommendation":  "",
    }
    result["recommendation"] = _price_recommendation(result)
    return result


def get_price_trend(commodity: str, days: int = 7) -> list[dict]:
    """
    Fetch price trend for last N days. Used by price forecaster.
    Returns list of {date, price} dicts.
    """
    trend = []
    for i in range(days, 0, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        # In production: query historical API. For MVP use slight variation
        base = _get_base_price(commodity)
        import random
        price = base + random.uniform(-base * 0.05, base * 0.05)
        trend.append({"date": d, "price": round(price, 2)})
    return trend


def _price_recommendation(data: dict) -> str:
    avg = data["avg_price"]
    mx  = data["max_price"]
    mn  = data["min_price"]
    spread = mx - mn
    if spread > avg * 0.3:
        return f"📊 High price variation across markets (₹{mn}–₹{mx}). Travel to higher-price mandi if possible."
    if avg > 0:
        return f"📊 Stable prices around ₹{avg}/quintal. Check local transport cost before deciding mandi."
    return "📊 Price data unavailable. Check local mandi directly."


def _get_base_price(commodity: str) -> float:
    base_prices = {
        "wheat": 2200, "rice": 2100, "maize": 1900, "onion": 1500,
        "tomato": 1200, "potato": 1100, "soybean": 4200, "cotton": 6000,
        "sugarcane": 350, "mustard": 5200, "groundnut": 5500,
    }
    return base_prices.get(commodity.lower(), 2000)


def _fallback_mock(commodity: str) -> dict:
    base = _get_base_price(commodity)
    return {
        "commodity":      commodity,
        "date":           datetime.now().strftime("%Y-%m-%d"),
        "avg_price":      base,
        "min_price":      round(base * 0.9, 2),
        "max_price":      round(base * 1.1, 2),
        "markets":        [],
        "recommendation": f"📊 Live data unavailable. Estimated price: ₹{base}/quintal. Verify at local mandi.",
        "note":           "Mock data — set DATA_GOV_API_KEY for live prices",
    }


def _safe_float(val: str) -> float:
    try:
        return float(val.replace(",", ""))
    except Exception:
        return 0.0
