import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
import os
import subprocess
import sys
from data_manager import DataManager, MAINTENANCE_TYPES
from agent import DepotAgent


def _spawn_notify(task_id: str) -> None:
    """Fire-and-forget subprocess that sends the WhatsApp notification for a
    single task. Running in a subprocess keeps the Streamlit UI responsive
    while pyautogui drives WhatsApp Desktop (which takes 7–10s per recipient).
    """
    project_dir = os.path.dirname(os.path.abspath(__file__))
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.Popen(
        [sys.executable, "-c",
         f"from daily_reminders import notify_task_now; notify_task_now({task_id!r})"],
        cwd=project_dir,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

st.set_page_config(
    page_title="Cairo Metro Line 1 — Depot Agent",
    page_icon="🚇",
    layout="wide",
)

dm = DataManager()

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Cairo_Metro_Logo.svg/200px-Cairo_Metro_Logo.svg.png", width=80)
st.sidebar.title("🚇 Depot Agent")
st.sidebar.caption("Cairo Metro Line 1")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigation",
    ["🤖 AI Assistant", "📬 Inbox Assistant", "👥 Employees", "📋 Tasks", "🚂 Trains & Assignments", "📅 Schedule Grid", "⚙️ Settings"],
)

config = dm.load_config()
st.sidebar.divider()
st.sidebar.caption(f"**{config.get('depot_name','Depot')}**")
st.sidebar.caption(f"Manager: {config.get('manager_name','')}")

# ── Code colours ──────────────────────────────────────────────────────────────
CODE_COLORS = {
    "A":   "#FFEB3B",   # yellow
    "B1":  "#8BC34A",   # green
    "B2":  "#8BC34A",   # green
    "B3":  "#8BC34A",   # green
    "C":   "",          # no fill — plain black text, matches the source sheet
    "A+C": "#9C27B0",   # purple
    "G":   "#2196F3",   # blue
    "9Y":  "#F44336",   # red
}

# Codes whose fill is dark enough that white text reads best. Others (A yellow,
# B* green, empty-fill C) look better with black text.
CODE_WHITE_TEXT = {"9Y", "G", "A+C"}


