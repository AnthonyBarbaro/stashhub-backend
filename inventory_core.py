"""
Core helpers shared by both the GUI and Flask versions.
"""

import subprocess, sys, os,json
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
from datetime import datetime
import subprocess

# ---------------------------------------------------------------------------
# get_catalog() – wraps your Selenium script
# ---------------------------------------------------------------------------
STORE_FILE = os.path.join(os.path.dirname(__file__), "stores.json")

def load_store_map():
    if os.path.exists(STORE_FILE):
        with open(STORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}  # empty until user configures

def save_store_map(m):
    with open(STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)
def get_catalog(dest_folder: str) -> dict:
    # compute path to getCatalog.py
    script_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "getCatalog.py")
    )
    # DEBUG!
    print(f"[DEBUG] get_catalog: script_path={script_path}, cwd={os.getcwd()!r}")
    if not os.path.exists(script_path):
        return {"ok": False, "msg": f"getCatalog.py not found at {script_path}"}

    try:
        subprocess.check_call(
            [sys.executable, script_path, dest_folder],
            cwd=os.path.dirname(script_path),
        )
        return {"ok": True, "msg": "Catalog downloaded"}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "msg": f"getCatalog.py failed: {e}"}


# ---------------------------------------------------------------------------
# scan_brands() – collects unique brands from CSVs
# ---------------------------------------------------------------------------
def scan_brands(csv_dir: str) -> list[str]:
    brands = set()
    for fn in os.listdir(csv_dir):
        if fn.lower().endswith(".csv"):
            try:
                df = pd.read_csv(os.path.join(csv_dir, fn), usecols=["Brand"])
                brands.update(df["Brand"].dropna().astype(str).str.strip().str.lower().unique())
            except Exception:
                pass
    return sorted(brands)

# ---------------------------------------------------------------------------
# run_full_pipeline() – XLSX gen, Drive upload, email
# ---------------------------------------------------------------------------
def run_full_pipeline(csv_dir: str,
                      output_dir: str,
                      selected_brands: list[str],
                      emails: str,
                      tokens_dir: str) -> dict:
    from brand_inventory_gui_code import (
        generate_brand_reports,
        upload_brand_reports_to_drive,
        send_email_with_gmail_html,
        save_config,
    )
    import inspect, sys
    print(">>> using function from:", upload_brand_reports_to_drive.__module__, 
        " @ ", sys.modules[upload_brand_reports_to_drive.__module__].__file__)
    print(">>> signature:", inspect.signature(upload_brand_reports_to_drive))
    all_brand_map = {}
    for file in os.listdir(csv_dir):
        if file.lower().endswith(".csv"):
            brand_map = generate_brand_reports(
                os.path.join(csv_dir, file), output_dir, selected_brands
            )
            for k, v in brand_map.items():
                all_brand_map.setdefault(k, []).extend(v)

    if not all_brand_map:
        return {"ok": False, "msg": "No XLSX generated–check filters/CSVs."}
    print("upload_brand_reports_to_drive")
    links = upload_brand_reports_to_drive(all_brand_map, tokens_dir)
    if not links:
        return {"ok": False, "msg": "Drive upload failed."}

    body = "".join(f"<h3>{b}</h3><p><a href='{url}'>{url}</a></p>" for b, url in links.items())
    html = f"<html><body><p>Hello,</p>{body}<p>– Brand Inventory Bot</p></body></html>"

    send_email_with_gmail_html("Brand Inventory Drive Links", html, emails, tokens_dir)
    save_config(csv_dir, output_dir)
    return {"ok": True, "msg": "Pipeline finished & email sent."}
