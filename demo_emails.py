"""
Demo mode — provides fake unread emails so you can see the Inbox Assistant
working without needing Outlook or Autoway connected.
"""
from datetime import datetime, timedelta

DEMO_EMAILS = [
    {
        "id": "demo-1",
        "source": "outlook",
        "from": "Eng. Karim Salah",
        "from_email": "k.salah@metro.com",
        "to": "depot.manager@metro.com",
        "subject": "Urgent: Train 7 brake pressure drop reported",
        "body": (
            "Dear Depot Manager,\n\n"
            "During today's morning service on Train 7, our driver reported a "
            "sudden drop in brake line pressure between Sadat and Nasser stations.\n"
            "The train was pulled out of service at 09:45 and is currently at the depot.\n\n"
            "Kindly assign a brake technician for full diagnostic today, and confirm "
            "estimated time back in service.\n\nRegards,\nKarim Salah\nOperations Control"
        ),
        "received": (datetime.now() - timedelta(hours=3)).isoformat(),
        "unread": True,
        "has_attachments": False,
        "attachments": [],
    },
    {
        "id": "demo-2",
        "source": "outlook",
        "from": "أ. سامي عبد الحكيم",
        "from_email": "s.abdelhakim@metro.com",
        "to": "depot.manager@metro.com",
        "subject": "طلب تقرير الصيانة الشهري - يوليو 2026",
        "body": (
            "السيد مدير الديبو المحترم،\n\n"
            "برجاء تعبئة الشيت المرفق بتقرير الصيانة الشهري لكل قطارات خط 1 "
            "خلال شهر يوليو، والمتضمن:\n"
            "  - رقم القطار\n"
            "  - نوع الصيانة\n"
            "  - التاريخ الفعلي للتنفيذ\n"
            "  - اسم الفني المسؤول\n"
            "  - ملاحظات إن وجدت\n\n"
            "المطلوب إرسال الشيت مكتملاً قبل يوم 25 يوليو.\n\n"
            "وتفضلوا بقبول فائق الاحترام،\nسامي عبد الحكيم\nإدارة الصيانة العامة"
        ),
        "received": (datetime.now() - timedelta(hours=8)).isoformat(),
        "unread": True,
        "has_attachments": True,
        "attachments": [{"filename": "Monthly_Maintenance_Report_July.xlsx", "size": 24500}],
    },
    {
        "id": "demo-3",
        "source": "autoway",
        "from": "Hyundai Rotem Support",
        "from_email": "support@hyundai-rotem.com",
        "to": "depot.line1@metro.com",
        "subject": "Firmware update available — CAF traction control units",
        "body": (
            "Dear Cairo Metro Line 1 Team,\n\n"
            "Firmware v3.4.2 is now available for the traction control units on "
            "your CAF fleet. The update improves regenerative braking efficiency "
            "by ~4% and addresses a rare fault code (E-217).\n\n"
            "The update takes approximately 45 minutes per train and requires the "
            "train to be at rest with power isolated.\n\n"
            "Please advise which trains you'd like scheduled first.\n\n"
            "Best regards,\nHyundai Rotem Global Support"
        ),
        "received": (datetime.now() - timedelta(days=1)).isoformat(),
        "unread": True,
        "has_attachments": False,
        "attachments": [],
    },
    {
        "id": "demo-4",
        "source": "outlook",
        "from": "Finance Dept",
        "from_email": "finance@metro.com",
        "to": "depot.manager@metro.com",
        "subject": "Q3 Spare Parts Budget Approval",
        "body": (
            "Dear Depot Manager,\n\n"
            "Your Q3 spare parts requisition (Ref: DEP/2026/Q3/017) has been "
            "reviewed and pre-approved for 2.4M EGP.\n\n"
            "Please confirm receipt and provide final vendor list by end of week "
            "so we can proceed with the purchase orders.\n\n"
            "Regards,\nFinance Department"
        ),
        "received": (datetime.now() - timedelta(days=2)).isoformat(),
        "unread": True,
        "has_attachments": False,
        "attachments": [],
    },
]

DEMO_ATTACHMENT_ANALYSIS = {
    "demo-2": {
        "file": "Monthly_Maintenance_Report_July.xlsx",
        "sheets": {
            "Report": {
                "rows": 20,
                "columns": ["Train ID", "Maintenance Type", "Actual Date", "Technician", "Notes"],
                "preview": [
                    {"Train ID": t, "Maintenance Type": "", "Actual Date": "", "Technician": "", "Notes": ""}
                    for t in range(1, 6)
                ],
                "sample_stats": {},
            }
        },
    }
}
