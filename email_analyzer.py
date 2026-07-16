"""
Email Analyzer — uses Claude to summarize emails and draft professional replies.
"""
import json
import anthropic
from data_manager import DataManager


def _get_client():
    dm = DataManager()
    api_key = dm.load_config().get("anthropic_api_key", "")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


SUMMARY_SYSTEM = """You are a professional executive assistant analyzing emails for a Depot Manager at Cairo Metro Line 1.
For each email, produce:
1. A short 2-3 sentence professional summary
2. The urgency level (high / medium / low)
3. Whether it requires action, and what
4. Whether the sender expects a data reply (e.g. filled-in spreadsheet)
5. A professional draft reply in the same language as the original email (Arabic or English)

Respond in JSON only, matching the schema requested."""


REPLY_SYSTEM = """You are drafting a professional reply on behalf of the Cairo Metro Line 1 Depot Manager.
- Match the tone and language (Arabic or English) of the original email.
- Be concise, respectful, and clear.
- Sign as "Depot Manager, Cairo Metro Line 1".
- If a spreadsheet is attached, acknowledge it and reference the analysis in your reply."""


def analyze_email(email: dict, attachment_analysis: dict = None) -> dict:
    """Analyze one email — return summary, urgency, action needed, and draft reply."""
    client = _get_client()
    if not client:
        return {
            "summary": "⚠️ Anthropic API key not configured. Add it in Settings.",
            "urgency": "unknown",
            "action_required": False,
            "action": "",
            "requires_spreadsheet_reply": False,
            "draft_reply": "",
            "language": "en",
        }

    attachment_context = ""
    if attachment_analysis:
        attachment_context = f"\n\nATTACHED SPREADSHEET ANALYSIS:\n{json.dumps(attachment_analysis, ensure_ascii=False, default=str)[:3000]}"

    user_prompt = f"""Analyze this email:

FROM: {email.get('from','')} <{email.get('from_email','')}>
SUBJECT: {email.get('subject','')}
RECEIVED: {email.get('received','')}
HAS ATTACHMENTS: {email.get('has_attachments', False)}

BODY:
{email.get('body','')[:3000]}
{attachment_context}

Respond in JSON with this exact schema:
{{
  "summary": "2-3 sentence professional summary",
  "urgency": "high|medium|low",
  "action_required": true|false,
  "action": "what needs to be done",
  "requires_spreadsheet_reply": true|false,
  "spreadsheet_reply_notes": "if a spreadsheet reply is needed, describe what columns/data to include",
  "draft_reply": "the full draft reply text, matching the language of the email",
  "language": "ar|en"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        return {
            "summary": f"Analysis error: {e}",
            "urgency": "unknown",
            "action_required": False,
            "action": "",
            "requires_spreadsheet_reply": False,
            "draft_reply": "",
            "language": "en",
        }


def refine_reply(original_email: dict, current_draft: str, user_instruction: str) -> str:
    """Refine a draft reply based on user instructions."""
    client = _get_client()
    if not client:
        return current_draft

    prompt = f"""Original email:
FROM: {original_email.get('from','')}
SUBJECT: {original_email.get('subject','')}
BODY: {original_email.get('body','')[:2000]}

Current draft reply:
{current_draft}

User's instruction to improve the draft:
{user_instruction}

Provide the refined reply only, no meta commentary."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=REPLY_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return current_draft


def suggest_spreadsheet_reply_data(email: dict, attachment_analysis: dict, notes: str) -> list:
    """Given the original spreadsheet and email context, propose rows for a reply spreadsheet."""
    client = _get_client()
    if not client:
        return []

    prompt = f"""Original email from {email.get('from','')}:
Subject: {email.get('subject','')}
Body: {email.get('body','')[:1500]}

Attached spreadsheet analysis:
{json.dumps(attachment_analysis, ensure_ascii=False, default=str)[:2500]}

Reply requirements (what the sender needs back):
{notes}

Generate a JSON array of rows to fill in the reply spreadsheet.
Each row is an object with column-name keys.
Use the original spreadsheet's columns where possible, plus any new columns needed for the response.
Return JSON array only.
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except Exception:
        return []
