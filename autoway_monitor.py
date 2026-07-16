"""
Depot Agent — background monitor.

Launches Chrome (debug port 9222), opens Autoway, waits for Chrome's saved-password
autofill+autosubmit to complete the login, clicks the mail/envelope icon, then polls
Autoway AND Outlook (if running) every POLL_SECS. Never types passwords.

State is written to:
  data/monitor_status.json  — current heartbeat (dashboard reads this)
  data/inbox_stream.jsonl   — append-only log of new emails seen
  data/monitor.log          — text log
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
CONFIG_FILE = BASE / "config.json"

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# Chrome 136+ refuses --remote-debugging-port when user-data-dir is the default
# profile (security fix). We use a dedicated profile inside data/ — the user does
# a one-time Autoway login the first time, then Chrome autofill takes over.
CHROME_PROFILE = str(Path(__file__).resolve().parent / "data" / "chrome_profile")
CDP_PORT = 9222

POLL_SECS = 300          # 5 min between polls
LOGIN_WAIT_SECS = 120    # how long to wait for auto-login
STATUS_FILE = DATA / "monitor_status.json"
STREAM_FILE = DATA / "inbox_stream.jsonl"
LOG_FILE = DATA / "monitor.log"


def log(msg: str) -> None:
    DATA.mkdir(exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_status(**kwargs) -> None:
    DATA.mkdir(exist_ok=True)
    kwargs["updated_at"] = datetime.now().isoformat()
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(kwargs, f, ensure_ascii=False, indent=2)


def chrome_cdp_up() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=2).read()
        return True
    except Exception:
        return False


def launch_chrome() -> None:
    if chrome_cdp_up():
        log("Chrome CDP already running on port 9222")
        return
    log("Launching Chrome with remote debugging...")
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [CHROME_PATH, f"--remote-debugging-port={CDP_PORT}", f"--user-data-dir={CHROME_PROFILE}"],
        creationflags=flags,
        close_fds=True,
    )
    for _ in range(30):
        if chrome_cdp_up():
            log("Chrome CDP is up")
            return
        time.sleep(1)
    log("WARNING: Chrome CDP did not come up within 30s")


def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _is_logged_in(url: str) -> bool:
    cur = (url or "").lower()
    return "autoway.hyundai.net" in cur and not any(
        k in cur for k in ("login", "signin", "auth")
    )


def find_autoway_page(ctx, cfg: dict):
    """Return the existing Autoway tab, or open a new one. Never closes Playwright."""
    autoway_url = (cfg.get("webmail") or {}).get("url") or "https://autoway.hyundai.net/main/"
    for pg in ctx.pages:
        if "autoway.hyundai.net" in pg.url:
            return pg
    page = ctx.new_page()
    try:
        page.goto(autoway_url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        log(f"Autoway navigate error: {e}")
    return page


def wait_for_login(page, deadline_secs: int = LOGIN_WAIT_SECS) -> bool:
    """Poll the page URL until it indicates the user is logged in, or timeout."""
    log(f"Autoway tab: {page.url}")
    write_status(state="waiting_for_login", autoway_url=page.url)
    deadline = time.time() + deadline_secs
    while time.time() < deadline:
        time.sleep(3)
        try:
            if _is_logged_in(page.url):
                log(f"Login appears complete: {page.url}")
                click_envelope(page)
                write_status(state="monitoring", autoway_url=page.url)
                return True
        except Exception:
            pass
    log("Autoway not logged in within timeout — leaving tab, will re-check each poll")
    write_status(state="login_pending", autoway_url=page.url,
                 note="Chrome did not auto-sign-in. Log in once so Chrome saves the password on this profile.")
    return False


def click_envelope(page) -> bool:
    """Best-effort click on a mail/envelope icon. Selectors will vary — safe to fail."""
    candidates = [
        "a[href*='mail']",
        "a[title*='Mail']", "a[title*='Envelope']", "a[title*='메일']",
        "button[aria-label*='Mail']", "button[aria-label*='메일']",
        ".fa-envelope", ".icon-envelope", "i.envelope",
        "[data-testid='envelope']", "[data-testid='mail-icon']",
    ]
    for sel in candidates:
        try:
            page.click(sel, timeout=1500)
            log(f"Clicked mail icon via selector: {sel}")
            return True
        except Exception:
            continue
    log("No envelope selector matched — leaving page as-is")
    return False


def poll_autoway(page) -> list:
    if page is None:
        return []
    try:
        return page.evaluate("""() => {
            const rows = document.querySelectorAll(
                'tr.unread, tr.mail-unread, .mail-list-item.unread, li.mail-unread'
            );
            return Array.from(rows).map((r, i) => ({
                idx: i,
                from: (r.querySelector('.sender, .from, .name') || {}).innerText || '',
                subject: (r.querySelector('.subject, .title') || {}).innerText || '',
                date: (r.querySelector('.date, .received, .time') || {}).innerText || '',
            }));
        }""")
    except Exception as e:
        log(f"autoway poll error: {e}")
        return []


def poll_outlook() -> list | None:
    """Return unread list, or None if Outlook isn't running."""
    try:
        import win32com.client
        try:
            outlook = win32com.client.GetActiveObject("Outlook.Application")
        except Exception:
            return None
        ns = outlook.GetNamespace("MAPI")
        inbox = ns.GetDefaultFolder(6)
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)
        out = []
        for msg in items:
            try:
                if not msg.UnRead:
                    continue
                out.append({
                    "id": msg.EntryID,
                    "from": getattr(msg, "SenderName", "") or "",
                    "subject": msg.Subject or "",
                    "received": msg.ReceivedTime.replace(tzinfo=None).isoformat(),
                })
                if len(out) >= 50:
                    break
            except Exception:
                continue
        return out
    except Exception as e:
        log(f"outlook error: {e}")
        return []


