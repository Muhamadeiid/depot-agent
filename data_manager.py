import json
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

MAINTENANCE_TYPES = {
    "A": "Type A Inspection",
    "B1": "Type B1 Maintenance",
    "B2": "Type B2 Maintenance",
    "B3": "Type B3 Maintenance",
    "C": "Type C Service",
    "A+C": "Combined A+C Service",
    "G": "Type G Maintenance",
    "9Y": "9-Year Overhaul"
}


def _load_json(filepath, default):
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class DataManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)

    # ── Config ──────────────────────────────────────────────────────────────
    def load_config(self) -> dict:
        default = {
            "depot_name": "Cairo Metro Line 1 Depot",
            "manager_name": "Depot Manager",
            "manager_phone": "",  # for the 5 PM personal digest
            "reminder_days_before": 1,
            "whatsapp_group_name": "Line 1 Management",
            "webmail": {
                "url": "https://autoway.hyundai.net/main/",
                "type": "autoway",
                "username": "",
                "password": "",
                "headless": False
            },
            "anthropic_api_key": ""
        }
        return _load_json(CONFIG_FILE, default)

    def save_config(self, config: dict):
        _save_json(CONFIG_FILE, config)

    # ── Employees ────────────────────────────────────────────────────────────
    def _emp_path(self):
        return os.path.join(DATA_DIR, "employees.json")

    def get_employees(self) -> list:
        return _load_json(self._emp_path(), [])

    def get_employee(self, emp_id: str) -> Optional[dict]:
        return next((e for e in self.get_employees() if e["id"] == emp_id), None)

    def add_employee(self, name: str, email: str, phone: str, role: str, department: str) -> dict:
        employees = self.get_employees()
        emp = {
            "id": f"EMP-{uuid.uuid4().hex[:6].upper()}",
            "name": name,
            "email": email,
            "phone": phone,
            "role": role,
            "department": department,
            "created_at": datetime.now().isoformat()
        }
        employees.append(emp)
        _save_json(self._emp_path(), employees)
        return emp

    def update_employee(self, emp_id: str, **kwargs) -> Optional[dict]:
        employees = self.get_employees()
        for emp in employees:
            if emp["id"] == emp_id:
                emp.update(kwargs)
                _save_json(self._emp_path(), employees)
                return emp
        return None

    def delete_employee(self, emp_id: str) -> bool:
        employees = self.get_employees()
        new_list = [e for e in employees if e["id"] != emp_id]
        if len(new_list) == len(employees):
            return False
        _save_json(self._emp_path(), new_list)
        return True

    # ── Tasks ────────────────────────────────────────────────────────────────
    def _task_path(self):
        return os.path.join(DATA_DIR, "tasks.json")

    def get_tasks(self) -> list:
        return _load_json(self._task_path(), [])

    def add_task(self, title: str, description: str, assigned_to_ids: list,
                 due_date: str, priority: str,
                 train_id: str = "", recipient: str = "",
                 remind_days_before=0) -> dict:
        # remind_days_before accepts int (single day) or list[int] (multiple offsets).
        # 0 = same day as due_date, 1 = one day before, etc.
        if isinstance(remind_days_before, (list, tuple)):
            offsets = sorted({int(x) for x in remind_days_before})
        else:
            offsets = [int(remind_days_before or 0)]
        tasks = self.get_tasks()
        task = {
            "id": f"TSK-{uuid.uuid4().hex[:6].upper()}",
            "title": title,
            "description": description,
            "assigned_to_ids": assigned_to_ids,
            "due_date": due_date,
            "priority": priority,
            "status": "pending",
            "train_id": train_id,
            "recipient": recipient,
            "remind_days_before": offsets,
            "reminder_sent_for": "",
            "created_at": datetime.now().isoformat()
        }
        tasks.append(task)
        _save_json(self._task_path(), tasks)
        return task

    def update_task(self, task_id: str, **kwargs) -> Optional[dict]:
        tasks = self.get_tasks()
        for task in tasks:
            if task["id"] == task_id:
                task.update(kwargs)
                _save_json(self._task_path(), tasks)
                return task
        return None

    def delete_task(self, task_id: str) -> bool:
        tasks = self.get_tasks()
        new_list = [t for t in tasks if t["id"] != task_id]
        if len(new_list) == len(tasks):
            return False
        _save_json(self._task_path(), new_list)
        return True

    # ── Trains ───────────────────────────────────────────────────────────────
    def _trains_path(self):
        return os.path.join(DATA_DIR, "trains.json")

    def _assignments_path(self):
        return os.path.join(DATA_DIR, "train_assignments.json")

    def get_trains(self) -> list:
        return _load_json(self._trains_path(), [])

    def add_train(self, train_id: str, name: str = "") -> dict:
        """Add a train. train_id is zero-padded to 2 digits ('7' -> '07')."""
        tid = str(train_id).strip().zfill(2)
        trains = self.get_trains()
        if any(t["id"] == tid for t in trains):
            return next(t for t in trains if t["id"] == tid)
        train = {"id": tid, "name": name.strip() or f"Train {tid}"}
        trains.append(train)
        _save_json(self._trains_path(), trains)
        return train

    def delete_train(self, train_id: str) -> bool:
        tid = str(train_id).strip().zfill(2)
        trains = self.get_trains()
        new_list = [t for t in trains if t["id"] != tid]
        if len(new_list) == len(trains):
            return False
        _save_json(self._trains_path(), new_list)
        return True

    def seed_line1_trains(self) -> int:
        """Seed the 20 standard Cairo Metro Line 1 trains (01..20). Returns count added."""
        existing = {t["id"] for t in self.get_trains()}
        added = 0
        for n in range(1, 21):
            tid = f"{n:02d}"
            if tid not in existing:
                self.add_train(tid)
                added += 1
        return added

    def get_train_assignments(self) -> dict:
        return _load_json(self._assignments_path(), {})

    def assign_employees_to_train(self, train_id: str, emp_ids: list):
        assignments = self.get_train_assignments()
        assignments[train_id] = emp_ids
        _save_json(self._assignments_path(), assignments)

    # ── Schedule Grid ────────────────────────────────────────────────────────
    def _schedule_path(self):
        return os.path.join(DATA_DIR, "schedule_grid.json")

    def get_schedule_grid(self) -> dict:
        return _load_json(self._schedule_path(), {})

    def get_month_schedule(self, year_month: str) -> dict:
        grid = self.get_schedule_grid()
        return {d: entries for d, entries in grid.items() if d.startswith(year_month)}

    def set_schedule_entry(self, date_str: str, train_id: str, maintenance_code: str):
        grid = self.get_schedule_grid()
        if date_str not in grid:
            grid[date_str] = {}
        grid[date_str][train_id] = maintenance_code
        _save_json(self._schedule_path(), grid)

    def remove_schedule_entry(self, date_str: str, train_id: str):
        grid = self.get_schedule_grid()
        if date_str in grid and train_id in grid[date_str]:
            del grid[date_str][train_id]
            if not grid[date_str]:
                del grid[date_str]
            _save_json(self._schedule_path(), grid)

    # ── Schedule per-day metadata (K6, K5, C, K19, remark) ──────────────
    def _schedule_meta_path(self):
        return os.path.join(DATA_DIR, "schedule_meta.json")

    def get_schedule_meta(self, date_str: str) -> dict:
        return _load_json(self._schedule_meta_path(), {}).get(date_str, {})

    def set_schedule_meta(self, date_str: str, meta: dict):
        all_meta = _load_json(self._schedule_meta_path(), {})
        cleaned = {k: v for k, v in meta.items() if v not in (None, "")}
        if cleaned:
            all_meta[date_str] = cleaned
        elif date_str in all_meta:
            del all_meta[date_str]
        _save_json(self._schedule_meta_path(), all_meta)

    def get_train_order(self) -> list:
        """Return the manager's preferred train column order for the schedule grid.
        Falls back to sorted train IDs if not configured.
        """
        cfg = self.load_config()
        order = cfg.get("schedule_train_order") or []
        train_ids = {t["id"] for t in self.get_trains()}
        # Keep configured order that still exists; append any new trains at the end.
        ordered = [tid for tid in order if tid in train_ids]
        ordered += [tid for tid in sorted(train_ids) if tid not in ordered]
        return ordered

    def set_train_order(self, order: list):
        cfg = self.load_config()
        cfg["schedule_train_order"] = list(order)
        self.save_config(cfg)

    def get_tomorrows_maintenance(self) -> list:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        grid = self.get_schedule_grid()
        day_entries = grid.get(tomorrow, {})
        assignments = self.get_train_assignments()
        trains = {t["id"]: t for t in self.get_trains()}
        employees = {e["id"]: e for e in self.get_employees()}

        result = []
        for train_id, code in day_entries.items():
            if code == "9Y":
                continue
            train = trains.get(train_id, {"id": train_id, "name": f"Train {train_id}"})
            emp_ids = assignments.get(train_id, [])
            emp_objects = [employees[eid] for eid in emp_ids if eid in employees]
            result.append({
                "train_id": train_id,
                "train_name": train["name"],
                "code": code,
                "code_name": MAINTENANCE_TYPES.get(code, code),
                "employees": emp_objects
            })
        return result

    # ── Maintenance Records ──────────────────────────────────────────────────
    def _maint_path(self):
        return os.path.join(DATA_DIR, "maintenance.json")

    def get_maintenances(self) -> list:
        return _load_json(self._maint_path(), [])

    def add_maintenance(self, train_id: str, maintenance_type: str, date_str: str, notes: str, emp_ids: list) -> dict:
        records = self.get_maintenances()
        record = {
            "id": f"MNT-{uuid.uuid4().hex[:6].upper()}",
            "train_id": train_id,
            "maintenance_type": maintenance_type,
            "date": date_str,
            "notes": notes,
            "emp_ids": emp_ids,
            "created_at": datetime.now().isoformat()
        }
        records.append(record)
        _save_json(self._maint_path(), records)
        return record
