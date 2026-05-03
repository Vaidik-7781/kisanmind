"""
Vision Agent — analyses crop/soil images, looks up treatment in RAG knowledge base.
"""

from tools.vision_tool import analyse_crop_image, analyse_soil_image
from tools.rag_tool import search_knowledge
from memory.farmer_profile import log_disease_event, get_profile
from config.settings import CONFIDENCE_THRESHOLD


def run(image_bytes: bytes, telegram_id: int, image_type: str = "crop") -> dict:
    """
    Main entry point for vision agent.

    Args:
        image_bytes:  Raw image bytes
        telegram_id:  Farmer's Telegram ID
        image_type:   'crop' | 'soil'

    Returns:
        {
          "analysis": {...},
          "rag_context": [...],
          "response_text": "...",
          "needs_escalation": bool
        }
    """
    profile = get_profile(telegram_id)
    lang    = profile.get("language", "hi")
    crops   = profile.get("current_crops", [])
    context = f"Farmer growing: {', '.join(c['name'] for c in crops)}" if crops else ""

    # ── Run vision model ─────────────────────────────────────────────────────
    if image_type == "soil":
        analysis = analyse_soil_image(image_bytes)
        response = _format_soil_response(analysis, lang)
        return {"analysis": analysis, "rag_context": [], "response_text": response, "needs_escalation": False}

    analysis = analyse_crop_image(image_bytes, context)

    if "error" in analysis:
        return {
            "analysis":        analysis,
            "rag_context":     [],
            "response_text":   f"❌ Image analysis failed: {analysis['error']}\nPlease try sending a clearer photo.",
            "needs_escalation": True,
        }

    if analysis.get("issue_type") == "not_agricultural":
        return {
            "analysis":        analysis,
            "rag_context":     [],
            "response_text":   "🤔 This image doesn't appear to be a crop or plant. Please send a photo of your crop or field.",
            "needs_escalation": False,
        }

    # ── RAG lookup for treatment info ────────────────────────────────────────
    query      = f"{analysis.get('issue_name', '')} {analysis.get('crop_detected', '')} treatment"
    rag_docs   = search_knowledge(query, n_results=3, category=None)

    # ── Log to farmer profile ────────────────────────────────────────────────
    if analysis.get("issue_name") and analysis.get("issue_type") not in ("healthy", "unknown"):
        log_disease_event(
            telegram_id  = telegram_id,
            crop         = analysis.get("crop_detected", "unknown"),
            disease      = analysis.get("issue_name", "unknown"),
            treatment    = str(analysis.get("treatment", {})),
            confidence   = analysis.get("confidence", 0),
        )

    response = _format_disease_response(analysis, rag_docs, lang)

    return {
        "analysis":         analysis,
        "rag_context":      rag_docs,
        "response_text":    response,
        "needs_escalation": analysis.get("escalate_to_human", False),
    }


def _format_disease_response(analysis: dict, rag_docs: list, lang: str) -> str:
    if not analysis:
        return "Could not analyse image."

    crop       = analysis.get("crop_detected", "Unknown crop")
    issue      = analysis.get("issue_name", "Unknown issue")
    issue_type = analysis.get("issue_type", "")
    confidence = analysis.get("confidence", 0)
    severity   = analysis.get("severity", "unknown")
    urgency    = analysis.get("urgency", "monitor")
    symptoms   = analysis.get("symptoms_observed", [])
    treatment  = analysis.get("treatment", {})

    # Urgency emoji
    urgency_emoji = {"immediate": "🚨", "within_3_days": "⚠️", "within_week": "📋", "monitor": "👁️"}.get(urgency, "📋")

    if issue_type == "healthy":
        return f"✅ *Good news!* Your {crop} crop looks *healthy*.\n\n{analysis.get('additional_notes', '')}"

    lines = [
        f"🌿 *Crop:* {crop.title()}",
        f"🔬 *Detected:* {issue}",
        f"📊 *Confidence:* {int(confidence * 100)}%",
        f"⚡ *Severity:* {severity.upper()}",
        f"{urgency_emoji} *Action needed:* {urgency.replace('_', ' ').title()}",
        "",
        f"*Symptoms seen:*",
        "\n".join(f"  • {s}" for s in symptoms),
        "",
    ]

    # Organic treatment
    organic = treatment.get("organic", [])
    if organic:
        lines += ["🌿 *Organic Treatment:*", "\n".join(f"  {i+1}. {t}" for i, t in enumerate(organic))]

    # Chemical treatment
    chemical = treatment.get("chemical", [])
    if chemical:
        lines += ["", "💊 *Chemical Treatment (if severe):*", "\n".join(f"  {i+1}. {t}" for i, t in enumerate(chemical))]

    dosage = treatment.get("dosage_per_acre")
    if dosage:
        lines += ["", f"📏 *Dosage:* {dosage}"]

    preventive = analysis.get("preventive_measures", [])
    if preventive:
        lines += ["", "*Prevention:*", "\n".join(f"  • {p}" for p in preventive)]

    # Add RAG context if available and high score
    good_rag = [r for r in rag_docs if r.get("score", 0) > 0.5]
    if good_rag:
        lines += ["", f"📚 *Source: {good_rag[0].get('source', 'ICAR')}*"]

    if analysis.get("escalate_to_human"):
        lines += ["", "⚠️ *Low confidence. Please consult your local Krishi Vigyan Kendra (KVK) or agriculture extension officer.*"]

    return "\n".join(lines)


def _format_soil_response(analysis: dict, lang: str) -> str:
    if "error" in analysis:
        return f"❌ Soil analysis failed: {analysis['error']}"

    lines = [
        "🌱 *Soil Analysis*",
        f"*Color:* {analysis.get('soil_color', 'N/A')}",
        f"*Type:* {analysis.get('soil_type', 'N/A')}",
        f"*Moisture:* {analysis.get('moisture_status', 'N/A')}",
        f"*Fertility:* {analysis.get('fertility_estimate', 'N/A')}",
    ]
    issues = analysis.get("visible_issues", [])
    if issues:
        lines += ["", "*Issues noticed:*", "\n".join(f"  • {i}" for i in issues)]

    crops = analysis.get("recommended_crops", [])
    if crops:
        lines += ["", f"*Suitable crops:* {', '.join(crops)}"]

    amendments = analysis.get("amendments_needed", [])
    if amendments:
        lines += ["", "*Amendments needed:*", "\n".join(f"  • {a}" for a in amendments)]

    return "\n".join(lines)
