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


PRIORITY_LABEL = {"high": "HIGH 🔴", "medium": "MEDIUM 🟡", "low": "LOW 🟢"}


def build_message(task: dict, employees_by_id: dict, recipient_emp: dict | None = None) -> str:
    """Build a professional English WhatsApp reminder.

    recipient_emp is the specific employee this copy is being sent to (if known),
    so we can greet them by name.
    """
    priority_raw = str(task.get("priority", "medium")).lower()
    priority = PRIORITY_LABEL.get(priority_raw, priority_raw.upper())
    train = task.get("train_id", "")
    due = task.get("due_date", "")
    try:
        due_dt = datetime.fromisoformat(due).date()
        days_left = (due_dt - date.today()).days
        if days_left == 0:
            due_hint = "today"
        elif days_left == 1:
            due_hint = "tomorrow"
        elif days_left > 1:
            due_hint = f"in {days_left} days"
        else:
            due_hint = f"OVERDUE by {-days_left} day(s)"
    except Exception:
        due_hint = ""

    assignee_names = [
        employees_by_id.get(i, {}).get("name", "") for i in task.get("assigned_to_ids", [])
    ]
    assignee_names = [n for n in assignee_names if n]
    desc = (task.get("description") or "").strip()
    title = task.get("title", "(untitled)")
    manager = ""
    try:
        manager = DataManager().load_config().get("manager_name", "")
    except Exception:
        pass

    greeting_name = (recipient_emp or {}).get("name", "").strip()
    greet = f"Dear {greeting_name}," if greeting_name else "Dear colleague,"

    lines = [
        "🚇 *Cairo Metro Line 1 — Depot*",
        "",
        greet,
        "You have been assigned the following task:",
        "",
        f"📌 *Task:* {title}",
    ]
    if train:
        lines.append(f"🚂 *Train:* {train}")
    if due:
        due_line = f"📅 *Due:* {due}"
        if due_hint:
            due_line += f"  ({due_hint})"
        lines.append(due_line)
    lines.append(f"⚑ *Priority:* {priority}")
    if assignee_names:
        lines.append(f"👷 *Assigned to:* {', '.join(assignee_names)}")
    if desc:
        lines += ["", "📝 *Details:*", desc]
    lines += [
        "",
        "Please confirm receipt and complete the task on time.",
        "Thank you for your cooperation.",
    ]
    if manager:
        lines.append(f"— {manager}")
    lines.append(f"[Ref: {task.get('id','')}]")
    return "\n".join(lines)


def polish_with_claude(message: str, api_key: str) -> str:
    """Optional: ask Claude to polish the message into professional Arabic.
    Falls back silently to the original message on any error.
    """
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": (
                    "Rewrite the following WhatsApp reminder in concise, "
                    "professional English for a maintenance technician at "
                    "Cairo Metro Line 1 Depot. Preserve every fact (task "
                    "title, train number, date, priority, details, names, "
                    "reference id) and keep the emojis. Return the message "
                    "only — no preamble, no explanation.\n\n"
                    f"Message:\n{message}"
                )
            }],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content).strip()
        return text or message
    except Exception as e:
        print(f"  (Claude polish skipped: {e})")
        return message


def _collect_recipient_phones(task: dict, employees_by_id: dict) -> list[tuple[str, dict | None]]:
    """Return a de-duplicated list of (phone, employee_dict_or_None) to notify.

    Combines phones of every assigned employee with the task's manual `recipient`
    field. Contact-name recipients (non-numeric) are kept as-is.
    """
    seen: set[str] = set()
    out: list[tuple[str, dict | None]] = []
    for emp_id in task.get("assigned_to_ids", []):
        emp = employees_by_id.get(emp_id)
        if not emp:
            continue
        phone = (emp.get("phone") or "").strip()
        if phone and phone not in seen:
            seen.add(phone)
            out.append((phone, emp))
    manual = (task.get("recipient") or "").strip()
    if manual and manual not in seen:
        seen.add(manual)
        out.append((manual, None))
    return out


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


def notify_task_now(task_id: str) -> tuple[int, int]:
    """Immediately send WhatsApp to every recipient of a single task.

    Returns (sent_count, total_recipients). Used by the UI's "Notify Now" flow.
    Safe to call from a subprocess so the Streamlit UI doesn't freeze while
    pyautogui drives WhatsApp Desktop.
    """
    dm = DataManager()
    task = next((t for t in dm.get_tasks() if t.get("id") == task_id), None)
    if not task:
        print(f"notify_task_now: task {task_id} not found")
        return (0, 0)

    employees = {e["id"]: e for e in dm.get_employees()}
    api_key = (dm.load_config() or {}).get("anthropic_api_key", "").strip()
    recipients = _collect_recipient_phones(task, employees)

    if not recipients:
        print(f"notify_task_now: task {task_id} has no recipients")
        return (0, 0)

    sent = 0
    for phone, emp in recipients:
        msg = build_message(task, employees, recipient_emp=emp)
        if api_key:
            msg = polish_with_claude(msg, api_key)
        label = f"{emp['name']} ({phone})" if emp else phone
        print(f"→ Notifying {label}")
        if send_via_whatsapp(phone, msg):
            sent += 1
            time.sleep(2)
        else:
            print(f"  ✗ send failed for {label}")

    print(f"notify_task_now: sent {sent}/{len(recipients)} for task {task_id}")
    return (sent, len(recipients))


def main() -> int:
    dm = DataManager()
    today = date.today()
    tasks = dm.get_tasks()
    employees = {e["id"]: e for e in dm.get_employees()}
    api_key = (dm.load_config() or {}).get("anthropic_api_key", "").strip()

    due_tasks = [t for t in tasks if is_due_for_reminder(t, today)]
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {len(due_tasks)} task(s) due for reminder today")

    if not due_tasks:
        return 0

    sent_msgs = 0
    tasks_notified = 0
    for t in due_tasks:
        try:
            recipients = _collect_recipient_phones(t, employees)
            if not recipients:
                print(f"  ✗ task {t['id']}: no recipients (no assignee phones, no manual recipient)")
                continue

            print(f"→ Task {t['id']} ({t['title']}) → {len(recipients)} recipient(s)")

            task_had_success = False
            for phone, emp in recipients:
                msg = build_message(t, employees, recipient_emp=emp)
                if api_key:
                    msg = polish_with_claude(msg, api_key)
                label = f"{emp['name']} ({phone})" if emp else phone
                print(f"   → {label}")
                if send_via_whatsapp(phone, msg):
                    sent_msgs += 1
                    task_had_success = True
                    # Small pause so WhatsApp Desktop settles before the next send.
                    time.sleep(2)
                else:
                    print(f"     ✗ send failed for {label}")

            if task_had_success:
                dm.update_task(t["id"], reminder_sent_for=today.isoformat())
                tasks_notified += 1
        except Exception as e:
            print(f"  ✗ error on task {t.get('id','?')}: {e}")

    print(f"Done. {tasks_notified}/{len(due_tasks)} task(s) notified · {sent_msgs} WhatsApp message(s) sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
