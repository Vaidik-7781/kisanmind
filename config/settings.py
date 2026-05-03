import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ───────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ─── LLM (Groq - Free) ──────────────────────────────────────
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL         = "llama-3.3-70b-versatile"
GROQ_BASE_URL      = "https://api.groq.com/openai/v1"

# ─── Vision (Gemini Flash - Free) ───────────────────────────
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL       = "gemini-2.0-flash-exp"

# ─── Weather (OpenWeatherMap - Free) ────────────────────────
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_URL     = "https://api.openweathermap.org/data/2.5"

# ─── Supabase (Free tier) ───────────────────────────────────
SUPABASE_URL       = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY       = os.getenv("SUPABASE_KEY", "")

# ─── ChromaDB (Local, Free) ─────────────────────────────────
CHROMA_PERSIST_DIR = "./chroma_db"
CHROMA_COLLECTION  = "kisanmind_knowledge"

# ─── Voice ──────────────────────────────────────────────────
WHISPER_MODEL      = "base"           # runs locally, free
DEFAULT_LANGUAGE   = "hi"             # Hindi default

# ─── Mandi / Market ─────────────────────────────────────────
AGMARKNET_BASE_URL = "https://agmarknet.gov.in"
DATA_GOV_API_KEY   = os.getenv("DATA_GOV_API_KEY", "")   # free at data.gov.in

# ─── App ────────────────────────────────────────────────────
DEBUG              = os.getenv("DEBUG", "false").lower() == "true"
MAX_HISTORY_TURNS  = 10
CONFIDENCE_THRESHOLD = 0.70   # below this → escalate to human
