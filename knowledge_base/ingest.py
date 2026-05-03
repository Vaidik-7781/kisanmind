"""
Knowledge base ingestion — loads ICAR PDFs + subsidy scheme docs into ChromaDB.
Run once: python -m knowledge_base.ingest

Sources (all free, public domain):
- ICAR crop manuals (icar.org.in)
- PM-Kisan / PMFBY scheme docs
- Pesticide approved/banned list (CIB&RC)
- Built-in seed knowledge for bootstrap
"""

import os
import uuid
from tools.rag_tool import add_documents, get_collection_stats

# ─── Built-in seed knowledge (bootstrap without PDFs) ─────────────────────

SEED_KNOWLEDGE = [
    # ── Diseases ─────────────────────────────────────────────────────────────
    {
        "text": "Late Blight in tomato is caused by Phytophthora infestans. Symptoms: dark brown spots on leaves with white mold underside. Treatment: Mancozeb 75WP @ 2g/L or Metalaxyl 8% + Mancozeb 64% WP @ 2.5g/L. Spray every 7-10 days. Organic: Copper oxychloride 0.3% spray.",
        "meta": {"source": "ICAR Tomato Manual", "category": "disease", "crop": "tomato"},
    },
    {
        "text": "Wheat rust (Yellow/Brown/Black rust) caused by Puccinia spp. Yellow rust: yellow stripes on leaves. Brown rust: circular orange pustules. Black rust: dark pustules on stem. Treatment: Propiconazole 25EC @ 0.1% or Tebuconazole 25.9EC @ 0.1%. Spray at first sign.",
        "meta": {"source": "ICAR Wheat Manual", "category": "disease", "crop": "wheat"},
    },
    {
        "text": "Rice blast caused by Magnaporthe oryzae. Symptoms: diamond-shaped lesions with grey center on leaves. Neck blast causes panicle to break. Treatment: Tricyclazole 75WP @ 0.6g/L or Carbendazim 50WP @ 1g/L. Spray at tillering and booting stage.",
        "meta": {"source": "ICAR Rice Manual", "category": "disease", "crop": "rice"},
    },
    {
        "text": "Powdery Mildew on wheat and vegetables caused by Erysiphe spp. White powdery coating on leaves. Treatment: Sulphur 80WP @ 2g/L water. Organic: Baking soda (sodium bicarbonate) 5g/L + soap. Ensure good air circulation.",
        "meta": {"source": "ICAR Plant Protection", "category": "disease", "crop": "wheat"},
    },
    {
        "text": "Cotton bollworm (Helicoverpa armigera) is major pest. Larvae bore into bolls. Treatment: Emamectin Benzoate 5SG @ 0.5g/L or Spinosad 45SC @ 0.3ml/L. Bt spray effective organically. Use pheromone traps for monitoring.",
        "meta": {"source": "ICAR Cotton Manual", "category": "pest", "crop": "cotton"},
    },
    {
        "text": "Aphids on mustard (Lipaphis erysimi) cause severe yield loss. Yellow-green insects under leaves. Treatment: Imidacloprid 17.8SL @ 0.5ml/L or Dimethoate 30EC @ 2ml/L. Organic: Neem oil 5ml/L + soap. Natural enemy: ladybird beetles.",
        "meta": {"source": "ICAR Oilseed Manual", "category": "pest", "crop": "mustard"},
    },
    {
        "text": "Nitrogen deficiency in crops shows as yellowing of older leaves first (chlorosis). Fix: Apply Urea 45% N @ 5kg per kg of N needed. Split application recommended. Organic: Compost 5 ton/acre or FYM 10 ton/acre. Soil test before application.",
        "meta": {"source": "ICAR Soil Science", "category": "deficiency", "crop": "all"},
    },
    {
        "text": "Iron deficiency (chlorosis) in rice and soybean. Interveinal yellowing on young leaves. Fix: Ferrous Sulphate 0.5% foliar spray. Apply 3-4 times at weekly intervals. Add lime if soil pH < 5.5. Iron chelate (EDTA) more effective in alkaline soils.",
        "meta": {"source": "ICAR Soil Manual", "category": "deficiency", "crop": "rice"},
    },
    # ── Crop Planning ─────────────────────────────────────────────────────────
    {
        "text": "Wheat sowing in North India: optimal time October 25 to November 25. Late sowing reduces yield 30-40%. Recommended varieties: HD-2967, HD-3086, GW-322. Seed rate: 100kg/acre. Basal dose: DAP 50kg/acre + MOP 20kg/acre. Irrigate 5-6 times.",
        "meta": {"source": "ICAR Wheat Agronomy", "category": "crop_planning", "crop": "wheat"},
    },
    {
        "text": "Tomato crop duration: 90-120 days. Best season: Rabi (Oct-Jan) in North India. Nursery raising: 25-30 days. Spacing: 60x45cm. Fertilizer: 120:60:60 NPK kg/ha. Drip irrigation saves 40% water. Support staking needed for indeterminate varieties.",
        "meta": {"source": "ICAR Vegetable Manual", "category": "crop_planning", "crop": "tomato"},
    },
    {
        "text": "Crop rotation benefits: Break pest/disease cycles, improve soil health. Good rotations: Wheat-Rice-Mustard, Maize-Wheat-Moong, Cotton-Wheat-Groundnut. Legumes in rotation fix nitrogen (40-60 kg N/ha). Avoid same crop family consecutively.",
        "meta": {"source": "ICAR Agronomy", "category": "crop_planning", "crop": "all"},
    },
    # ── Irrigation ────────────────────────────────────────────────────────────
    {
        "text": "Drip irrigation saves 30-50% water vs flood. Suitable for vegetables, cotton, sugarcane. Critical irrigation stages for wheat: Crown root initiation (20-25 DAS), tillering (40-45 DAS), jointing (60-65 DAS), flowering (80-85 DAS), grain filling (100-105 DAS).",
        "meta": {"source": "ICAR Water Management", "category": "irrigation", "crop": "wheat"},
    },
    {
        "text": "Sprinkler irrigation efficiency 75-80% vs flood 40-50%. Suitable for uneven terrain, sandy soils. Avoid sprinkler during wind >15 km/hr. Best time: early morning or evening. Reduces foliar disease risk vs overhead flooding.",
        "meta": {"source": "ICAR Irrigation Manual", "category": "irrigation", "crop": "all"},
    },
    # ── Subsidies ─────────────────────────────────────────────────────────────
    {
        "text": "PM-KISAN: Rs 6000/year direct benefit transfer to farmer families. 3 installments of Rs 2000. Eligibility: small/marginal farmers with cultivable land. Apply at local CSC or pmkisan.gov.in. Required documents: Aadhaar, bank account, land records (Khatauni).",
        "meta": {"source": "PM-KISAN Scheme", "category": "subsidy", "crop": "all"},
    },
    {
        "text": "PMFBY (Pradhan Mantri Fasal Bima Yojana) crop insurance. Premium: 2% for Kharif, 1.5% for Rabi, 5% for horticulture. Government pays rest. Apply before sowing at bank or CSC. Claim for natural calamity, pest, disease. Min compensation: sum insured per hectare.",
        "meta": {"source": "PMFBY Scheme", "category": "subsidy", "crop": "all"},
    },
    {
        "text": "Kisan Credit Card (KCC): Short-term credit for farming needs. Interest rate 4% after 3% interest subvention. Limit based on land holding + crop. Repay after harvest. Apply at nearest bank with land records. ATM withdrawal possible. Valid 5 years.",
        "meta": {"source": "KCC Scheme", "category": "finance", "crop": "all"},
    },
    {
        "text": "Soil Health Card scheme: Free soil testing by govt every 2 years. Card recommends fertilizer doses for 6 major + micronutrients. Apply at village level soil testing lab or agriculture department. Use recommendations to reduce fertilizer cost 20-30%.",
        "meta": {"source": "Soil Health Card Scheme", "category": "subsidy", "crop": "all"},
    },
    # ── Pesticide safety ──────────────────────────────────────────────────────
    {
        "text": "Banned pesticides in India (CIB&RC 2020): Monocrotophos, Methyl Parathion, Phorate, Triazophos, Chlorpyrifos (for some uses), Endosulfan, Lindane, DDT (for agriculture). Never use these. Check CIB&RC approved pesticide list before purchase.",
        "meta": {"source": "CIB&RC Pesticide List", "category": "pesticide", "crop": "all"},
    },
    {
        "text": "Neem-based pesticides are safe organic option. Neem oil 5ml + soap 2ml per liter water. Effective against aphids, whitefly, mites, thrips. 0 days pre-harvest interval. No chemical residue. ICAR recommends as first option before chemical pesticides.",
        "meta": {"source": "ICAR Organic Farming", "category": "pesticide", "crop": "all"},
    },
]