def _system_strip():
    """Persistent one-line system-health strip shown at the top of every page."""
    import os as _os, json as _json, subprocess as _sp
    status_path = _os.path.join(_os.path.dirname(__file__), "data", "monitor_status.json")
    status = {}
    if _os.path.exists(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                status = _json.load(f)
        except Exception:
            pass
    state = status.get("state", "not_started")
    emoji = {"monitoring": "🟢", "waiting_for_login": "🟡", "login_pending": "🟠",
             "starting": "⚪", "error": "🔴"}.get(state, "⚫")

    sched = False
    try:
        _cf = _sp.CREATE_NO_WINDOW if hasattr(_sp, "CREATE_NO_WINDOW") else 0
        r = _sp.run(["schtasks", "/Query", "/TN", "DepotAgent_TaskReminders"],
                    capture_output=True, text=True, timeout=3, creationflags=_cf)
        sched = r.returncode == 0
    except Exception:
        pass

    outlook = status.get("outlook", "—")
    aw = status.get("autoway_unread", "—")
    last = status.get("last_poll", "—")
    sched_icon = "✅" if sched else "🔴"
    st.markdown(
        f"<div style='padding:6px 12px;background:#F5F5F5;border-radius:6px;"
        f"font-size:13px;margin-bottom:8px;color:#333'>"
        f"<b>Monitor</b>: {emoji} {state} &nbsp;·&nbsp; "
        f"<b>Autoway</b>: {aw} unread &nbsp;·&nbsp; "
        f"<b>Outlook</b>: {outlook} &nbsp;·&nbsp; "
        f"<b>Daily reminders 08:00</b>: {sched_icon} &nbsp;·&nbsp; "
        f"<span style='color:#888'>Last poll: {last}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


_system_strip()


def badge(code):
    color = CODE_COLORS.get(code, "#333")
    return f'<span style="background:{color};color:white;padding:2px 7px;border-radius:4px;font-size:12px;font-weight:bold">{code}</span>'


# ════════════════════════════════════════════════════════════════════════════════
# PAGE: AI ASSISTANT
# ════════════════════════════════════════════════════════════════════════════════
if page == "🤖 AI Assistant":
    st.title("🤖 AI Depot Assistant")
    st.caption("Chat in Arabic or English — I can manage employees, tasks, and the maintenance schedule.")

    if "agent" not in st.session_state:
        st.session_state.agent = DepotAgent()
    if "messages" not in st.session_state:
        st.session_state.messages = []
        welcome = (
            "👋 Welcome to Cairo Metro Line 1 Depot Agent!\n\n"
            "I can help you:\n"
            "- Add or list employees / موظفين\n"
            "- Create and assign tasks / مهام\n"
            "- Check tomorrow's maintenance / صيانة الغد\n"
            "- Update the schedule grid / الجدول الشبكي\n\n"
            "What would you like to do?"
        )
        st.session_state.messages.append({"role": "assistant", "content": welcome})

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Type your message..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply = st.session_state.agent.chat(prompt)
            st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.session_state.agent = DepotAgent()
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# PAGE: EMPLOYEES
# ════════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════════
# PAGE: INBOX ASSISTANT
# ════════════════════════════════════════════════════════════════════════════════
elif page == "📬 Inbox Assistant":
    st.title("📬 Inbox Assistant")
    st.caption("Reads unread emails from Outlook Desktop and Autoway. Drafts professional replies for your review.")

    # Background monitor status
    import os as _os, json as _json
    _status_path = _os.path.join(_os.path.dirname(__file__), "data", "monitor_status.json")
    if _os.path.exists(_status_path):
        try:
            with open(_status_path, "r", encoding="utf-8") as _f:
                _mon = _json.load(_f)
            _state = _mon.get("state", "unknown")
            _emoji = {"monitoring": "🟢", "waiting_for_login": "🟡", "login_pending": "🟠",
                      "starting": "⚪", "error": "🔴"}.get(_state, "⚫")
            _cols = st.columns([1, 1, 1, 2])
            _cols[0].metric("Monitor", f"{_emoji} {_state}")
            _cols[1].metric("Autoway unread", _mon.get("autoway_unread", "—"))
            _cols[2].metric("Outlook", _mon.get("outlook", "—"))
            _cols[3].caption(f"Last poll: {_mon.get('last_poll', '—')}")
            if _mon.get("note"):
                st.info(_mon["note"])
        except Exception:
            pass
    else:
        st.info("Background monitor is not running yet. Run `install_startup.bat` to have it start on login, or start it now with `pythonw autoway_monitor.py`.")
    st.divider()

    from email_reader import read_outlook_unread, read_autoway_unread, download_outlook_attachments, mark_outlook_read, send_outlook_reply, DOWNLOADS_DIR
    from attachment_handler import analyze_spreadsheet, create_reply_spreadsheet
    from email_analyzer import analyze_email, refine_reply, suggest_spreadsheet_reply_data

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 2])
    src_outlook = c1.checkbox("Outlook Desktop", value=True)
    src_autoway = c2.checkbox("Autoway", value=True)
    demo_mode = c3.checkbox("🧪 Demo Mode", value=False, help="Use fake sample emails")
    days_back = c4.number_input("Days back", 0, 7, 2)
    fetch_btn = c5.button("🔄 Fetch Unread Emails", type="primary", use_container_width=True)

    if fetch_btn and demo_mode:
        from demo_emails import DEMO_EMAILS
        st.session_state.inbox_emails = list(DEMO_EMAILS)
        st.session_state.inbox_analyses = {}
        st.session_state.inbox_attachments = {}
        st.success(f"🧪 Loaded {len(DEMO_EMAILS)} demo emails.")
    elif fetch_btn:
        emails = []
        with st.spinner("Fetching emails..."):
            if src_outlook:
                emails.extend(read_outlook_unread(days_back))
            if src_autoway:
                emails.extend(read_autoway_unread(days_back))
        # Filter out error/info entries but keep them separately shown
        real_emails = [e for e in emails if "error" not in e and "info" not in e]
        messages = [e for e in emails if "error" in e or "info" in e]
        st.session_state.inbox_emails = real_emails
        st.session_state.inbox_analyses = {}
        st.session_state.inbox_attachments = {}
        for m in messages:
            if "error" in m:
                st.warning(m["error"])
            if "info" in m:
                st.info(m["info"])
        st.success(f"✅ Found {len(real_emails)} unread email(s).")

    emails = st.session_state.get("inbox_emails", [])
    if not emails:
        st.info("Click **Fetch Unread Emails** to load your inbox. The background monitor already keeps Autoway open — just make sure Outlook Desktop is running for Outlook mail.")
    else:
        st.divider()
        for idx, em in enumerate(emails):
            urgency_emoji = ""
            analysis = st.session_state.inbox_analyses.get(em["id"])
            if analysis:
                urgency_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(analysis.get("urgency", ""), "")

            source_icon = "📮" if em["source"] == "outlook" else "🌐"
            attach_icon = "📎" if em.get("has_attachments") else ""

            with st.expander(f"{urgency_emoji}{source_icon} **{em.get('subject','(no subject)')}** — from {em.get('from','')} {attach_icon}"):
                c1, c2 = st.columns([3, 1])
                c1.caption(f"Received: {em.get('received','')}  |  Source: {em['source'].upper()}")

                if c2.button("🔍 Analyze", key=f"analyze_{idx}"):
                    with st.spinner("Analyzing..."):
                        # Handle attachments first
                        att_analysis = None
                        if em.get("has_attachments") and em["source"] == "outlook":
                            paths = download_outlook_attachments(em["id"])
                            st.session_state.inbox_attachments[em["id"]] = paths
                            for p in paths:
                                if p.lower().endswith((".xlsx", ".xls", ".csv", ".xlsm")):
                                    att_analysis = analyze_spreadsheet(p)
                                    break
                        result = analyze_email(em, att_analysis)
                        st.session_state.inbox_analyses[em["id"]] = result
                    st.rerun()

                st.markdown("**📄 Body:**")
                body_text = (em.get("body", "") or "").strip()
                if body_text:
                    st.text_area("body", body_text, height=150, disabled=True, label_visibility="collapsed", key=f"body_{idx}")
                else:
                    st.info("This email's body isn't cached locally — open it once in Outlook Desktop and Outlook will download the content. Attachments below still download fine.")

                # Show attachment metadata (from the fetched envelope) even before download.
                atts = em.get("attachments") or []
                if atts:
                    st.markdown("**📎 Attachments in this email:**")
                    for a in atts:
                        nm = a.get("filename", "?") if isinstance(a, dict) else str(a)
                        sz = a.get("size", 0) if isinstance(a, dict) else 0
                        st.caption(f"• {nm} ({(sz / 1024):.1f} KB)" if sz else f"• {nm}")
                    if em["source"] == "outlook":
                        if st.button("📥 Download attachments to ~/Downloads", key=f"dl_att_{idx}"):
                            paths = download_outlook_attachments(em["id"])
                            st.session_state.inbox_attachments[em["id"]] = paths
                            if paths:
                                st.success(f"✅ Downloaded {len(paths)} file(s):")
                                for p in paths:
                                    st.caption(f"• {os.path.basename(p)}")
                            else:
                                st.warning("No files were downloaded (attachments may be inline images only).")

                if em["id"] in st.session_state.inbox_attachments and not atts:
                    st.markdown("**📎 Downloaded to `~/Downloads`:**")
                    for p in st.session_state.inbox_attachments[em["id"]]:
                        st.caption(f"• {os.path.basename(p)}")

                if analysis:
                    st.divider()
                    st.markdown(f"### {urgency_emoji} Analysis")
                    st.markdown(f"**Summary:** {analysis.get('summary','')}")
                    st.markdown(f"**Urgency:** `{analysis.get('urgency','')}`  |  **Action Required:** `{analysis.get('action_required')}`")
                    if analysis.get("action"):
                        st.markdown(f"**Action:** {analysis['action']}")

                    if analysis.get("requires_spreadsheet_reply"):
                        st.warning(f"📊 This email requires a spreadsheet reply. Notes: {analysis.get('spreadsheet_reply_notes','')}")
                        if st.button("🧮 Generate Reply Spreadsheet", key=f"gen_ss_{idx}"):
                            att_paths = st.session_state.inbox_attachments.get(em["id"], [])
                            if att_paths:
                                att_analysis = analyze_spreadsheet(att_paths[0])
                                rows = suggest_spreadsheet_reply_data(em, att_analysis, analysis.get("spreadsheet_reply_notes", ""))
                                if rows:
                                    out_path = create_reply_spreadsheet(att_paths[0], rows)
                                    st.success(f"✅ Reply spreadsheet created: `{out_path}`")
                                    st.session_state.inbox_attachments.setdefault(f"reply_{em['id']}", []).append(out_path)
                                else:
                                    st.error("Could not generate reply data.")
                            else:
                                st.error("No spreadsheet attachment found.")

                    st.markdown("### ✉️ Draft Reply (edit before sending)")
                    draft_key = f"draft_{em['id']}"
                    if draft_key not in st.session_state:
                        st.session_state[draft_key] = analysis.get("draft_reply", "")

                    st.session_state[draft_key] = st.text_area(
                        "Draft",
                        value=st.session_state[draft_key],
                        height=250,
                        key=f"draft_area_{idx}",
                        label_visibility="collapsed",
                    )

                    refine_instr = st.text_input("💡 Refine draft (e.g. 'make it shorter', 'more formal', 'خليها بالعربي'):", key=f"refine_{idx}")
                    ref_col, send_col, mark_col = st.columns(3)

                    if ref_col.button("✨ Refine", key=f"refine_btn_{idx}"):
                        if refine_instr:
                            with st.spinner("Refining..."):
                                st.session_state[draft_key] = refine_reply(em, st.session_state[draft_key], refine_instr)
                            st.rerun()

                    if em["source"] == "outlook":
                        if send_col.button("📤 Approve & Send", key=f"send_{idx}", type="primary"):
                            reply_atts = st.session_state.inbox_attachments.get(f"reply_{em['id']}", [])
                            ok = send_outlook_reply(em["id"], st.session_state[draft_key], reply_atts)
                            if ok:
                                st.success("✅ Reply sent successfully!")
                                mark_outlook_read(em["id"])
                            else:
                                st.error("❌ Failed to send reply.")

                    if mark_col.button("👁️ Mark Read", key=f"mark_{idx}"):
                        if em["source"] == "outlook":
                            mark_outlook_read(em["id"])
                            st.success("Marked as read.")

    st.divider()
    with st.expander("💡 How this works"):
        st.markdown("""
**Outlook Desktop** — just have Outlook open on your PC. This tab reads directly from it, no login needed.

**Autoway** — a background monitor keeps a dedicated Chrome window open on Autoway 24/7. It signs in with Chrome's saved-password autofill (never asks for your password). If you're seeing 0 unread but the site has mail, the monitor might still be waiting for login — check the health strip at the top of the page.
""")


