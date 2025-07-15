#!/usr/bin/env python3
"""
Flask front-end for the Brand-Inventory pipeline.

Routes
------
GET  /               → main HTML page
POST /update-files   → starts Selenium scrape in background
GET  /brands         → list of brands from data/csv
POST /run            → starts full pipeline in background
GET  /status         → last-status.txt contents
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import os, logging, threading
from flask import Flask, render_template, request, jsonify
from inventory_core import get_catalog, scan_brands, run_full_pipeline

# ─── Config ───────────────────────────────────────────────────────────
APP         = Flask(__name__)
DATA_ROOT   = os.path.abspath("data")
CSV_DIR     = os.path.join(DATA_ROOT, "csv")
XLSX_DIR    = os.path.join(DATA_ROOT, "xlsx")
STATUS_FILE = "last_status.txt"
LOG_PATH    = "server.log"

for d in (DATA_ROOT, CSV_DIR, XLSX_DIR):
    os.makedirs(d, exist_ok=True)

# ─── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="💬 %(asctime)s | %(levelname)-7s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8")
    ],
)
log = logging.getLogger("brand-inventory-flask")

def write_status(msg: str):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(msg)

# ─── Routes ──────────────────────────────────────────────────────────
@APP.route("/")
def index():
    return render_template("index.html")
@APP.post("/update-files")
def update_files():
    # 1) clear out old CSVs
    log.info("📥  Clearing old CSVs in %s", CSV_DIR)
    for fn in os.listdir(CSV_DIR):
        if fn.lower().endswith(".csv"):
            try:
                os.remove(os.path.join(CSV_DIR, fn))
            except Exception:
                pass

    # 2) run Selenium scraper synchronously
    log.info("📥  Starting catalog scrape")
    res = get_catalog(CSV_DIR)   # → { ok: bool, msg: str }

    # 3) write the same status your JS used to poll for
    status_msg = ("✅ " if res["ok"] else "❌ ") + res["msg"]
    write_status(status_msg)

    # 4) return real JSON so the front-end can await it
    code = 200 if res["ok"] else 500
    return jsonify(ok=res["ok"], msg=res["msg"]), code

@APP.get("/brands")
def brands():
    lst = scan_brands(CSV_DIR)
    log.info("🔍  Scanned CSVs → %d brands", len(lst))
    return jsonify(lst)

@APP.post("/run")
def run_pipeline():
    data = request.get_json(force=True)
    def bg():
        log.info("🚀  Pipeline started")
        st = run_full_pipeline(CSV_DIR, XLSX_DIR, data["brands"], data["emails"])
        msg = ("✅ " + st["msg"]) if st["ok"] else f"❌ {st['msg']}"
        write_status(msg)
        log.info("🏁  Pipeline finished → %s", msg)

    threading.Thread(target=bg, daemon=True).start()
    return jsonify(ok=True, msg="Pipeline started"), 202

@APP.get("/status")
def status():
    try:
        txt = open(STATUS_FILE, encoding="utf-8").read()
    except FileNotFoundError:
        txt = "No status yet."
    return txt, 200, {"Content-Type":"text/plain; charset=utf-8"}

# ─── Main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("🌐  Starting server on http://127.0.0.1:5000")
    APP.run(host="0.0.0.0", port=5000, threaded=True)
