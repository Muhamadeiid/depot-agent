"""
Daily task reminders — Cairo Metro Line 1 Depot Agent.

For each Pending task where (due_date - remind_days_before) == today,
sends a WhatsApp message to the task's recipient via WhatsApp Desktop.
A `reminder_sent_for` marker on the task prevents duplicate sends the same day.

Run daily at 08:00 via Windows Task Scheduler (install_scheduler.bat).
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

# Force UTF-8 stdout so emoji/arrows in log lines don't blow up on Windows cp1252 consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from data_manager import DataManager


def _try_import_gui():
    try:
        import pyautogui
        import pygetwindow as gw
        import pyperclip
        # Disable the corner-of-screen fail-safe. This script runs headlessly at
        # 08:00 via Task Scheduler; if the mouse happens to sit near a corner
        # the fail-safe would abort the send. Nothing else in this script relies
        # on it, and the send is confined to the WhatsApp window.
        pyautogui.FAILSAFE = False
        return pyautogui, gw, pyperclip
    except ImportError:
        return None, None, None


def _find_and_focus_whatsapp():
    """Find the real WhatsApp Desktop window (not a Chrome tab) and bring it to focus."""
    _, gw, _ = _try_import_gui()
    if gw is None:
        return None
    # WhatsApp Desktop's window title is exactly "WhatsApp" — a Chrome tab shows
    # "WhatsApp - Google Chrome". Prefer exact match.
    for w in gw.getAllWindows():
        try:
            if (w.title or "").strip() == "WhatsApp":
                try:
                    if w.isMinimized:
                        w.restore()
                except Exception:
                    pass
                try:
                    w.activate()
                except Exception:
                    # Windows sometimes refuses activate() — retry via minimize+restore
                    try:
                        w.minimize(); time.sleep(0.2); w.restore()
                    except Exception:
                        pass
                time.sleep(0.6)
                return w
        except Exception:
            continue
    return None


def send_via_whatsapp(recipient: str, message: str) -> bool:
    """
    Open WhatsApp Desktop with the given phone + message pre-filled, focus the
    window, and press Enter to send. This uses whatsapp://send?phone=X&text=Y
    which fills the composer for us — no fragile click-and-paste at guessed
    screen coordinates.
    Contact-name recipients still fall back to Ctrl+F search + paste.
    """
    import urllib.parse

    pyautogui, gw, pyperclip = _try_import_gui()
    if pyautogui is None:
        print("pyautogui not available — cannot drive WhatsApp Desktop.")
        return False

    phone_like = re.fullmatch(r"\+?\d[\d\s\-]{6,}", recipient.strip())

    if phone_like:
        phone = re.sub(r"[^\d]", "", recipient)
        # Egyptian mobile numbers entered as 01XXXXXXXXX → normalise to 201XXXXXXXXX
        if phone.startswith("01") and len(phone) == 11:
            phone = "20" + phone[1:]
        text_q = urllib.parse.quote(message)
        # Use os.startfile so cmd doesn't split the URL on the '&' between params.
        import os as _os
        try:
            _os.startfile(f"whatsapp://send?phone={phone}&text={text_q}")
        except OSError as e:
            print(f"whatsapp:// launch failed: {e}")
            return False
        # WhatsApp needs a real moment to open the chat and populate the composer.
        time.sleep(7)
        win = _find_and_focus_whatsapp()
        if win is None:
            print("Couldn't find the WhatsApp Desktop window after opening chat.")
            return False
        # Extra beat so keystrokes land in the composer, not still-loading UI.
        time.sleep(1)
        pyautogui.press("enter")
        time.sleep(0.5)
        return True

    # Contact-name path: search inside WhatsApp, then paste + enter.
    win = _find_and_focus_whatsapp()
    if win is None:
        print("WhatsApp Desktop not open.")
        return False
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.8)
    pyperclip.copy(recipient)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1.2)
    pyautogui.press("enter")
    time.sleep(1)
    pyautogui.press("escape")
    time.sleep(0.5)
    pyperclip.copy(message)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)
    pyautogui.press("enter")
    time.sleep(0.5)
    return True


def build_message(task: dict, employees_by_id: dict) -> str:
    priority = str(task.get("priority", "")).upper() or "MEDIUM"
    train = task.get("train_id", "")
    train_line = f"🚂 Train {train}\n" if train else ""
    due = task.get("due_date", "")
    assignees = ", ".join(
        employees_by_id.get(i, {}).get("name", i)
        for i in task.get("assigned_to_ids", [])
    )
    desc = (task.get("description") or "").strip()
    lines = [
        "🔔 *Depot Reminder*",
        f"*{task.get('title','(untitled)')}*",
        train_line + f"📅 Due: {due}   ⚑ {priority}",
    ]
    if assignees:
        lines.append(f"👷 Assigned: {assignees}")
    if desc:
        lines.append("")
        lines.append(desc)
    lines.append("")
    lines.append(f"— task {task.get('id','')}")
    return "\n".join(lines)


def status_is_pending(task: dict) -> bool:
    return str(task.get("status", "")).strip().lower() in {"pending", ""}


def is_due_for_reminder(task: dict, today: date) -> bool:
    if not status_is_pending(task):
        return False
    if not task.get("recipient"):
        return False
    if task.get("reminder_sent_for") == today.isoformat():
        return False
    try:
        due = datetime.fromisoformat(task["due_date"]).date()
    except Exception:
        return False
    raw = task.get("remind_days_before")
    if isinstance(raw, (list, tuple)):
        offsets = [int(x) for x in raw]
    elif raw in (None, ""):
        offsets = [0]
    else:
        offsets = [int(raw)]
    return (due - today).days in offsets


def main() -> int:
    dm = DataManager()
    today = date.today()
    tasks = dm.get_tasks()
    employees = {e["id"]: e for e in dm.get_employees()}

    due_tasks = [t for t in tasks if is_due_for_reminder(t, today)]
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {len(due_tasks)} task(s) due for reminder today")

    if not due_tasks:
        return 0

    sent = 0
    for t in due_tasks:
        try:
            recipient = t["recipient"]
            print(f"→ Reminding {recipient} about task {t['id']} ({t['title']})")
            if not send_via_whatsapp(recipient, build_message(t, employees)):
                continue
            dm.update_task(t["id"], reminder_sent_for=today.isoformat())
            sent += 1
        except Exception as e:
            print(f"  ✗ error: {e}")

    print(f"Done. Sent {sent}/{len(due_tasks)} reminders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