elif page == "👥 Employees":
    st.title("👥 Employees")
    employees = dm.get_employees()
    st.metric("Total Employees", len(employees))

    with st.expander("➕ Add New Employee", expanded=not employees):
        with st.form("add_emp"):
            c1, c2 = st.columns(2)
            name  = c1.text_input("Full Name *")
            email = c2.text_input("Email *")
            phone = c1.text_input("Phone")
            role  = c2.text_input("Role (e.g. Maintenance Engineer)")
            dept  = st.text_input("Department (e.g. Mechanical)")
            if st.form_submit_button("Add Employee", type="primary"):
                if name and email:
                    dm.add_employee(name, email, phone, role, dept)
                    st.success(f"✅ {name} added successfully!")
                    st.rerun()
                else:
                    st.error("Name and Email are required.")

    st.divider()

    if not employees:
        st.info("No employees yet. Add one above.")
    else:
        for emp in employees:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 3, 1])
                c1.markdown(f"**{emp['name']}**  \n`{emp['id']}`")
                c2.markdown(f"📧 {emp['email']}  \n📞 {emp.get('phone','—')}  \n🏷️ {emp.get('role','—')} · {emp.get('department','—')}")
                if c3.button("🗑️", key=f"del_emp_{emp['id']}", help="Delete employee"):
                    dm.delete_employee(emp["id"])
                    st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# PAGE: TASKS
