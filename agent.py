import json
import os
import subprocess
from datetime import datetime
import anthropic
from data_manager import DataManager, MAINTENANCE_TYPES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def _system_health() -> dict:
    """Return a snapshot of the automation stack — used by the AI Assistant."""
    status_path = os.path.join(DATA_DIR, "monitor_status.json")
    log_path = os.path.join(DATA_DIR, "monitor.log")
    report_path = os.path.join(DATA_DIR, "boot_report.md")

    status = {}
    if os.path.exists(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            pass

    scheduler_registered = False
    try:
        _cf = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        r = subprocess.run(
            ["schtasks", "/Query", "/TN", "DepotAgent_TaskReminders"],
            capture_output=True, text=True, timeout=5, creationflags=_cf,
        )
        scheduler_registered = r.returncode == 0
    except Exception:
        pass

    log_tail = ""
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log_tail = "".join(f.readlines()[-8:])
        except Exception:
            pass

    boot_report = ""
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                boot_report = f.read()
        except Exception:
            pass

    return {
        "monitor": status or {"state": "not_started",
                              "note": "monitor_status.json does not exist yet — the monitor may not have started."},
        "task_reminders_scheduler_registered": scheduler_registered,
        "monitor_log_tail": log_tail,
        "boot_report_markdown": boot_report,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def _recent_inbox_events(limit: int = 10) -> list:
    stream_path = os.path.join(DATA_DIR, "inbox_stream.jsonl")
    if not os.path.exists(stream_path):
        return []
    try:
        with open(stream_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        events = []
        for line in lines[-limit:]:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
        return events
    except Exception:
        return []

TOOLS = [
    {
        "name": "get_employees",
        "description": "Get list of all employees in the depot.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_employee",
        "description": "Add a new employee to the depot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":       {"type": "string"},
                "email":      {"type": "string"},
                "phone":      {"type": "string"},
                "role":       {"type": "string"},
                "department": {"type": "string"},
            },
            "required": ["name", "email"],
        },
    },
    {
        "name": "get_tasks",
        "description": "Get all tasks. Optionally filter by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
            },
        },
    },
    {
        "name": "add_task",
        "description": "Create and assign a new task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title":           {"type": "string"},
                "description":     {"type": "string"},
                "assigned_to_ids": {"type": "array", "items": {"type": "string"}},
                "due_date":        {"type": "string", "description": "YYYY-MM-DD"},
                "priority":        {"type": "string", "enum": ["high", "medium", "low"]},
                "train_id":        {"type": "string", "description": "Optional train id (e.g. '03'). Omit for non-train tasks."},
                "recipient":       {"type": "string", "description": "WhatsApp recipient phone or contact name for the reminder."},
                "remind_days_before": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Days-before-due offsets to send WhatsApp reminders on. Defaults to [0] (same day as the task). Pass [0, 1] to send both same day AND one day before, etc.",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task_status",
        "description": "Update the status of a task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "status":  {"type": "string", "enum": ["pending", "in_progress", "completed"]},
            },
            "required": ["task_id", "status"],
        },
    },
    {
        "name": "get_tomorrows_maintenance",
        "description": "Get all trains scheduled for maintenance tomorrow.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "set_schedule_entry",
        "description": "Set a maintenance entry in the schedule grid.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_str":         {"type": "string", "description": "YYYY-MM-DD"},
                "train_id":         {"type": "string"},
                "maintenance_code": {"type": "string", "enum": ["A", "B1", "B2", "B3", "C", "A+C", "G", "9Y"]},
            },
            "required": ["date_str", "train_id", "maintenance_code"],
        },
    },
    {
        "name": "get_schedule_month",
        "description": "Get maintenance schedule for a specific month.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year_month": {"type": "string", "description": "Format: YYYY-MM"},
            },
            "required": ["year_month"],
        },
    },
    {
        "name": "assign_employees_to_train",
        "description": "Assign employees to be responsible for a train.",
        "input_schema": {
            "type": "object",
            "properties": {
                "train_id": {"type": "string"},
                "emp_ids":  {"type": "array", "items": {"type": "string"}},
            },
            "required": ["train_id", "emp_ids"],
        },
    },
    {
        "name": "get_trains",
        "description": "Get list of all trains in the depot.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_system_health",
        "description": (
            "Return the current health of the Depot Agent automation: background monitor state, "
            "last poll time, Autoway unread count, Outlook state, whether the daily task-reminders "
            "scheduler is registered, and the boot report if available. Call this whenever the user "
            "asks 'شوف الحالة' / 'check' / 'الوضع إيه' / 'is everything working' / anything similar."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_recent_inbox_events",
        "description": "Return up to N most recent inbox events (new emails detected by the background monitor).",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
        },
    },
]

