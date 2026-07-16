"""
Email Reader — reads unread emails from Outlook Desktop (via COM) or Autoway webmail (via Chrome CDP).
"""
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path


DOWNLOADS_DIR = str(Path.home() / "Downloads")


def _com_init():
    """Ensure COM is initialised on the current thread (needed for Streamlit worker threads)."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass


def read_outlook_unread(days_back: int = 2) -> list:
    """
    Read unread emails from Outlook Desktop using pywin32.
    Returns emails from today and the past `days_back` days.
    """
    try:
        import win32com.client
    except ImportError:
        return [{"error": "pywin32 not installed. Run: pip install pywin32"}]

    _com_init()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6)  # 6 = Inbox
        messages = inbox.Items
        messages.Sort("[ReceivedTime]", True)

        cutoff = datetime.now() - timedelta(days=days_back)
        results = []

        for msg in messages:
            try:
                # Filter: unread and recent
                if msg.UnRead is False:
                    continue
                received = msg.ReceivedTime.replace(tzinfo=None)
                if received < cutoff:
                    break  # sorted desc, no point continuing

                attachments = []
                for att in msg.Attachments:
                    attachments.append({
                        "filename": att.FileName,
                        "size": att.Size,
                    })

                results.append({
                    "id": msg.EntryID,
                    "source": "outlook",
                    "from": getattr(msg, "SenderName", "") or "",
                    "from_email": getattr(msg, "SenderEmailAddress", "") or "",
                    "to": getattr(msg, "To", "") or "",
                    "subject": msg.Subject or "",
                    "body": (msg.Body or "")[:5000],  # limit body size
                    "received": received.isoformat(),
                    "unread": True,
                    "has_attachments": len(attachments) > 0,
                    "attachments": attachments,
                })
            except Exception as e:
                continue

        return results
    except Exception as e:
        return [{"error": f"Outlook access failed: {e}"}]


def download_outlook_attachments(email_entry_id: str) -> list:
    """Download all attachments from a specific Outlook email into ~/Downloads."""
    try:
        import win32com.client
    except ImportError:
        return []

    _com_init()
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    msg = outlook.GetItemFromID(email_entry_id)
    saved = []
    for att in msg.Attachments:
        target = os.path.join(DOWNLOADS_DIR, att.FileName)
        att.SaveAsFile(target)
        saved.append(target)
    return saved


def mark_outlook_read(email_entry_id: str):
    """Mark an Outlook email as read."""
    try:
        import win32com.client
        _com_init()
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        msg = outlook.GetItemFromID(email_entry_id)
        msg.UnRead = False
        msg.Save()
    except Exception:
        pass


def send_outlook_reply(email_entry_id: str, reply_body: str, attachment_paths: list = None) -> bool:
    """Send a reply to an Outlook email. Attachments optional."""
    try:
        import win32com.client
        _com_init()
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        original = outlook.GetItemFromID(email_entry_id)
        reply = original.Reply()
        reply.Body = reply_body + "\n\n" + (reply.Body or "")
        if attachment_paths:
            for path in attachment_paths:
                if os.path.exists(path):
                    reply.Attachments.Add(path)
        reply.Send()
        return True
    except Exception as e:
        print(f"Send failed: {e}")
        return False


# ── Autoway (via Chrome CDP) ─────────────────────────────────────────────────

def read_autoway_unread(days_back: int = 2) -> list:
    """
    Read unread emails from Autoway webmail via Chrome running with --remote-debugging-port=9222.
    Uses Playwright to attach to the existing Chrome session.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [{"error": "playwright not installed. Run: pip install playwright && playwright install chromium"}]

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            contexts = browser.contexts
            if not contexts:
                return [{"error": "No Chrome context found. Open Chrome first."}]

            # Find the Autoway tab
            autoway_page = None
            for ctx in contexts:
                for page in ctx.pages:
                    if "autoway.hyundai.net" in page.url:
                        autoway_page = page
                        break
                if autoway_page:
                    break

            if not autoway_page:
                return [{"error": "No Autoway tab open. Please open autoway.hyundai.net in Chrome."}]

            # Autoway-specific scraping — selectors will need to be adjusted per real DOM
            # This is a scaffold: extract unread mail rows from the inbox
            autoway_page.wait_for_load_state("domcontentloaded", timeout=5000)

            emails = autoway_page.evaluate("""
                () => {
                    // Try to find unread email rows — this needs to be adapted to Autoway's actual DOM
                    const rows = document.querySelectorAll('tr.unread, tr.mail-unread, .mail-list-item.unread');
                    const items = [];
                    rows.forEach((row, idx) => {
                        items.push({
                            index: idx,
                            from: (row.querySelector('.sender, .from') || {}).innerText || '',
                            subject: (row.querySelector('.subject, .title') || {}).innerText || '',
                            date: (row.querySelector('.date, .received') || {}).innerText || '',
                            preview: (row.querySelector('.preview') || {}).innerText || '',
                        });
                    });
                    return items;
                }
            """)

            results = []
            for e in emails:
                results.append({
                    "id": f"autoway-{e.get('index')}",
                    "source": "autoway",
                    "from": e.get("from", ""),
                    "from_email": "",
                    "to": "",
                    "subject": e.get("subject", ""),
                    "body": e.get("preview", ""),
                    "received": e.get("date", ""),
                    "unread": True,
                    "has_attachments": False,
                    "attachments": [],
                })

            return results if results else [{"info": "No unread emails found on Autoway (or selectors need adjustment for this webmail's DOM)."}]

    except Exception as e:
        return [{"error": f"Autoway read failed: {e}. Is Chrome running with --remote-debugging-port=9222?"}]


def read_all_unread(days_back: int = 2, sources: list = None) -> list:
    """Read unread emails from both Outlook and Autoway."""
    sources = sources or ["outlook", "autoway"]
    results = []
    if "outlook" in sources:
        results.extend(read_outlook_unread(days_back))
    if "autoway" in sources:
        results.extend(read_autoway_unread(days_back))
    return results
