"""
Daily WhatsApp Reminder — Cairo Metro Line 1 Depot Agent
Sends tomorrow's maintenance schedule to the WhatsApp group.
Run via Windows Task Scheduler every day at 08:00 AM.
Requires WhatsApp Desktop to be open and logged in.
"""
import time
import sys
from datetime import date, timedelta
from data_manager import DataManager
from rich.console import Console

console = Console()


def build_message(maintenance_list: list, config: dict) -> str:
    tomorrow = (date.today() + timedelta(days=1)).strftime("%A, %d %B %Y")
    depot = config.get("depot_name", "Cairo Metro Line 1 Depot")
    manager = config.get("manager_name", "Depot Manager")

    if not maintenance_list:
        return (
            f"🚇 *{depot}*\n"
            f"📅 Tomorrow ({tomorrow})\n"
            f"✅ No maintenance scheduled for tomorrow."
        )

    lines = [
        f"🚇 *{depot} — Daily Maintenance Reminder*",
        f"📅 *Tomorrow: {tomorrow}*",
        f"🔧 *Scheduled Maintenance ({len(maintenance_list)} train(s)):*",
        "",
    ]
    for item in maintenance_list:
        code = item["code"]
        code_name = item["code_name"]
        emp_names = ", ".join(e["name"] for e in item.get("employees", []))
        lines.append(f"• *Train {item['train_id']}* — {code} ({code_name})")
        if emp_names:
            lines.append(f"  👷 {emp_names}")
    lines += ["", "✅ Please confirm readiness by EOD.", f"— {manager}"]
    return "\n".join(lines)


def send_whatsapp_reminder():
    dm = DataManager()
    config = dm.load_config()
    maintenance = dm.get_tomorrows_maintenance()
    message = build_message(maintenance, config)
    group_name = config.get("whatsapp_group_name", "Line 1 Management")

    console.print(f"\n[bold blue]Cairo Metro — Daily WhatsApp Reminder[/bold blue]")
    console.print(f"Group: {group_name}")
    console.print(f"Trains scheduled tomorrow: {len(maintenance)}")
    console.print("\n[dim]Message preview:[/dim]")
    console.print(message)

    try:
        import pyautogui
        import pygetwindow as gw
        import pyperclip

        # Find WhatsApp window
        windows = gw.getWindowsWithTitle("WhatsApp")
        if not windows:
            console.print("[red]WhatsApp Desktop window not found. Please open WhatsApp.[/red]")
            return False

        win = windows[0]
        win.activate()
        time.sleep(1)

        # Open search (Ctrl+F) and find the group
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.8)
        pyautogui.typewrite(group_name, interval=0.05)
        time.sleep(1.5)
        pyautogui.press("enter")
        time.sleep(1)

        # Close search
        pyautogui.press("escape")
        time.sleep(0.5)

        # Click message input area (bottom of screen, center)
        screen_w, screen_h = pyautogui.size()
        pyautogui.click(screen_w // 2, int(screen_h * 0.93))
        time.sleep(0.5)

        # Paste message using clipboard (supports Arabic + emojis)
        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(0.5)

        console.print(f"[green]✅ Message sent to '{group_name}' successfully![/green]")
        return True

    except ImportError:
        console.print("[yellow]⚠️ pyautogui/pygetwindow not available (Linux environment).[/yellow]")
        console.print("[dim]On Windows, this script will control WhatsApp Desktop automatically.[/dim]")
        return False
    except Exception as e:
        console.print(f"[red]Error sending WhatsApp message: {e}[/red]")
        return False


if __name__ == "__main__":
    send_whatsapp_reminder()
