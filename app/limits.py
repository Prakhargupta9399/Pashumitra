"""
app/limits.py
In-memory rate limiting for Phase 1 (no Redis needed).
Free tier: 3 queries per phone per day.
Premium: unlimited.
"""
import os
from datetime import date
from typing import Dict, Tuple

# {phone: (date_str, count)}
_store: Dict[str, Tuple[str, int]] = {}

DAILY_FREE_LIMIT = int(os.getenv("DAILY_FREE_LIMIT", "3"))


def check_and_increment(phone: str, is_premium: bool = False) -> bool:
    """
    Returns True if query is allowed (and increments counter).
    Returns False if daily limit exceeded.
    """
    if is_premium:
        return True

    today = str(date.today())
    stored_date, count = _store.get(phone, (today, 0))

    # Reset counter on new day
    if stored_date != today:
        count = 0

    if count >= DAILY_FREE_LIMIT:
        return False

    _store[phone] = (today, count + 1)
    return True


def get_usage(phone: str) -> dict:
    """Return current usage info for a phone number."""
    today = str(date.today())
    stored_date, count = _store.get(phone, (today, 0))

    if stored_date != today:
        count = 0

    return {
        "phone": phone,
        "used":  count,
        "limit": DAILY_FREE_LIMIT,
        "remaining": max(0, DAILY_FREE_LIMIT - count),
        "date": today,
    }


def reset(phone: str) -> None:
    """Reset usage for a phone (admin / testing use)."""
    _store.pop(phone, None)