def append_stream(source: str, items: list) -> None:
    if not items:
        return
    DATA.mkdir(exist_ok=True)
    with open(STREAM_FILE, "a", encoding="utf-8") as f:
        for it in items:
            it["source"] = source
            it["seen_at"] = datetime.now().isoformat()
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def key_of(item: dict, source: str) -> tuple:
    if source == "outlook":
        return ("outlook", item.get("id", ""))
    return ("autoway", item.get("from", ""), item.get("subject", ""), item.get("date", ""))


def main() -> None:
    from playwright.sync_api import sync_playwright

    DATA.mkdir(exist_ok=True)
    log("=== depot monitor starting ===")
    write_status(state="starting")

    cfg = load_config()
    launch_chrome()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        if not browser.contexts:
            log("ERROR: Chrome has no contexts (unexpected)")
            write_status(state="error", error="no chrome context")
            return
        ctx = browser.contexts[0]

        page = find_autoway_page(ctx, cfg)
        logged_in = wait_for_login(page)
        envelope_clicked = logged_in

        seen: set = set()
        while True:
            try:
                # Re-attach if the user closed Chrome (or the whole page).
                # Symptoms: page.url raises, or CDP endpoint is gone.
                need_reattach = False
                try:
                    _ = page.url  # touch the page — raises if it was closed
                except Exception:
                    need_reattach = True

                if need_reattach or not chrome_cdp_up():
                    log("Chrome/page gone — re-launching and re-attaching")
                    launch_chrome()
                    try:
                        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
                        if browser.contexts:
                            ctx = browser.contexts[0]
                            page = find_autoway_page(ctx, cfg)
                            logged_in = _is_logged_in(page.url)
                            envelope_clicked = False
                    except Exception as e:
                        log(f"re-attach failed: {e}")

                if not logged_in:
                    try:
                        if _is_logged_in(page.url):
                            log(f"Login detected on poll: {page.url}")
                            logged_in = True
                    except Exception:
                        pass
                if logged_in and not envelope_clicked:
                    try:
                        click_envelope(page)
                        envelope_clicked = True
                    except Exception:
                        pass

                aw = poll_autoway(page) if logged_in else []
                new_aw = [x for x in aw if key_of(x, "autoway") not in seen]
                for x in new_aw:
                    seen.add(key_of(x, "autoway"))
                append_stream("autoway", new_aw)

                ol = poll_outlook()
                if ol is None:
                    outlook_state = "not_running"
                    new_ol = []
                else:
                    new_ol = [x for x in ol if key_of(x, "outlook") not in seen]
                    for x in new_ol:
                        seen.add(key_of(x, "outlook"))
                    append_stream("outlook", new_ol)
                    outlook_state = f"{len(ol)} unread ({len(new_ol)} new)"

                state = "monitoring" if logged_in else "login_pending"
                write_status(
                    state=state,
                    autoway_url=page.url if page else "",
                    autoway_unread=len(aw),
                    autoway_new=len(new_aw),
                    outlook=outlook_state,
                    last_poll=datetime.now().isoformat(),
                )
                log(f"poll: autoway unread={len(aw)} new={len(new_aw)} | outlook={outlook_state} | logged_in={logged_in}")
            except Exception as e:
                log(f"cycle error: {e}")
                write_status(state="error", error=str(e))
            time.sleep(POLL_SECS)


if __name__ == "__main__":
    main()
