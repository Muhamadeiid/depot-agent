# 🚇 Cairo Metro Line 1 — Depot Agent

## Quick Start on Your PC

### Step 1 — Install Python
Download from **python.org/downloads** — check ✅ "Add Python to PATH" during install.

### Step 2 — Download the project
Option A (Git):
```
git clone https://github.com/muhamadeiid/template_1.git C:\depot-agent
cd C:\depot-agent
git checkout claude/awesome-lovelace-1j3ety
```

Option B (No Git):
- Go to the GitHub repo → **Code → Download ZIP** → extract to `C:\depot-agent`

### Step 3 — Install everything
Double-click:
```
setup_new_laptop.bat
```

### Step 4 — Launch the dashboard
Double-click:
```
run_gui.bat
```
Opens automatically at `http://localhost:8501`

### Step 5 — Configure API Key (one time)
- Go to **⚙️ Settings** tab
- Paste your Anthropic API key (get from console.anthropic.com)
- Click **Save Settings**

---

## Features

| Tab | What it does |
|---|---|
| 🤖 AI Assistant | Chat in Arabic/English — manages employees, tasks, schedule |
| 📬 Inbox Assistant | Reads unread emails from Outlook + Autoway, drafts replies |
| 👥 Employees | Add/manage your team |
| 📋 Tasks | Assign tasks with due dates |
| 🚂 Trains & Assignments | Assign employees to each of the 20 trains |
| 📅 Schedule Grid | Monthly maintenance grid (A/B1/B2/B3/C/A+C/9Y) |
| ⚙️ Settings | Config, API key, webmail |

---

## Inbox Assistant — Enable Real Emails

### For Outlook Desktop:
Double-click: `install_outlook_support.bat`
Then open Outlook Desktop normally.

### For Autoway (autoway.hyundai.net):
Close all Chrome windows, then double-click: `launch_chrome_debug.bat`
Log in to Autoway in that Chrome window.

### Just want to see how it works?
✅ Turn on **🧪 Demo Mode** — no setup needed, uses fake emails.

---

## Daily WhatsApp Reminder (Automated)

Runs every day at 8:00 AM automatically. To register in Windows Task Scheduler:

```cmd
schtasks /create /tn "DepotAgent_DailyWhatsApp" /tr "python C:\depot-agent\daily_whatsapp.py" /sc daily /st 08:00
```

Requires WhatsApp Desktop to be open and logged in.
