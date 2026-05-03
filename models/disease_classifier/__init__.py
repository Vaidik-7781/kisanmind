"""
Disease Classifier — fine-tuned vision model for crop disease classification.
Used as a FAST local classifier before calling Gemini Vision API.
Falls back gracefully to Gemini if model not loaded.

Model: PlantVillage fine-tuned ResNet50 / EfficientNet
Dataset: PlantVillage (54,309 images, 38 disease classes)
Source: https://github.com/spMohanty/PlantVillage-Dataset (free, public)

To use a pre-trained model:
1. Download from HuggingFace: nickmuchi/vit-finetuned-plant-disease
   pip install transformers
   from transformers import pipeline
   classifier = pipeline("image-classification", model="nickmuchi/vit-finetuned-plant-disease")

Or use our lightweight local model after training (see train.py).
"""

import io
from PIL import Image

# 38 PlantVillage disease classes
DISEASE_CLASSES = [
    "Apple___Apple_scab", "Apple___Black_rot", "Apple___Cedar_apple_rust", "Apple___healthy",
    "Blueberry___healthy",
    "Cherry___Powdery_mildew", "Cherry___healthy",
    "Corn___Cercospora_leaf_spot", "Corn___Common_rust", "Corn___Northern_Leaf_Blight", "Corn___healthy",
    "Grape___Black_rot", "Grape___Esca", "Grape___Leaf_blight", "Grape___healthy",
    "Orange___Haunglongbing",
    "Peach___Bacterial_spot", "Peach___healthy",
    "Pepper___Bacterial_spot", "Pepper___healthy",
    "Potato___Early_blight", "Potato___Late_blight", "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch", "Strawberry___healthy",
    "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight",
    "Tomato___Leaf_Mold", "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites", "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]

# Friendly display names
CLASS_DISPLAY = {
    "Tomato___Late_blight":        ("Tomato", "Late Blight", "fungal"),
    "Tomato___Early_blight":       ("Tomato", "Early Blight", "fungal"),
    "Potato___Late_blight":        ("Potato", "Late Blight", "fungal"),
    "Potato___Early_blight":       ("Potato", "Early Blight", "fungal"),
    "Corn___Common_rust":          ("Maize", "Common Rust", "fungal"),
    "Corn___Northern_Leaf_Blight": ("Maize", "Northern Leaf Blight", "fungal"),
    "Tomato___Leaf_Mold":          ("Tomato", "Leaf Mold", "fungal"),
    "Tomato___Spider_mites":       ("Tomato", "Spider Mite Infestation", "pest"),
    "Apple___Apple_scab":          ("Apple", "Apple Scab", "fungal"),
    "Grape___Black_rot":           ("Grape", "Black Rot", "fungal"),
    "Tomato___Bacterial_spot":     ("Tomato", "Bacterial Spot", "bacterial"),
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": ("Tomato", "Yellow Leaf Curl Virus", "viral"),
}


_hf_pipeline = None


def load_hf_model():
    """Load HuggingFace plant disease classifier (downloads once, ~90MB)."""
    global _hf_pipeline
    if _hf_pipeline is not None:
        return _hf_pipeline
    try:
        from transformers import pipeline
        _hf_pipeline = pipeline(
            "image-classification",
            model="nickmuchi/vit-finetuned-plant-disease",
            top_k=3,
        )
        return _hf_pipeline
    except Exception as e:
        print(f"[Disease Classifier] HuggingFace model not available: {e}")
        return None


def classify_image(image_bytes: bytes) -> dict | None:
    """
    Quick local classification before calling Gemini Vision.
    Returns None if model unavailable (falls back to Gemini).

    Returns:
        {
          "crop": "Tomato",
          "disease": "Late Blight",
          "type": "fungal",
          "confidence": 0.87,
          "raw_label": "Tomato___Late_blight"
        }
    """
    clf = load_hf_model()
    if clf is None:
        return None

    try:
        image   = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        results = clf(image)

        if not results:
            return None

        top = results[0]
        label      = top["label"]
        confidence = top["score"]

        display = CLASS_DISPLAY.get(label)
        if display:
            crop, disease, dtype = display
        else:
            # Parse from raw label
            parts   = label.split("___")
            crop    = parts[0].replace("_", " ") if parts else "Unknown"
            disease = parts[1].replace("_", " ") if len(parts) > 1 else "Unknown"
            dtype   = "unknown"

        is_healthy = "healthy" in label.lower()

        return {
            "crop":       crop,
            "disease":    "Healthy" if is_healthy else disease,
            "type":       "healthy" if is_healthy else dtype,
            "confidence": round(confidence, 3),
            "raw_label":  label,
            "all_results": [{"label": r["label"], "score": r["score"]} for r in results],
        }

    except Exception as e:
        print(f"[Disease Classifier] Error: {e}")
        return None
