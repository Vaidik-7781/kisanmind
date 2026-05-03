"""
KisanMind — Agentic AI Farmer Advisory System
Entry point. Run: python main.py
"""

import asyncio
import logging
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

from interface.telegram_bot import create_app
from knowledge_base.ingest import ingest_seed_knowledge
from tools.rag_tool import get_collection_stats
from config.settings import TELEGRAM_BOT_TOKEN, GROQ_API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)


def check_environment():
    """Validate required env vars before starting."""
    missing = []
    warnings = []

    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not GEMINI_API_KEY:
        warnings.append("GEMINI_API_KEY (vision disabled — crop photo analysis won't work)")

    if missing:
        print("\n❌ MISSING REQUIRED ENV VARS:")
        for m in missing:
            print(f"   • {m}")
        print("\nCreate a .env file. See .env.example for reference.")
        sys.exit(1)

    if warnings:
        print("\n⚠️  OPTIONAL ENV VARS NOT SET:")
        for w in warnings:
            print(f"   • {w}")


def bootstrap_knowledge_base():
    """Ingest seed knowledge if DB is empty."""
    stats = get_collection_stats()
    if stats["total_documents"] == 0:
        print("📚 Knowledge base empty — ingesting seed knowledge...")
        ingest_seed_knowledge()
    else:
        print(f"📚 Knowledge base ready ({stats['total_documents']} documents)")


def main():
    print("""
╔══════════════════════════════════════════╗
║         🌾  KisanMind  v1.0              ║
║   Agentic AI Advisor for Indian Farmers  ║
╚══════════════════════════════════════════╝
    """)

    # Step 1 — check env
    print("🔍 Checking environment...")
    check_environment()
    print("✅ Environment OK\n")

    # Step 2 — bootstrap knowledge base
    print("📖 Checking knowledge base...")
    bootstrap_knowledge_base()
    print()

    # Step 3 — start bot
    print("🤖 Starting Telegram bot...")
    app = create_app()
    print("✅ Bot running. Press Ctrl+C to stop.\n")
    print("─" * 45)
    app.run_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
