"""
In-memory conversation history per farmer.
Kept in RAM (resets on restart). For production, persist to Supabase/Redis.
"""

from collections import defaultdict
from config.settings import MAX_HISTORY_TURNS

# { telegram_id: [ {role, content}, ... ] }
_store: dict[int, list] = defaultdict(list)


def add_message(telegram_id: int, role: str, content: str):
    """role = 'user' | 'assistant'"""
    history = _store[telegram_id]
    history.append({"role": role, "content": content})
    # Trim to last N turns (N*2 messages)
    if len(history) > MAX_HISTORY_TURNS * 2:
        _store[telegram_id] = history[-(MAX_HISTORY_TURNS * 2):]


def get_history(telegram_id: int) -> list[dict]:
    return list(_store[telegram_id])


def clear_history(telegram_id: int):
    _store[telegram_id] = []


def get_last_user_message(telegram_id: int) -> str:
    history = _store[telegram_id]
    for msg in reversed(history):
        if msg["role"] == "user":
            return msg["content"]
    return ""