# ════════════════════════════════════════════════════════════════════════════════
elif page == "📋 Tasks":
    st.title("📋 Tasks")
    tasks = dm.get_tasks()
    employees = dm.get_employees()
    emp_map = {e["id"]: e["name"] for e in employees}

    tab_all, tab_pending, tab_ip, tab_done = st.tabs(["All", "⏳ Pending", "🔄 In Progress", "✅ Completed"])

    def render_tasks(task_list):
        if not task_list:
            st.info("No tasks here.")
            return
        priority_colors = {"high": "🔴", "medium": "🟡", "low": "🟢",
                           "High": "🔴", "Medium": "🟡", "Low": "🟢"}
        for t in task_list:
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 3, 2])
                assigned_names = ", ".join(emp_map.get(i, i) for i in t.get("assigned_to_ids", t.get("assigned_to", [])))
                train = t.get("train_id", "")
                train_line = f" · 🚂 Train {train}" if train else ""
                c1.markdown(f"{priority_colors.get(t.get('priority','medium'),'🟡')} **{t['title']}**  \n`{t['id']}` · Due: {t.get('due_date','—')}{train_line}")
                c1.caption(t.get("description",""))
                rec = t.get("recipient", "")
                rem = t.get("remind_days_before", [0])
                if isinstance(rem, (list, tuple)):
                    rem_list = list(rem)
                else:
                    rem_list = [int(rem)] if rem not in (None, "") else [0]
                def _fmt_offset(n):
                    if n == 0:
                        return "same day"
                    if n == 1:
                        return "1d before"
                    if n == 7:
                        return "1w before"
                    return f"{n}d before"
                rem_str = ", ".join(_fmt_offset(n) for n in rem_list) if rem_list else "same day"
                reminder_line = f"  \n🔔 Notify: {rec} ({rem_str})" if rec else ""
                c2.markdown(f"👷 {assigned_names or '—'}  \nPriority: **{str(t.get('priority','medium')).upper()}**{reminder_line}")
                new_status = c3.selectbox(
                    "Status", ["pending", "in_progress", "completed"],
                    index=["pending","in_progress","completed"].index(t.get("status","pending")),
                    key=f"status_{t['id']}"
                )
                if new_status != t.get("status"):
                    dm.update_task(t["id"], status=new_status)
                    st.rerun()
                if c3.button("🔔 Notify Now", key=f"notify_task_{t['id']}"):
                    _spawn_notify(t["id"])
                    st.toast(f"⏳ Sending notifications for task {t['id']}…", icon="📤")
                if c3.button("🗑️ Delete", key=f"del_task_{t['id']}"):
                    dm.delete_task(t["id"])
                    st.rerun()

    with tab_all:
        render_tasks(tasks)
    with tab_pending:
        render_tasks([t for t in tasks if t.get("status") == "pending"])
    with tab_ip:
        render_tasks([t for t in tasks if t.get("status") == "in_progress"])
    with tab_done:
        render_tasks([t for t in tasks if t.get("status") == "completed"])

    st.divider()
    with st.expander("➕ New Task"):
        with st.form("add_task"):
            title = st.text_input("Title *")
            desc  = st.text_area("Description")
            c1, c2 = st.columns(2)
            due_date = c1.date_input("Due Date", value=date.today() + timedelta(days=7))
            priority = c2.selectbox("Priority", ["high", "medium", "low"], index=1)
            trains = dm.get_trains()
            train_options = [""] + [t["id"] for t in trains]
            c3, c4 = st.columns([2, 4])
            train_id = c3.selectbox("Train (optional)", train_options,
                                    format_func=lambda x: f"Train {x}" if x else "— none —")
            recipient = c4.text_input("Notify (phone e.g. 01012345678, or WhatsApp contact name)")
            reminder_options = {
                "Same day (day of the task)": 0,
                "1 day before": 1,
                "2 days before": 2,
                "3 days before": 3,
                "1 week before": 7,
            }
            picked_labels = st.multiselect(
                "When to send WhatsApp reminder",
                list(reminder_options.keys()),
                default=["Same day (day of the task)"],
                help="Pick one or more. The reminder goes out at 08:00 on each selected day.",
            )
            remind_offsets = sorted({reminder_options[l] for l in picked_labels}) or [0]
            assigned = st.multiselect("Assign To", options=[e["id"] for e in employees], format_func=lambda x: emp_map.get(x, x))
            notify_now = st.checkbox(
                "🔔 Send WhatsApp notification now to everyone assigned",
                value=True,
                help="Sends a WhatsApp message immediately to every assigned "
                     "employee (using their phone from the Employees tab) plus the "
                     "manual Notify field. WhatsApp Desktop must be open and logged in."
            )
            if st.form_submit_button("Create Task", type="primary"):
                if title:
                    new_task = dm.add_task(title, desc, assigned, due_date.isoformat(), priority,
                                train_id=train_id, recipient=recipient,
                                remind_days_before=remind_offsets)
                    if notify_now:
                        _spawn_notify(new_task["id"])
                        st.success("✅ Task created — sending WhatsApp notifications now…")
                        st.info("⚠️ WhatsApp Desktop must be open. Sending takes ~10s per recipient.")
                    else:
                        st.success("✅ Task created!")
                    st.rerun()
                else:
                    st.error("Title is required.")


