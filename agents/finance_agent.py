"""
Finance Agent — subsidies, crop insurance (PMFBY), KCC loans, PM-KISAN eligibility.
"""

from openai import OpenAI
from tools.rag_tool import search_knowledge
from memory.farmer_profile import get_profile
from config.settings import GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL

client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)


# Quick reference for most common schemes
SCHEME_QUICK_REF = {
    "pm-kisan": {
        "name":         "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
        "benefit":      "₹6,000/year in 3 installments of ₹2,000",
        "eligibility":  "Small/marginal farmers with cultivable land",
        "documents":    ["Aadhaar card", "Bank account", "Land records (Khatauni/7-12)"],
        "apply":        "pmkisan.gov.in or nearest CSC",
        "helpline":     "155261",
        "emoji":        "💸",
    },
    "pmfby": {
        "name":         "PMFBY (Pradhan Mantri Fasal Bima Yojana)",
        "benefit":      "Crop insurance. Premium: 2% Kharif, 1.5% Rabi, 5% Horticulture",
        "eligibility":  "All farmers with notified crops in notified areas",
        "documents":    ["Land records", "Aadhaar", "Bank account", "Sowing certificate"],
        "apply":        "pmfby.gov.in, nearest bank, or insurance company",
        "helpline":     "1800-200-7710",
        "emoji":        "🛡️",
    },
    "kcc": {
        "name":         "Kisan Credit Card (KCC)",
        "benefit":      "Short-term crop loan @ 4% interest (after subvention). ATM card included.",
        "eligibility":  "All farmers, SHGs, JLGs involved in farming/allied activities",
        "documents":    ["Land records", "Aadhaar", "Photo", "Bank account"],
        "apply":        "Nearest bank branch (SBI, PNB, cooperative bank)",
        "helpline":     "1800-180-1551",
        "emoji":        "💳",
    },
    "soil_health_card": {
        "name":         "Soil Health Card Scheme",
        "benefit":      "Free soil testing + nutrient recommendation card",
        "eligibility":  "All farmers",
        "documents":    ["Land parcel details"],
        "apply":        "Local agriculture department office or soilhealth.dac.gov.in",
        "helpline":     "1800-180-1551",
        "emoji":        "🌱",
    },
    "pm_kusum": {
        "name":         "PM-KUSUM (Solar Pump Scheme)",
        "benefit":      "90% subsidy on solar water pumps (central + state combined)",
        "eligibility":  "Individual farmers, groups, cooperatives",
        "documents":    ["Land records", "Aadhaar", "Bank account"],
        "apply":        "State DISCOM or agriculture department",
        "helpline":     "1800-180-3333",
        "emoji":        "☀️",
    },
}


def run(telegram_id: int, query: str) -> dict:
    """
    Answer finance/subsidy questions for farmer.

    Returns:
        {"response_text": "...", "schemes": [...]}
    """
    profile = get_profile(telegram_id)
    acres   = profile.get("land_acres")
    crops   = profile.get("current_crops", [])
    loc     = profile.get("location", {})

    # Quick match for known schemes
    quick = _quick_match(query)
    if quick:
        return {"response_text": _format_scheme(quick, acres), "schemes": [quick]}

    # RAG search
    rag_docs = search_knowledge(query, n_results=3, category="subsidy")
    rag_text = "\n".join(r["text"] for r in rag_docs if r.get("score", 0) > 0.2)

    # LLM response
    farmer_ctx = f"""
Farmer profile:
- Land: {acres or 'unknown'} acres
- Crops: {', '.join(c['name'] for c in crops) or 'not specified'}
- Location: {loc.get('city', 'India') if loc else 'India'}
"""
    prompt = f"""
Farmer query: "{query}"

{farmer_ctx}

Knowledge base context:
{rag_text if rag_text else 'No specific context found.'}

Common schemes available:
- PM-KISAN: ₹6000/year cash transfer
- PMFBY: Crop insurance
- KCC: Low-interest farm loan @ 4%
- Soil Health Card: Free soil testing
- PM-KUSUM: Solar pump subsidy

Answer the farmer's query about subsidies, loans, or government schemes.
Be specific about:
1. What benefit they get
2. How to apply
3. Documents needed
4. Helpline number

Keep answer concise and actionable (Telegram-friendly).
"""
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a government scheme advisor for Indian farmers. Give accurate, simple information about agricultural subsidies and loans."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.2,
        )
        answer = resp.choices[0].message.content.strip()
    except Exception as e:
        answer = _fallback_finance_response()

    return {"response_text": answer, "schemes": list(SCHEME_QUICK_REF.values())}


def get_all_schemes_summary() -> str:
    """Return a quick summary of all major schemes."""
    lines = ["💰 *Government Schemes for Farmers*\n"]
    for key, scheme in SCHEME_QUICK_REF.items():
        lines.append(
            f"{scheme['emoji']} *{scheme['name']}*\n"
            f"   {scheme['benefit']}\n"
            f"   Apply: {scheme['apply']}\n"
        )
    lines.append("\n📞 *Kisan Call Centre: 1800-180-1551* (Free, 24x7)")
    return "\n".join(lines)


def _quick_match(query: str) -> dict | None:
    """Direct match for scheme keywords."""
    q = query.lower()
    if any(w in q for w in ["pm kisan", "pm-kisan", "pmkisan", "6000", "samman nidhi"]):
        return SCHEME_QUICK_REF["pm-kisan"]
    if any(w in q for w in ["insurance", "bima", "pmfby", "fasal bima"]):
        return SCHEME_QUICK_REF["pmfby"]
    if any(w in q for w in ["kcc", "kisan credit", "credit card", "loan"]):
        return SCHEME_QUICK_REF["kcc"]
    if any(w in q for w in ["soil test", "soil health", "soil card"]):
        return SCHEME_QUICK_REF["soil_health_card"]
    if any(w in q for w in ["solar", "kusum", "pump"]):
        return SCHEME_QUICK_REF["pm_kusum"]
    return None


def _format_scheme(scheme: dict, acres: float = None) -> str:
    lines = [
        f"{scheme['emoji']} *{scheme['name']}*",
        "",
        f"✅ *Benefit:* {scheme['benefit']}",
        f"👤 *Eligibility:* {scheme['eligibility']}",
        "",
        "*Documents needed:*",
        "\n".join(f"  • {d}" for d in scheme["documents"]),
        "",
        f"📝 *Apply at:* {scheme['apply']}",
        f"📞 *Helpline:* {scheme['helpline']} (Free call)",
    ]
    return "\n".join(lines)


def _fallback_finance_response() -> str:
    return (
        "💡 *Main Government Schemes for Farmers:*\n\n"
        "1. *PM-KISAN* — ₹6000/year cash. Apply: pmkisan.gov.in\n"
        "2. *PMFBY* — Crop insurance from 1.5% premium\n"
        "3. *KCC* — Farm loan @ 4% interest\n"
        "4. *Soil Health Card* — Free soil test\n\n"
        "📞 *Kisan Call Centre: 1800-180-1551* (Free, 24x7)"
    )
