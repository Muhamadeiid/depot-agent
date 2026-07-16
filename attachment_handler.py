"""
Attachment Handler — download, analyze and reply to Excel/CSV attachments.
"""
import os
import json
from pathlib import Path

DOWNLOADS_DIR = str(Path.home() / "Downloads")


def analyze_spreadsheet(filepath: str) -> dict:
    """Read an Excel/CSV file and return a summary of its contents."""
    try:
        import pandas as pd
    except ImportError:
        return {"error": "pandas not installed"}

    if not os.path.exists(filepath):
        return {"error": f"File not found: {filepath}"}

    ext = os.path.splitext(filepath)[1].lower()

    try:
        if ext in [".xlsx", ".xls", ".xlsm"]:
            sheets = pd.read_excel(filepath, sheet_name=None)
            summary = {"file": os.path.basename(filepath), "sheets": {}}
            for name, df in sheets.items():
                summary["sheets"][name] = {
                    "rows": len(df),
                    "columns": list(df.columns.astype(str)),
                    "preview": df.head(10).to_dict(orient="records"),
                    "sample_stats": _safe_describe(df),
                }
            return summary
        elif ext == ".csv":
            df = pd.read_csv(filepath)
            return {
                "file": os.path.basename(filepath),
                "rows": len(df),
                "columns": list(df.columns.astype(str)),
                "preview": df.head(10).to_dict(orient="records"),
                "sample_stats": _safe_describe(df),
            }
        else:
            return {"file": os.path.basename(filepath), "error": f"Unsupported format: {ext}"}
    except Exception as e:
        return {"error": f"Failed to read {filepath}: {e}"}


def _safe_describe(df):
    try:
        numeric = df.select_dtypes(include="number")
        if numeric.empty:
            return {}
        return numeric.describe().to_dict()
    except Exception:
        return {}


def create_reply_spreadsheet(original_path: str, reply_data: list, output_name: str = None) -> str:
    """
    Create a professional response spreadsheet based on the original.
    reply_data = list of dicts to write into the reply sheet.
    Returns path of the created file.
    """
    try:
        import pandas as pd
    except ImportError:
        return ""

    if not output_name:
        base = os.path.splitext(os.path.basename(original_path))[0]
        output_name = f"REPLY_{base}.xlsx"

    output_path = os.path.join(DOWNLOADS_DIR, output_name)
    df = pd.DataFrame(reply_data)

    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Response", index=False)

            # Try to load and copy over the original sheet as reference
            try:
                original_sheets = pd.read_excel(original_path, sheet_name=None)
                for name, sheet_df in original_sheets.items():
                    sheet_df.to_excel(writer, sheet_name=f"Original_{name}"[:31], index=False)
            except Exception:
                pass
        return output_path
    except Exception as e:
        return ""


def list_downloaded_attachments() -> list:
    """List all files currently in the Downloads folder."""
    if not os.path.isdir(DOWNLOADS_DIR):
        return []
    files = []
    for name in os.listdir(DOWNLOADS_DIR):
        full = os.path.join(DOWNLOADS_DIR, name)
        if os.path.isfile(full):
            files.append({
                "name": name,
                "path": full,
                "size": os.path.getsize(full),
                "modified": os.path.getmtime(full),
            })
    return sorted(files, key=lambda x: -x["modified"])