# ════════════════════════════════════════════════════════════════════════════════
# PAGE: TRAINS & ASSIGNMENTS
# ════════════════════════════════════════════════════════════════════════════════
elif page == "🚂 Trains & Assignments":
    st.title("🚂 Trains & Assignments")
    trains = dm.get_trains()
    employees = dm.get_employees()
    assignments = dm.get_train_assignments()
    emp_map = {e["id"]: e["name"] for e in employees}

    st.caption("Assign employees to each train. These assignments are used in WhatsApp reminders.")

    # ── Add / Manage trains ─────────────────────────────────────────────────
    with st.expander("➕ Manage Trains", expanded=not trains):
        c1, c2, c3 = st.columns([1, 2, 1])
        if c1.button(f"🚂 Add all 20 Line 1 trains", type="primary", disabled=len(trains) >= 20):
            added = dm.seed_line1_trains()
            st.success(f"Added {added} train(s). Total now: {len(dm.get_trains())}.")
            st.rerun()

        with c2.form("add_single_train"):
            tc1, tc2, tc3 = st.columns([1, 2, 1])
            new_tid = tc1.text_input("Train ID", placeholder="e.g. 21")
            new_name = tc2.text_input("Name (optional)", placeholder="Train 21")
            if tc3.form_submit_button("Add"):
                if new_tid.strip():
                    t = dm.add_train(new_tid, new_name)
                    st.success(f"Added Train {t['id']}.")
                    st.rerun()

        if trains:
            del_tid = c3.selectbox("Delete", [""] + [t["id"] for t in trains], format_func=lambda x: f"Train {x}" if x else "— pick —", key="del_train_sel")
            if del_tid and c3.button("🗑️ Remove", key="del_train_btn"):
                dm.delete_train(del_tid)
                st.success(f"Removed Train {del_tid}.")
                st.rerun()

    if not trains:
        st.info("No trains yet. Click **Add all 20 Line 1 trains** above to get started.")
    elif not employees:
        st.warning("⚠️ Add employees first in the Employees tab, then come back here to assign them.")
    else:
        st.caption(f"**{len(trains)} train(s)** · **{len(employees)} employee(s)** available")
        cols = st.columns(4)
        for i, train in enumerate(trains):
            tid = train["id"]
            assigned_ids = assignments.get(tid, [])
            with cols[i % 4]:
                with st.container(border=True):
                    st.markdown(f"**🚂 Train {tid}**")
                    new_assigned = st.multiselect(
                        "Assigned",
                        options=[e["id"] for e in employees],
                        default=assigned_ids,
                        format_func=lambda x: emp_map.get(x, x),
                        key=f"train_{tid}",
                        label_visibility="collapsed",
                    )
                    if new_assigned != assigned_ids:
                        dm.assign_employees_to_train(tid, new_assigned)
                        st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# PAGE: SCHEDULE GRID
