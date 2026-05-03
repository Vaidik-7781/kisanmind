"""
Farmer persistent memory — stored in Supabase.
Each farmer identified by telegram_id.
"""

import json
from datetime import datetime
from typing import Optional
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ─── Default profile ────────────────────────────────────────────────────────

def _default_profile(telegram_id: int, name: str = "Farmer") -> dict:
    return {
        "telegram_id":   str(telegram_id),
        "name":          name,
        "language":      "hi",
        "location":      None,          # {"city": ..., "lat": ..., "lon": ...}
        "land_acres":    None,
        "soil_type":     None,          # loamy / clay / sandy / black
        "current_crops": [],            # [{"name": "wheat", "sown_date": "..."}]
        "crop_history":  [],            # past seasons
        "disease_events": [],           # [{date, crop, disease, treatment}]
        "last_active":   datetime.utcnow().isoformat(),
        "created_at":    datetime.utcnow().isoformat(),
    }


# ─── CRUD ───────────────────────────────────────────────────────────────────

def get_profile(telegram_id: int) -> dict:
    """Fetch farmer profile. Creates default if not exists."""
    db = _get_client()
    resp = db.table("farmers").select("*").eq("telegram_id", str(telegram_id)).execute()
    if resp.data:
        profile = resp.data[0]
        # Parse JSON string columns
        for col in ("location", "current_crops", "crop_history", "disease_events"):
            if isinstance(profile.get(col), str):
                try:
                    profile[col] = json.loads(profile[col])
                except Exception:
                    profile[col] = [] if col != "location" else None
        return profile
    # create new
    new_profile = _default_profile(telegram_id)
    db.table("farmers").insert(_serialise(new_profile)).execute()
    return new_profile


def update_profile(telegram_id: int, updates: dict) -> dict:
    """Partially update farmer profile."""
    db = _get_client()
    updates["last_active"] = datetime.utcnow().isoformat()
    db.table("farmers").update(_serialise(updates)).eq("telegram_id", str(telegram_id)).execute()
    return get_profile(telegram_id)


def log_disease_event(telegram_id: int, crop: str, disease: str, treatment: str, confidence: float):
    profile = get_profile(telegram_id)
    events  = profile.get("disease_events") or []
    events.append({
        "date":       datetime.utcnow().isoformat(),
        "crop":       crop,
        "disease":    disease,
        "treatment":  treatment,
        "confidence": confidence,
    })
    # Keep last 50 events
    events = events[-50:]
    update_profile(telegram_id, {"disease_events": events})


def add_crop(telegram_id: int, crop_name: str, sown_date: Optional[str] = None):
    profile = get_profile(telegram_id)
    crops   = profile.get("current_crops") or []
    crops.append({
        "name":      crop_name,
        "sown_date": sown_date or datetime.utcnow().date().isoformat(),
    })
    update_profile(telegram_id, {"current_crops": crops})


def set_location(telegram_id: int, city: str, lat: float, lon: float):
    update_profile(telegram_id, {"location": {"city": city, "lat": lat, "lon": lon}})


def _serialise(d: dict) -> dict:
    """Convert lists/dicts to JSON strings for Supabase text columns."""
    out = {}
    for k, v in d.items():
        if isinstance(v, (list, dict)):
            out[k] = json.dumps(v, ensure_ascii=False)
        else:
            out[k] = v
    return out