def ingest_seed_knowledge():
    """Load built-in knowledge into ChromaDB."""
    print("Ingesting seed knowledge...")
    texts     = [item["text"] for item in SEED_KNOWLEDGE]
    metadatas = [item["meta"] for item in SEED_KNOWLEDGE]
    ids       = [str(uuid.uuid4()) for _ in SEED_KNOWLEDGE]
    count     = add_documents(texts, metadatas, ids)
    print(f"✅ Ingested {count} seed documents")


def ingest_pdf_directory(directory: str, category: str = "general"):
    """
    Ingest all PDFs from a directory.
    Uses PyMuPDF for text extraction.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("PyMuPDF not installed. Run: pip install pymupdf")
        return

    pdf_files = [f for f in os.listdir(directory) if f.endswith(".pdf")]
    if not pdf_files:
        print(f"No PDFs found in {directory}")
        return

    all_texts = []
    all_metas = []
    all_ids   = []

    for fname in pdf_files:
        path = os.path.join(directory, fname)
        print(f"Processing: {fname}")
        try:
            doc    = fitz.open(path)
            source = fname.replace(".pdf", "")
            for page_num, page in enumerate(doc):
                text = page.get_text().strip()
                if len(text) < 100:
                    continue
                # Chunk into ~500 char pieces
                chunks = _chunk_text(text, chunk_size=500, overlap=50)
                for i, chunk in enumerate(chunks):
                    all_texts.append(chunk)
                    all_metas.append({
                        "source":   source,
                        "category": category,
                        "page":     page_num + 1,
                        "crop":     "all",
                    })
                    all_ids.append(f"{source}_p{page_num}_c{i}_{uuid.uuid4().hex[:8]}")
        except Exception as e:
            print(f"Error processing {fname}: {e}")

    if all_texts:
        add_documents(all_texts, all_metas, all_ids)
        print(f"✅ Ingested {len(all_texts)} chunks from {len(pdf_files)} PDFs")


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    chunks = []
    start  = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c for c in chunks if len(c) > 100]


if __name__ == "__main__":
    print("=== KisanMind Knowledge Base Ingestion ===")
    ingest_seed_knowledge()

    # Ingest PDFs if directories exist
    icar_dir    = "knowledge_base/icar_docs"
    subsidy_dir = "knowledge_base/subsidy_schemes"

    if os.path.exists(icar_dir) and os.listdir(icar_dir):
        ingest_pdf_directory(icar_dir, category="crop")
    if os.path.exists(subsidy_dir) and os.listdir(subsidy_dir):
        ingest_pdf_directory(subsidy_dir, category="subsidy")

    stats = get_collection_stats()
    print(f"\n📊 Total knowledge base: {stats['total_documents']} documents")
    print("✅ Ingestion complete!")
