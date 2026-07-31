"""Tiny per-day run marker.

Used by scheduled scripts to avoid double-sending when both the daily trigger
AND the AtLogOn catch-up trigger fire on the same day.
"""
import json
from datetime import date
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent / "data" / "run_state.json"


def _load() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        # utf-8-sig transparently strips a BOM if a human edited the file
        # with Notepad (which writes BOMs by default on Windows).
        return json.loads(STATE_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def already_ran_today(name: str) -> bool:
    return _load().get(name) == date.today().isoformat()


def mark_ran_today(name: str) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = _load()
    data[name] = date.today().isoformat()
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
