"""
Boot verification — runs a few seconds after login to produce a plain-language
boot report the user (or a fresh Claude session) can read to know if the
overnight/at-boot pipeline succeeded.

Writes: data/boot_report.md
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
REPORT = DATA / "boot_report.md"
STATUS = DATA / "monitor_status.json"
LOG = DATA / "monitor.log"


def is_task_registered(name: str) -> bool:
    try:
        r = subprocess.run(
            ["schtasks", "/Query", "/TN", name],
            capture_output=True, text=True, timeout=8,
        )
        return r.returncode == 0
    except Exception:
        return False


def read_status() -> dict:
    if not STATUS.exists():
        return {}
    try:
        with open(STATUS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def tail(path: Path, n: int = 12) -> str:
    if not path.exists():
        return "(no log yet)"
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception:
        return "(unreadable)"


def main() -> None:
    DATA.mkdir(exist_ok=True)

    # Give the monitor up to 40s to reach a stable state
    for _ in range(20):
        status = read_status()
        if status.get("state") in {"monitoring", "login_pending", "error"}:
            break
        time.sleep(2)

    status = read_status()
    reminders_registered = is_task_registered("DepotAgent_TaskReminders")

    state = status.get("state", "unknown")
    verdict_map = {
        "monitoring":       ("✅", "Monitor is running and polling both sources."),
        "waiting_for_login":("⏳", "Monitor launched Chrome — auto-login still in progress."),
        "login_pending":    ("🟠", "Chrome did not auto-sign-in. Sign in to Autoway once so Chrome saves the password."),
        "starting":         ("⚪", "Monitor is still initialising."),
        "error":            ("🔴", f"Monitor error: {status.get('error','?')}"),
        "unknown":          ("⚫", "Monitor status file not found. It may not have started."),
    }
    icon, verdict = verdict_map.get(state, ("⚫", f"Unknown state: {state}"))

    lines = [
        f"# Depot Agent — Boot Report",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"## Monitor  {icon}",
        f"- **State**: `{state}`",
        f"- **Autoway URL**: {status.get('autoway_url','—')}",
        f"- **Autoway unread**: {status.get('autoway_unread','—')}",
        f"- **Outlook**: {status.get('outlook','—')}",
        f"- **Last poll**: {status.get('last_poll','—')}",
        f"- **Verdict**: {verdict}",
        "",
        f"## Task Reminders  {'✅' if reminders_registered else '🔴'}",
        f"- Windows Task Scheduler entry `DepotAgent_TaskReminders`: "
        f"{'registered — will fire daily at 08:00' if reminders_registered else 'NOT registered'}",
        "",
        f"## Recent monitor log",
        "```",
        tail(LOG),
        "```",
    ]

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
