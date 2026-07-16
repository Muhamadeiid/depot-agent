"""
End-of-Day Personal Digest — Cairo Metro Line 1 Depot Agent.

Fires at 17:00 daily via Windows Task Scheduler. Builds a WhatsApp summary of:
  - Tomorrow's maintenance (how many trains, which codes)
  - Pending tasks (with any that are late highlighted)
  - Today's new emails (count + who from — no bodies)
  - Trains available for service tomorrow
  - Overdue tasks (Pending, due_date < today)

Sends to the phone in config.json → `manager_phone`. If that field is empty,
the script logs a warning and exits cleanly (won't spam anyone).
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

# UTF-8 stdout so emoji don't crash on Windows cp1252 consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from data_manager import DataManager, MAINTENANCE_TYPES
from daily_reminders import send_via_whatsapp

BASE = Path(__file__).resolve().parent
STREAM_FILE = BASE / "data" / "inbox_stream.jsonl"


def _tomorrow_maintenance(dm: DataManager, tomorrow: date) -> list[dict]:
    """Return the list of scheduled maintenance entries for tomorrow."""
    grid = dm.get_schedule_grid()
    day_entries = grid.get(tomorrow.isoformat(), {})
    return [
        {"train_id": tid, "code": code, "code_name": MAINTENANCE_TYPES.get(code, code)}
        for tid, code in day_entries.items()
    ]


def _todays_inbox_events(today: date) -> list[dict]:
    """Return today's new inbox events (from monitor's stream file)."""
    if not STREAM_FILE.exists():
        return []
    out: list[dict] = []
    today_iso = today.isoformat()
    try:
        with open(STREAM_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                seen_at = ev.get("seen_at", "")
                if seen_at.startswith(today_iso):
                    out.append(ev)
    except Exception:
        pass
    return out


def _pending_and_overdue(dm: DataManager, today: date, tomorrow: date):
    """Return (pending_tomorrow_and_later, overdue). Overdue = due < today, Pending."""
    tasks = [t for t in dm.get_tasks() if str(t.get("status", "")).lower() == "pending"]
    pending: list[dict] = []
    overdue: list[dict] = []
    for t in tasks:
        try:
            due = datetime.fromisoformat(t["due_date"]).date()
        except Exception:
            continue
        if due < today:
            overdue.append(t)
        else:
            pending.append(t)
    pending.sort(key=lambda t: t["due_date"])
    overdue.sort(key=lambda t: t["due_date"])
    return pending, overdue


def _available_trains_tomorrow(dm: DataManager, tomorrow: date) -> int:
    """Trains NOT scheduled for maintenance tomorrow."""
    grid = dm.get_schedule_grid()
    day_entries = grid.get(tomorrow.isoformat(), {})
    all_trains = {t["id"] for t in dm.get_trains()}
    in_maintenance = set(day_entries.keys())
    return len(all_trains - in_maintenance)


def build_digest(dm: DataManager, today: date | None = None) -> str:
    today = today or date.today()
    tomorrow = today + timedelta(days=1)

    maint = _tomorrow_maintenance(dm, tomorrow)
    pending, overdue = _pending_and_overdue(dm, today, tomorrow)
    events = _todays_inbox_events(today)
    available = _available_trains_tomorrow(dm, tomorrow)
    total_trains = len(dm.get_trains())

    lines = [
        f"📊 *End-of-Day Digest — {today.strftime('%A %d %b %Y')}*",
        "",
    ]

    # 1. Tomorrow's maintenance
    if maint:
        codes = Counter(m["code"] for m in maint)
        codes_str = ", ".join(f"{n}×{c}" for c, n in codes.most_common())
        lines.append(f"📅 *Tomorrow ({tomorrow.strftime('%a %d %b')}):* {len(maint)} train(s) — {codes_str}")
        for m in maint[:10]:
            lines.append(f"   • Train {m['train_id']} — {m['code']} ({m['code_name']})")
        if len(maint) > 10:
            lines.append(f"   … and {len(maint) - 10} more")
    else:
        lines.append(f"📅 *Tomorrow ({tomorrow.strftime('%a %d %b')}):* No maintenance scheduled ✅")

    lines.append("")

    # 2. Available trains
    lines.append(f"🚂 *Available for service tomorrow:* {available}/{total_trains}")
    lines.append("")

    # 3. Overdue (biggest attention grabber)
    if overdue:
        lines.append(f"⚠️ *OVERDUE ({len(overdue)}):*")
        for t in overdue[:5]:
            days_late = (today - datetime.fromisoformat(t["due_date"]).date()).days
            lines.append(f"   • {t['title']} — {days_late}d late (due {t['due_date']})")
        if len(overdue) > 5:
            lines.append(f"   … and {len(overdue) - 5} more")
        lines.append("")

    # 4. Pending tasks
    if pending:
        due_today = [t for t in pending if t["due_date"] == today.isoformat()]
        due_tomorrow = [t for t in pending if t["due_date"] == tomorrow.isoformat()]
        lines.append(f"📋 *Pending tasks:* {len(pending)} ({len(due_today)} due today, {len(due_tomorrow)} due tomorrow)")
        # Show next 5
        for t in pending[:5]:
            lines.append(f"   • {t['title']} — due {t['due_date']}")
        if len(pending) > 5:
            lines.append(f"   … and {len(pending) - 5} more")
        lines.append("")

    # 5. Today's inbox activity
    if events:
        senders = Counter(ev.get("from", "?") for ev in events)
        lines.append(f"📬 *New emails today:* {len(events)} from {len(senders)} sender(s)")
        for sender, n in senders.most_common(5):
            short = (sender[:35] + "…") if len(sender) > 35 else sender
            lines.append(f"   • {short} ({n})")
        if len(senders) > 5:
            lines.append(f"   … +{len(senders) - 5} other sender(s)")
    else:
        lines.append("📬 *New emails today:* none detected by the monitor")

    lines.append("")
    lines.append("— Depot Agent")
    return "\n".join(lines)


def main() -> int:
    dm = DataManager()
    cfg = dm.load_config()

    phone = (cfg.get("manager_phone") or "").strip()
    if not phone:
        print(
            f"[{datetime.now().isoformat(timespec='seconds')}] "
            "manager_phone not set in config.json — skipping digest. "
            "Add it in Settings tab to receive the 17:00 digest."
        )
        return 0

    digest = build_digest(dm)
    print(f"[{datetime.now().isoformat(timespec='seconds')}] sending digest to {phone}")
    print("--- digest preview ---")
    print(digest)
    print("--- end preview ---")

    ok = send_via_whatsapp(phone, digest)
    if ok:
        print("Digest sent ✅")
        return 0
    print("Digest send FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
