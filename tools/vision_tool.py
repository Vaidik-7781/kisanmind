"""
Vision tool — Gemini 2.0 Flash (free tier).
Identifies crop diseases, pests, soil conditions from images.
"""

import base64
import json
import re
import google.generativeai as genai
from config.settings import GEMINI_API_KEY, GEMINI_MODEL, CONFIDENCE_THRESHOLD

genai.configure(api_key=GEMINI_API_KEY)


VISION_SYSTEM_PROMPT = """
You are KisanMind Vision — an expert agricultural AI trained to identify:
1. Crop diseases (fungal, bacterial, viral, nutritional deficiencies)
2. Pest infestations
3. Soil conditions (waterlogging, cracking, nutrient deficiency signs)
4. Crop growth stage
5. Harvest readiness

Respond ONLY in this exact JSON format (no markdown, no extra text):
{
  "crop_detected": "wheat / tomato / rice / unknown",
  "issue_type": "disease / pest / deficiency / healthy / unknown",
  "issue_name": "Late Blight / Aphid Infestation / Nitrogen Deficiency / etc.",
  "confidence": 0.85,
  "symptoms_observed": ["yellowing leaves", "brown spots", "wilting"],
  "severity": "mild / moderate / severe",
  "affected_area_pct": 30,
  "treatment": {
    "organic": ["Neem oil spray 5ml/L water", "Remove infected leaves immediately"],
    "chemical": ["Mancozeb 75WP @ 2g/L water", "Spray every 7 days"],
    "dosage_per_acre": "200L spray solution per acre"
  },
  "preventive_measures": ["Ensure proper drainage", "Crop rotation next season"],
  "urgency": "immediate / within_3_days / within_week / monitor",
  "escalate_to_human": false,
  "additional_notes": "Any extra observations"
}

If confidence < 0.70, set escalate_to_human = true.
If image is not a crop/plant, return issue_type = "not_agricultural".
"""


def analyse_crop_image(image_bytes: bytes, extra_context: str = "") -> dict:
    """
    Analyse a crop image using Gemini Vision.

    Args:
        image_bytes: Raw image bytes (JPEG/PNG)
        extra_context: Optional farmer context ("wheat field, 45 days after sowing")

    Returns:
        Parsed analysis dict
    """
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not set"}

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)

        image_part = {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(image_bytes).decode("utf-8"),
        }

        prompt = VISION_SYSTEM_PROMPT
        if extra_context:
            prompt += f"\n\nFarmer context: {extra_context}"

        response = model.generate_content([prompt, image_part])
        raw_text = response.text.strip()

        # Strip markdown code fences if present
        raw_text = re.sub(r"```json|```", "", raw_text).strip()

        result = json.loads(raw_text)
        result["escalate_to_human"] = result.get("confidence", 1.0) < CONFIDENCE_THRESHOLD
        return result

    except json.JSONDecodeError:
        return {
            "error":              "Could not parse vision response",
            "raw_response":       response.text if 'response' in dir() else "",
            "escalate_to_human":  True,
        }
    except Exception as e:
        return {"error": str(e), "escalate_to_human": True}


def analyse_soil_image(image_bytes: bytes) -> dict:
    """Specialised soil analysis prompt."""
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not set"}

    soil_prompt = """
    Analyse this soil image and respond ONLY in JSON:
    {
      "soil_color": "black / red / brown / yellow / grey",
      "soil_type": "loamy / clay / sandy / black_cotton / laterite",
      "moisture_status": "dry / adequate / waterlogged",
      "visible_issues": ["cracking", "salt_crust", "erosion"],
      "fertility_estimate": "low / medium / high",
      "recommended_crops": ["wheat", "soybean"],
      "amendments_needed": ["add organic matter", "drainage improvement"],
      "confidence": 0.75
    }
    """
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        image_part = {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode("utf-8")}
        response = model.generate_content([soil_prompt, image_part])
        raw_text = re.sub(r"```json|```", "", response.text.strip()).strip()
        return json.loads(raw_text)
    except Exception as e:
        return {"error": str(e)}
