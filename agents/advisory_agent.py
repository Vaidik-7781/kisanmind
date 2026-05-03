"""
Advisory Agent — answers farmer questions about pesticides, fertilizers,
crop care using Groq LLM + RAG knowledge base.
"""

from openai import OpenAI
from tools.rag_tool import search_knowledge
from memory.farmer_profile import get_profile
from memory.conversation import get_history, add_message
from config.settings import GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL

client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)


SYSTEM_PROMPT = """
You are KisanMind — an expert agricultural advisor for Indian farmers.
You help with crop diseases, pesticides, fertilizers, irrigation, and farming practices.

RULES:
1. Always recommend ORGANIC solutions first, chemical only if organic fails.
2. NEVER recommend banned pesticides (Endosulfan, Monocrotophos, Methyl Parathion, DDT).
3. Give specific dosages (g/L or ml/L), not vague amounts.
4. Mention pre-harvest interval (PHI) for chemical pesticides.
5. Cite source when using scientific info (ICAR, KVK, etc.)
6. If unsure, say so — never guess for health/safety issues.
7. Keep answers concise for WhatsApp/Telegram (no long paragraphs).
8. Use simple Hindi/regional language phrases when appropriate.
9. Always end with a safety reminder for chemical use.

You have access to knowledge base context provided in each message.
Farmer profile will be provided for personalized advice.
"""


def run(telegram_id: int, user_message: str, rag_context: list = None) -> dict:
    """
    Answer farmer's advisory question using LLM + RAG.

    Args:
        telegram_id:  Farmer ID for profile + history
        user_message: Farmer's question
        rag_context:  Pre-fetched RAG results (optional)

    Returns:
        {"response_text": "...", "rag_used": bool}
    """
    profile = get_profile(telegram_id)
    history = get_history(telegram_id)

    # ── RAG search if not pre-fetched ─────────────────────────────────────────
    if rag_context is None:
        rag_context = search_knowledge(user_message, n_results=3)

    rag_text = ""
    if rag_context and rag_context[0].get("score", 0) > 0.3:
        rag_text = "\n\n".join([
            f"[Source: {r.get('source', 'ICAR')}]\n{r['text']}"
            for r in rag_context if r.get("score", 0) > 0.3
        ])

    # ── Build context message ─────────────────────────────────────────────────
    farmer_ctx = _build_farmer_context(profile)
    system_with_ctx = SYSTEM_PROMPT
    if farmer_ctx:
        system_with_ctx += f"\n\nFARMER PROFILE:\n{farmer_ctx}"
    if rag_text:
        system_with_ctx += f"\n\nKNOWLEDGE BASE CONTEXT:\n{rag_text}"

    # ── Build messages list ───────────────────────────────────────────────────
    messages = [{"role": "system", "content": system_with_ctx}]
    # Add recent history (last 6 turns)
    messages += history[-6:]
    messages.append({"role": "user", "content": user_message})

    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=600,
            temperature=0.3,
        )
        answer = resp.choices[0].message.content.strip()

        # Save to conversation memory
        add_message(telegram_id, "user",      user_message)
        add_message(telegram_id, "assistant", answer)

        return {
            "response_text": answer,
            "rag_used":      bool(rag_text),
            "sources":       [r.get("source") for r in rag_context if r.get("score", 0) > 0.3],
        }

    except Exception as e:
        fallback = _fallback_response(user_message)
        return {"response_text": fallback, "rag_used": False, "error": str(e)}


def _build_farmer_context(profile: dict) -> str:
    parts = []
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    if profile.get("location"):
        parts.append(f"Location: {profile['location'].get('city', 'N/A')}")
    if profile.get("land_acres"):
        parts.append(f"Land: {profile['land_acres']} acres")
    if profile.get("soil_type"):
        parts.append(f"Soil: {profile['soil_type']}")
    crops = profile.get("current_crops", [])
    if crops:
        parts.append(f"Current crops: {', '.join(c['name'] for c in crops)}")
    return "\n".join(parts)


def _fallback_response(message: str) -> str:
    """Return when Groq API fails."""
    msg_lower = message.lower()
    if any(w in msg_lower for w in ["disease", "blight", "rust", "rot", "spot"]):
        return (
            "⚠️ API temporarily unavailable.\n\n"
            "General disease advice:\n"
            "1. Remove and destroy infected plant parts\n"
            "2. Spray Mancozeb 75WP @ 2g/L water\n"
            "3. Improve air circulation\n"
            "4. Avoid overhead irrigation\n\n"
            "Please try again in a moment for specific advice."
        )
    return (
        "⚠️ I'm temporarily unable to process your query.\n"
        "Please try again in a few minutes.\n\n"
        "For urgent issues, contact your local KVK:\n"
        "📞 Kisan Call Centre: 1800-180-1551 (free)"
    )
