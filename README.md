# 🌾 KisanMind — Agentic AI Farmer Advisory System

> **100% free stack. Zero rupees. Real impact.**
> Multi-agent AI system for Indian farmers via Telegram.

---

## What it does

| Send this | Get this |
|---|---|
| 📸 Photo of sick crop | Disease name, treatment, dosage |
| 🎤 Voice note in Hindi | Answer in Hindi voice |
| "wheat mandi bhav" | Live price + 14-day forecast |
| "aaj ka mausam" | Weather + farm-specific alerts |
| "kya ugaun is season" | Top 3 crop recommendations |
| "PM-KISAN kaise apply karein" | Step-by-step subsidy guide |

---

## Architecture

```
Farmer (Telegram)
      │
      ▼
 Orchestrator ──── classifies intent ────────────────────┐
      │                                                   │
      ├──▶ Vision Agent      (Gemini Vision)              │
      ├──▶ Climate Agent     (OpenWeatherMap)             │
      ├──▶ Market Agent      (AGMARKNET + Prophet)        │
      ├──▶ Advisory Agent    (Groq LLaMA + RAG)          │
      ├──▶ Crop Plan Agent   (Groq LLaMA + ICAR RAG)     │
      └──▶ Finance Agent     (Groq LLaMA + Scheme RAG)   │
                                                          │
ChromaDB (local RAG) ◀── ICAR docs, scheme PDFs ─────────┘
Supabase (farmer profiles, history)
```

---

## Free Stack

| Component | Tool | Cost |
|---|---|---|
| Bot interface | Telegram Bot API | Free |
| LLM brain | Groq (LLaMA 3.3 70B) | Free |
| Vision / disease | Gemini 2.0 Flash | Free |
| Voice input | OpenAI Whisper (local) | Free |
| Voice output | gTTS | Free |
| Vector DB / RAG | ChromaDB (local) | Free |
| Farmer profiles | Supabase free tier | Free |
| Weather | OpenWeatherMap | Free |
| Market prices | AGMARKNET / data.gov.in | Free |
| Hosting | Railway.app | Free |

---

## Setup (15 minutes)

### 1. Clone & install

```bash
git clone https://github.com/yourname/kisanmind
cd kisanmind
pip install -r requirements.txt
```

> **Note:** First run downloads ~500MB total (Whisper model + sentence-transformers). One-time only.

### 2. Get free API keys