# ════════════════════════════════════════════════════════════════════════════════
elif page == "📅 Schedule Grid":
    st.title("📅 Maintenance Schedule Grid")

    today = date.today()

    # Smart default: pick the month with actual schedule data closest to today.
    # Priority: today's month if it has entries → next month if it has entries →
    # today's month (empty).
    all_dates = set(dm.get_schedule_grid().keys())

    def _month_has_data(y: int, m: int) -> bool:
        return any(d.startswith(f"{y}-{m:02d}") for d in all_dates)

    if _month_has_data(today.year, today.month):
        default_y, default_m = today.year, today.month
    else:
        nxt = today.replace(day=1) + timedelta(days=32)
        nxt = nxt.replace(day=1)
        if _month_has_data(nxt.year, nxt.month):
            default_y, default_m = nxt.year, nxt.month
        else:
            default_y, default_m = today.year, today.month

    year_options = [today.year, today.year + 1]
    if default_y not in year_options:
        year_options.insert(0, default_y)

    c1, c2, c3 = st.columns([2, 2, 4])
    sel_year  = c1.selectbox("Year",  year_options, index=year_options.index(default_y))
    sel_month = c2.selectbox("Month", list(range(1, 13)), index=default_m - 1, format_func=lambda m: calendar.month_name[m])
    year_month = f"{sel_year}-{sel_month:02d}"

    month_data = dm.get_month_schedule(year_month)
    days_in_month = calendar.monthrange(sel_year, sel_month)[1]
    trains = dm.get_trains()

    if not trains:
        st.warning(
            "⚠️ No trains yet. Add them in the **🚂 Trains & Assignments** tab "
            "(or use the *Add all Line 1 trains* button there) before you can "
            "build a schedule grid."
        )
        st.stop()

    train_order = dm.get_train_order()  # manager's preferred column order

    # ── Build the layout DataFrame (rows = days, cols = No/Date/D/trains/summary) ──
    rows_list = []
    for day in range(1, days_in_month + 1):
        d_iso = f"{year_month}-{day:02d}"
        dt = date(sel_year, sel_month, day)
        entries = month_data.get(d_iso, {})
        meta = dm.get_schedule_meta(d_iso)
        row = {
            "No":   day,
            "Date": dt.strftime("%d/%b/%Y"),
            "D":    dt.strftime("%a"),
        }
        for tid in train_order:
            row[tid] = entries.get(tid, "") or ""
        row["K6"]     = meta.get("K6", "")
        row["K5"]     = meta.get("K5", "")
        row["C_col"]  = meta.get("C", "")
        row["K19"]    = meta.get("K19", "")
        row["Remark"] = meta.get("remark", "")
        rows_list.append(row)
    df = pd.DataFrame(rows_list)

    # Legend
    st.markdown(
        "**Legend:** " + "  ".join(
            f'<span style="background:{c};color:white;padding:2px 8px;border-radius:3px;font-size:11px;margin-right:4px">{k}</span>'
            for k, c in CODE_COLORS.items()
        ) + '  <span style="background:#A6A6A6;color:white;padding:2px 8px;border-radius:3px;font-size:11px">Fri</span>',
        unsafe_allow_html=True,
    )
    st.caption("Coloured preview (read-only). Scroll down for the inline editor.")

    # ── Coloured read-only preview (raw HTML — Streamlit's canvas grid
    # doesn't reliably render per-cell background colours, so we emit our
    # own table so the look matches the manager's printed sheet) ────────
    train_order_set = set(train_order)
    header_cols = ["No", "Date", "D"] + train_order + ["K6", "K5", "C", "K19", "Remark"]

    def _cell_html(col_name: str, val, dow: str) -> str:
        base = ["text-align:center", "padding:2px 4px", "border:1px solid #888",
                "font-size:12px", "white-space:nowrap", "color:#111"]
        text = "" if val in (None, "") else str(val)
        if text.strip().lower() == "nan":
            text = ""
        code = text.strip() if col_name in train_order_set else ""

        if code and code in CODE_COLORS:
            bg = CODE_COLORS[code] or "#FFFFFF"  # codes with no fill (e.g. C) stay white
            fg = "#FFF" if code in CODE_WHITE_TEXT else "#111"
            css = [
                f"background:{bg}",
                f"color:{fg}",
                "font-weight:bold",
                "text-align:center",
                "padding:2px 4px",
                "border:1px solid #888",
                "font-size:12px",
                "white-space:nowrap",
            ]
        elif dow == "Fri":
            css = base + ["background:#A6A6A6"]
        else:
            css = base + ["background:#FFFFFF"]

        css = [c for c in css if c]
        return f'<td style="{";".join(css)}">{text}</td>'

    def _header_cell(name: str, width_hint: str = "") -> str:
        w = f" width:{width_hint};" if width_hint else ""
        return (
            f'<th style="background:#2c3e50;color:white;padding:4px 6px;'
            f'border:1px solid #666;font-size:12px;text-align:center;'
            f'position:sticky;top:0;{w}">{name}</th>'
        )

    header_html = "<tr>" + "".join(
        _header_cell(c, "48px" if c in train_order_set or c in {"K6","K5","C","K19"}
                     else ("32px" if c in {"No","D"} else ("100px" if c=="Date" else "160px" if c=="Remark" else "")))
        for c in header_cols
    ) + "</tr>"

    body_html = ""
    for _, row in df.iterrows():
        dow = row["D"]
        cells_html = "".join(
            _cell_html(col, row["C_col"] if col == "C" else row[col], dow)
            for col in header_cols
        )
        body_html += f"<tr>{cells_html}</tr>"

    table_html = (
        '<div style="overflow-x:auto;max-height:800px;overflow-y:auto;'
        'border:1px solid #444;border-radius:4px">'
        f'<table style="border-collapse:collapse;width:auto;">'
        f'<thead>{header_html}</thead>'
        f'<tbody>{body_html}</tbody>'
        '</table></div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)

    # ── Inline editor ────────────────────────────────────────────────────
    with st.expander("✏️ Edit the schedule inline", expanded=False):
        st.caption(
            "Click any cell to edit. Train cells show a dropdown of valid codes; "
            "K6/K5/C/K19/Remark accept free text. Click **Save Changes** to persist."
        )
        valid_codes = [""] + list(MAINTENANCE_TYPES.keys())
        col_cfg = {
            "No":     st.column_config.NumberColumn("No", disabled=True, width="small"),
            "Date":   st.column_config.TextColumn("Date", disabled=True, width="medium"),
            "D":      st.column_config.TextColumn("D", disabled=True, width="small"),
            "K6":     st.column_config.TextColumn("K6", width="small"),
            "K5":     st.column_config.TextColumn("K5", width="small"),
            "C_col":  st.column_config.TextColumn("C", width="small"),
            "K19":    st.column_config.TextColumn("K19", width="small"),
            "Remark": st.column_config.TextColumn("Remark", width="medium"),
        }
        for tid in train_order:
            col_cfg[tid] = st.column_config.SelectboxColumn(
                tid, options=valid_codes, width="small"
            )
        col_order = ["No", "Date", "D"] + train_order + ["K6", "K5", "C_col", "K19", "Remark"]

        edited = st.data_editor(
            df,
            column_config=col_cfg,
            column_order=col_order,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            height=min(50 + days_in_month * 35, 800),
            key=f"grid_editor_{year_month}",
        )
        # Clearing a cell in st.data_editor stores NaN, not "". Normalise so
        # downstream str(...) never yields the literal string "nan".
        edited = edited.fillna("")

        if st.button("💾 Save Changes", type="primary", key=f"save_grid_{year_month}"):
            def _s(v) -> str:
                if v is None:
                    return ""
                s = str(v).strip()
                return "" if s.lower() == "nan" else s

            changes = 0
            for _, row in edited.iterrows():
                day = int(row["No"])
                d_iso = f"{year_month}-{day:02d}"
                current = dm.get_month_schedule(year_month).get(d_iso, {})
                for tid in train_order:
                    new_code = _s(row[tid]).upper()
                    old_code = current.get(tid, "")
                    if new_code != old_code:
                        if new_code:
                            dm.set_schedule_entry(d_iso, tid, new_code)
                        else:
                            dm.remove_schedule_entry(d_iso, tid)
                        changes += 1
                dm.set_schedule_meta(d_iso, {
                    "K6":     _s(row["K6"]),
                    "K5":     _s(row["K5"]),
                    "C":      _s(row["C_col"]),
                    "K19":    _s(row["K19"]),
                    "remark": _s(row["Remark"]),
                })
            st.success(f"✅ Saved. {changes} schedule cell(s) changed.")
            st.rerun()

    st.divider()

    col_set, col_clear = st.columns(2)

    with col_set:
        with st.form("set_entry"):
            st.subheader("Set Maintenance")
            c1, c2, c3 = st.columns(3)
            sel_train = c1.selectbox("Train", [t["id"] for t in trains], format_func=lambda x: f"Train {x}")
            sel_day   = c2.number_input("Day", 1, days_in_month, today.day if today.month == sel_month else 1)
            sel_code  = c3.selectbox("Code", list(MAINTENANCE_TYPES.keys()))
            if st.form_submit_button("✅ Set", type="primary"):
                d_str = f"{year_month}-{int(sel_day):02d}"
                dm.set_schedule_entry(d_str, sel_train, sel_code)
                st.success(f"Train {sel_train} on {d_str} → {sel_code}")
                st.rerun()

    with col_clear:
        with st.form("clear_entry"):
            st.subheader("Clear Entry")
            c1, c2 = st.columns(2)
            clr_train = c1.selectbox("Train", [t["id"] for t in trains], format_func=lambda x: f"Train {x}", key="clr_t")
            clr_day   = c2.number_input("Day", 1, days_in_month, today.day if today.month == sel_month else 1, key="clr_d")
            if st.form_submit_button("🗑️ Clear"):
                d_str = f"{year_month}-{int(clr_day):02d}"
                dm.remove_schedule_entry(d_str, clr_train)
                st.success(f"Cleared Train {clr_train} on {d_str}")
                st.rerun()

    st.divider()
    st.subheader("📤 Upload Monthly Schedule")
    st.caption(
        "Upload an Excel (.xlsx) or CSV file for the selected month. Two formats accepted: "
        "**matrix** (rows = trains, columns = days 1..31, cells = code) — matches how the grid looks above; "
        "or **long** (three columns: `date`, `train_id`, `code`)."
    )
    up = st.file_uploader("Pick a file", type=["xlsx", "xls", "csv"], key=f"schedule_upload_{year_month}")
    if up is not None:
        try:
            if up.name.lower().endswith(".csv"):
                raw = pd.read_csv(up, dtype=str).fillna("")
            else:
                raw = pd.read_excel(up, dtype=str).fillna("")
        except Exception as e:
            st.error(f"Couldn't read file: {e}")
            raw = None

        if raw is not None and not raw.empty:
            valid_codes = set(MAINTENANCE_TYPES.keys())
            valid_train_ids = {t["id"] for t in trains}
            entries: list[tuple[str, str, str]] = []
            errors: list[str] = []

            cols_lower = {str(c).strip().lower(): c for c in raw.columns}
            is_long = {"date", "train_id", "code"}.issubset(cols_lower.keys())

            if is_long:
                for i, row in raw.iterrows():
                    d = str(row[cols_lower["date"]]).strip()
                    tid = str(row[cols_lower["train_id"]]).strip().zfill(2)
                    code = str(row[cols_lower["code"]]).strip().upper()
                    if not d or not tid or not code:
                        continue
                    try:
                        d_norm = datetime.fromisoformat(d[:10]).date().isoformat()
                    except Exception:
                        errors.append(f"Row {i+2}: invalid date `{d}`")
                        continue
                    if tid not in valid_train_ids:
                        errors.append(f"Row {i+2}: unknown train `{tid}`")
                        continue
                    if code not in valid_codes:
                        errors.append(f"Row {i+2}: unknown code `{code}`")
                        continue
                    entries.append((d_norm, tid, code))
            else:
                first_col = raw.columns[0]
                for i, row in raw.iterrows():
                    label = str(row[first_col]).strip()
                    tid = "".join(ch for ch in label if ch.isdigit())
                    if not tid:
                        continue
                    tid = tid.zfill(2)
                    if tid not in valid_train_ids:
                        errors.append(f"Row {i+2}: unknown train `{label}`")
                        continue
                    for col in raw.columns[1:]:
                        col_str = str(col).strip()
                        if not col_str.isdigit():
                            continue
                        day = int(col_str)
                        if day < 1 or day > days_in_month:
                            continue
                        code = str(row[col]).strip().upper()
                        if not code:
                            continue
                        if code not in valid_codes:
                            errors.append(f"Train {tid} day {day}: unknown code `{code}`")
                            continue
                        d_norm = f"{year_month}-{day:02d}"
                        entries.append((d_norm, tid, code))

            st.markdown(f"**Parsed:** {len(entries)} entries · **Errors:** {len(errors)}")
            if errors:
                with st.expander(f"⚠️ {len(errors)} errors — click to see"):
                    for e in errors[:50]:
                        st.text(e)

            if entries:
                st.dataframe(
                    pd.DataFrame(entries, columns=["date", "train_id", "code"]).head(50),
                    use_container_width=True,
                )
                c_apply, c_replace = st.columns([2, 1])
                replace_month = c_replace.checkbox(
                    "Clear existing entries in this month first",
                    value=False,
                    help=f"Wipes all schedule entries for {year_month} before applying the upload.",
                )
                if c_apply.button(f"✅ Apply {len(entries)} entries", type="primary"):
                    if replace_month:
                        for d in list(dm.get_schedule_grid().keys()):
                            if d.startswith(year_month):
                                for tid in list(dm.get_schedule_grid()[d].keys()):
                                    dm.remove_schedule_entry(d, tid)
                    for d, tid, code in entries:
                        dm.set_schedule_entry(d, tid, code)
                    st.success(f"✅ Applied {len(entries)} schedule entries for {year_month}.")
                    st.rerun()

    st.divider()
    st.subheader("📲 Tomorrow's Maintenance")
    tomorrow_items = dm.get_tomorrows_maintenance()
    if not tomorrow_items:
        st.info("No maintenance scheduled for tomorrow.")
    else:
        for item in tomorrow_items:
            emp_names = ", ".join(e["name"] for e in item.get("employees", []))
            st.markdown(f"🚂 **Train {item['train_id']}** — {badge(item['code'])} {item['code_name']}  \n👷 {emp_names or 'No assignment'}", unsafe_allow_html=True)

    if st.button("📲 Send WhatsApp Reminder Now", type="primary"):
        with st.spinner("Sending..."):
            import subprocess, sys
            _cf = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            result = subprocess.run([sys.executable, "daily_whatsapp.py"], capture_output=True, text=True, creationflags=_cf)
            st.code(result.stdout or result.stderr)


# ════════════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ════════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    config = dm.load_config()

    with st.form("settings_form"):
        st.subheader("General")
        c1, c2 = st.columns(2)
        depot_name   = c1.text_input("Depot Name", value=config.get("depot_name", ""))
        manager_name = c2.text_input("Manager Name", value=config.get("manager_name", ""))
        c1, c2 = st.columns(2)
        manager_phone = c1.text_input(
            "Manager Phone (for 5 PM digest)",
            value=config.get("manager_phone", ""),
            help="Egyptian mobile format e.g. 01012345678. Leave empty to disable the daily end-of-day digest.",
        )
        whatsapp_group = c2.text_input("WhatsApp Group Name", value=config.get("whatsapp_group_name", ""))
        reminder_days = st.number_input("Reminder Days Before", 1, 7, value=int(config.get("reminder_days_before", 1)))

        st.subheader("AI (Anthropic)")
        api_key = st.text_input("Anthropic API Key", value=config.get("anthropic_api_key", ""), type="password")
        st.caption("Get your key from console.anthropic.com")

        st.subheader("Webmail (autoway)")
        wm = config.get("webmail", {})
        wm_url  = st.text_input("Webmail URL", value=wm.get("url", ""))
        c1, c2 = st.columns(2)
        wm_user = c1.text_input("Username", value=wm.get("username", ""))
        wm_pass = c2.text_input("Password", value=wm.get("password", ""), type="password")

        if st.form_submit_button("💾 Save Settings", type="primary"):
            config.update({
                "depot_name": depot_name,
                "manager_name": manager_name,
                "manager_phone": manager_phone,
                "reminder_days_before": reminder_days,
                "whatsapp_group_name": whatsapp_group,
                "anthropic_api_key": api_key,
                "webmail": {"url": wm_url, "type": "autoway", "username": wm_user, "password": wm_pass, "headless": False},
            })
            dm.save_config(config)
            # Reset agent so it picks up new API key
            if "agent" in st.session_state:
                del st.session_state["agent"]
            st.success("✅ Settings saved!")
            st.rerun()

    st.divider()
    st.subheader("📊 System Status")
    import os
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    c1, c2, c3 = st.columns(3)
    c1.metric("Employees", len(dm.get_employees()))
    c2.metric("Tasks", len(dm.get_tasks()))
    c3.metric("Trains", len(dm.get_trains()))
    st.caption(f"Data directory: `{data_dir}`")
    api_configured = bool(config.get("anthropic_api_key"))
    st.markdown(f"AI Agent: {'✅ Configured' if api_configured else '⚠️ API key not set'}")

    st.divider()
    st.subheader("📲 Manual WhatsApp Send")
    if st.button("Send Tomorrow's Reminder to WhatsApp Now"):
        with st.spinner("Running..."):
            _cf = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            result = subprocess.run([sys.executable, "daily_whatsapp.py"], capture_output=True, text=True, cwd=os.path.dirname(__file__), creationflags=_cf)
            st.code(result.stdout or result.stderr or "Done.")