SYSTEM_PROMPT = f"""You are the AI Depot Manager Assistant for Cairo Metro Line 1.

You are the operator-facing surface of the Depot Agent. Everything runs headless:
a background monitor polls Autoway + Outlook every 5 min, and a scheduled task at 08:00
sends WhatsApp reminders for pending tasks due tomorrow. The user never checks logs or
runs scripts — they ask *you*.

Language: respond in whichever language the user uses (Egyptian Arabic or English).
When they act — add employees, create tasks, update schedule — call the tool and confirm.
When they ask about the system (شوف / check / الوضع إيه / is it running / any errors),
call `get_system_health` immediately and give a short, direct summary. Never tell the
user to open a log file or run a script themselves.

Maintenance codes:
{json.dumps(MAINTENANCE_TYPES, ensure_ascii=False, indent=2)}

Note: 9Y (9-Year Overhaul) is excluded from WhatsApp reminders.
"""


class DepotAgent:
    def __init__(self):
        self.dm = DataManager()
        config = self.dm.load_config()
        api_key = config.get("anthropic_api_key", "")
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.history = []

    def _execute_tool(self, name, inputs):
        dm = self.dm
        if name == "get_employees":
            emps = dm.get_employees()
            return emps if emps else "No employees found."
        elif name == "add_employee":
            emp = dm.add_employee(**inputs)
            return f"Employee added: {emp['name']} (ID: {emp['id']})"
        elif name == "get_tasks":
            tasks = dm.get_tasks()
            if "status" in inputs:
                tasks = [t for t in tasks if t["status"] == inputs["status"]]
            emps = {e["id"]: e["name"] for e in dm.get_employees()}
            for t in tasks:
                t["assigned_names"] = [emps.get(i, i) for i in t.get("assigned_to_ids", t.get("assigned_to", []))]
            return tasks if tasks else "No tasks found."
        elif name == "add_task":
            task = dm.add_task(
                title=inputs["title"],
                description=inputs.get("description", ""),
                assigned_to_ids=inputs.get("assigned_to_ids", []),
                due_date=inputs.get("due_date", ""),
                priority=inputs.get("priority", "medium"),
                train_id=inputs.get("train_id", ""),
                recipient=inputs.get("recipient", ""),
                remind_days_before=inputs.get("remind_days_before", [0]),
            )
            return f"Task created: {task['title']} (ID: {task['id']})"
        elif name == "update_task_status":
            dm.update_task(inputs["task_id"], status=inputs["status"])
            return f"Task {inputs['task_id']} status updated to {inputs['status']}."
        elif name == "get_tomorrows_maintenance":
            items = dm.get_tomorrows_maintenance()
            return items if items else "No maintenance scheduled for tomorrow."
        elif name == "set_schedule_entry":
            dm.set_schedule_entry(inputs["date_str"], inputs["train_id"], inputs["maintenance_code"])
            return f"Schedule set: Train {inputs['train_id']} on {inputs['date_str']} → {inputs['maintenance_code']}"
        elif name == "get_schedule_month":
            return dm.get_month_schedule(inputs["year_month"])
        elif name == "assign_employees_to_train":
            dm.assign_employees_to_train(inputs["train_id"], inputs["emp_ids"])
            return f"Employees assigned to Train {inputs['train_id']}."
        elif name == "get_trains":
            return dm.get_trains()
        elif name == "get_system_health":
            return _system_health()
        elif name == "get_recent_inbox_events":
            return _recent_inbox_events(int(inputs.get("limit", 10)))
        return "Unknown tool."

    def chat(self, user_message: str) -> str:
        if not self.client:
            return "⚠️ Anthropic API key not configured. Please add it in the ⚙️ Settings tab."

        self.history.append({"role": "user", "content": user_message})

        messages = list(self.history)

        while True:
            response = self.client.messages.create(
                model="claude-sonnet-5",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                assistant_msg = {"role": "assistant", "content": response.content}
                messages.append(assistant_msg)

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })

                messages.append({"role": "user", "content": tool_results})

            else:
                text = "".join(b.text for b in response.content if hasattr(b, "text"))
                self.history.append({"role": "assistant", "content": text})
                return text
