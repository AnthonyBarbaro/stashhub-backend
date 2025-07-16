#!/usr/bin/env python3
"""
Brand‑Inventory Flask front‑end
  • /setup  – wizard → stores.json  (username, password, store_map)
  • /update-files – launches getCatalog.py once per store
  • /brands, /run – unchanged pipeline endpoints
  • /status – plain‑text progress
"""

import os, sys, json, subprocess, threading, logging
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for

# ────── paths ──────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent
DATA_ROOT   = ROOT / "data"
CSV_DIR     = DATA_ROOT / "csv"
XLSX_DIR    = DATA_ROOT / "xlsx"
STATUS_FILE = DATA_ROOT / "last_status.txt"
STORES_JSON = ROOT / "stores.json"

for d in (CSV_DIR, XLSX_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ────── logging ────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
    format="💬 %(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("inventory‑flask")

# ────── helpers ────────────────────────────────────────
def load_cfg() -> dict:
    if STORES_JSON.exists():
        try:
            return json.loads(STORES_JSON.read_text(encoding="utf‑8"))
        except json.JSONDecodeError:
            log.warning("stores.json is corrupted → resetting")
    return {"username": "", "password": "", "store_map": {}}

def save_cfg(cfg: dict):
    STORES_JSON.write_text(json.dumps(cfg, indent=2), encoding="utf‑8")

def write_status(s): 
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(s)

# ────── Flask app ──────────────────────────────────────
APP = Flask(__name__)

# ----------  Setup wizard  -----------------------------
@APP.route("/setup", methods=["GET"])
def setup_get():
    return render_template("setup.html", cfg=load_cfg())

@APP.route("/setup", methods=["POST"])
def setup_post():
    data = request.get_json(force=True)
    cfg  = {
        "username":  data.get("username", "").strip(),
        "password":  data.get("password", "").strip(),
        "store_map": data.get("store_map", {}),
    }
    save_cfg(cfg)
    return jsonify(ok=True, msg="Settings saved")

# ----------  Main UI  ----------------------------------
@APP.route("/")
def index():
    if not STORES_JSON.exists():
        return redirect(url_for("setup_get"))
    return render_template("index.html")

# ----------  Catalog scrape  ---------------------------
@APP.post("/update-files")
def update_files():
    cfg = load_cfg()
    if not (cfg.get("username") and cfg.get("password") and cfg["store_map"]):
        return jsonify(ok=False, msg="Run setup first"), 400

    # clear old CSVs
    for f in CSV_DIR.glob("*.csv"):
        f.unlink(missing_ok=True)

    def worker():
        user = cfg["username"]
        pw   = cfg["password"]

        for store_name, abbr in cfg["store_map"].items():
            write_status(f"⏳ Scraping {store_name} …")
            cmd = [
                sys.executable, "getCatalog.py", str(CSV_DIR),
                "--username", user, "--password", pw
            ]
            env = os.environ.copy()
            env["STORE_NAME"] = store_name
            env["STORE_ABBR"] = abbr
            try:
                subprocess.check_call(cmd, cwd=ROOT, env=env)
                write_status(f"✅ {store_name} downloaded")
            except subprocess.CalledProcessError:
                write_status(f"❌ Failed to download from {store_name}")
                break
            except Exception as e:
                write_status(f"❌ Unexpected error: {e}")
                break
        else:
            write_status("✅ All stores done")

    threading.Thread(target=worker, daemon=True).start()
    return jsonify(ok=True, msg="Scrape started"), 202

# ----------  Brand / pipeline  -------------------------
from inventory_core import scan_brands, run_full_pipeline

@APP.get("/brands")
def brands():
    lst = scan_brands(CSV_DIR)
    log.info("🔍  Scanned CSVs → %d brands", len(lst))
    return jsonify(lst)

@APP.post("/run")
def run_pipeline():
    print("✅ /run endpoint hit")  # DEBUG
    data = request.get_json(force=True)
    print("📦 received brands:", data.get("brands"))
    print("📧 received emails:", data.get("emails"))

    def bg():
        try:
            st = run_full_pipeline(CSV_DIR, XLSX_DIR,
                                   data["brands"], data["emails"])
            print("📊 run_full_pipeline result:", st)
            write_status(("✅ " if st["ok"] else "❌ ") + st["msg"])
        except Exception as e:
            print("🔥 Exception in pipeline:", e)
            write_status("❌ Internal error: " + str(e))

    threading.Thread(target=bg, daemon=True).start()
    return jsonify(ok=True, msg="Pipeline started"), 202


@APP.get("/status")
def status():
    try:
        return STATUS_FILE.read_text(encoding="utf‑8"), 200, {
            "Content-Type": "text/plain; charset=utf-8"}
    except FileNotFoundError:
        return "No status yet.", 200

if __name__ == "__main__":
    APP.run(port=5000, threaded=True)