| Service | Where | Time |
|---|---|---|
| Telegram token | [@BotFather](https://t.me/BotFather) → `/newbot` | 2 min |
| Groq API key | [console.groq.com](https://console.groq.com) | 2 min |
| Gemini API key | [aistudio.google.com](https://aistudio.google.com/app/apikey) | 2 min |
| OpenWeatherMap | [openweathermap.org/api](https://openweathermap.org/api) | 3 min |
| Supabase | [supabase.com](https://supabase.com) → New Project | 5 min |

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your keys
```

### 4. Setup Supabase database

1. Go to Supabase → your project → SQL Editor
2. Copy contents of `supabase_schema.sql`
3. Click Run

### 5. Build knowledge base

```bash
python -m knowledge_base.ingest
```

Output:
```
✅ Ingested 19 seed documents
📊 Total knowledge base: 19 documents
```

To add your own crop manuals: drop PDFs into `knowledge_base/icar_docs/` and re-run ingest.

### 6. Run

```bash
python main.py
```

```
╔══════════════════════════════════════════╗
║         🌾  KisanMind  v1.0              ║
║   Agentic AI Advisor for Indian Farmers  ║
╚══════════════════════════════════════════╝

🔍 Checking environment... ✅ OK
📖 Checking knowledge base... 📚 19 documents
🤖 Starting Telegram bot... ✅ Running
```

Open Telegram → find your bot → `/start`

---

## Commands

```
/start              — Welcome + feature overview
/weather            — Today's weather + farm alerts
/price [crop]       — Mandi price + 14-day forecast
/plan               — Crop planning for this season
/schemes            — Govt subsidies + schemes
/setlocation [city] — Set your city (enables local data)
/addcrop [name]     — Register crop you're growing
/setlang [code]     — Change language (hi/en/mr/te/ta/pa/kn/bn)
/profile            — View your farmer profile
/reset              — Clear conversation history
```

**Special inputs:**
- 📸 Send any crop photo → automatic disease detection
- 🎤 Send voice note → transcribed + answered in your language
- 📍 Share location → enables precise weather + nearby mandi prices

---

## Supported Languages

| Code | Language |
|---|---|
| `hi` | Hindi (default) |
| `en` | English |
| `mr` | Marathi |
| `te` | Telugu |
| `ta` | Tamil |
| `pa` | Punjabi |
| `kn` | Kannada |
| `bn` | Bengali |

---

## Deploy to Railway (free)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login + deploy
railway login
railway new
railway up
```

Set env vars in Railway dashboard → Variables. Done.

---

## Run Tests

```bash
python tests/test_agents.py
```

```
╔══════════════════════════════════════════╗
║     KisanMind — Test Suite               ║
╚══════════════════════════════════════════╝

TestOrchestrator ... ✅
TestWeatherTool  ... ✅
TestMandiTool    ... ✅
...
Tests run: 42 | Failures: 0 | Status: ✅ PASSED
```

---

## Project Structure

```
kisanmind/
├── main.py                      ← Entry point
├── agents/
│   ├── orchestrator.py          ← Master router (intent classification)
│   ├── vision_agent.py          ← Crop disease from photo
│   ├── climate_agent.py         ← Weather + farm alerts
│   ├── market_agent.py          ← Mandi prices + forecasting
│   ├── advisory_agent.py        ← General Q&A (LLM + RAG)
│   ├── crop_plan_agent.py       ← Seasonal crop recommendations
│   └── finance_agent.py         ← Subsidies + loans
├── tools/
│   ├── weather_tool.py          ← OpenWeatherMap wrapper
│   ├── mandi_tool.py            ← AGMARKNET scraper
│   ├── vision_tool.py           ← Gemini Vision API
│   ├── voice_tool.py            ← Whisper ASR + gTTS
│   └── rag_tool.py              ← ChromaDB semantic search
├── memory/
│   ├── farmer_profile.py        ← Supabase persistent profiles
│   └── conversation.py          ← In-memory chat history
├── knowledge_base/
│   ├── ingest.py                ← Load PDFs + seed data → ChromaDB
│   ├── pesticide_list.json      ← Approved/banned chemicals
│   ├── icar_docs/               ← Drop ICAR PDFs here
│   └── subsidy_schemes/         ← Drop scheme PDFs here
├── models/
│   ├── disease_classifier/      ← Local HuggingFace model (optional)
│   └── price_forecaster.py      ← Prophet/heuristic price prediction
├── interface/
│   ├── telegram_bot.py          ← Bot handlers
│   └── message_formatter.py     ← Text/voice response formatting
├── config/settings.py           ← All configuration
├── tests/test_agents.py         ← Full test suite (42 tests)
├── supabase_schema.sql          ← Run once in Supabase
├── requirements.txt
├── Dockerfile
├── railway.toml
└── .env.example
```

---

## Adding Knowledge

Drop any agricultural PDF into `knowledge_base/icar_docs/` and run:

```bash
python -m knowledge_base.ingest
```

Good sources (all free):
- [ICAR Publications](https://icar.org.in/content/icar-publications) — crop manuals
- [data.gov.in](https://data.gov.in) — scheme documents
- [CIB&RC](http://cibrc.nic.in) — pesticide lists
- [KVK portals](https://kvk.icar.gov.in) — regional crop guides

---

## Emergency Contacts (hardcoded in bot)

| Service | Number |
|---|---|
| Kisan Call Centre | 1800-180-1551 |
| Pesticide Poisoning | 1800-425-1213 |
| PM-KISAN Helpline | 155261 |
| PMFBY Helpline | 1800-200-7710 |

---

## License

MIT — free to use, modify, deploy.

Built with ❤️ for 600 million Indian farmers.

---

## Developer

**Vaidik Gupta**
B.Tech — Electronics & Computer Science Engineering, KIIT University
[github.com/Vaidik-7781](https://github.com/Vaidik-7781)
