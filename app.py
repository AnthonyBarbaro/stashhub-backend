#!/usr/bin/env python3
"""
Brand‑Inventory Flask front‑end (multi‑user, secure)

Key endpoints
 • /login  – users authenticate (accounts pre‑created by admin)
 • /logout – end session
 • /setup  – per‑user wizard  → <user>/stores.json
 • /update-files – runs getCatalog.py for this user’s stores
 • /brands, /run – unchanged pipeline endpoints
 • /status – plain‑text progress
"""

import os, sys, json, subprocess, threading, logging, time
from pathlib import Path
from functools import wraps
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, abort, send_from_directory)
from flask_login import (LoginManager, login_user, login_required,
                         logout_user, current_user, UserMixin)

# ────── basic setup ───────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent
DATA_ROOT  = ROOT / "data"
USERS_FILE = DATA_ROOT / "users.json"

load_dotenv()
APP = Flask(__name__, static_folder="static", template_folder="templates")
APP.secret_key = os.getenv("SECRET_KEY", "dev‑change‑me")          # session cookie
APP.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

login_manager = LoginManager(APP)
login_manager.login_view = "login"

# ────── logging ───────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
    format="💬 %(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("inventory‑flask")

# ────── user model & helpers ─────────────────────────────────┐
class User(UserMixin):
    def __init__(self, uid: int, username: str, pw_hash: str):
        self.id = uid
        self.username = username
        self.pw_hash = pw_hash

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.pw_hash, raw)

def load_users() -> dict[str, User]:
    if not USERS_FILE.exists():
        log.error("🚫 users.json not found. Create it first.")
        return {}
    raw = json.loads(USERS_FILE.read_text())
    return {
        uname: User(v["id"], uname, v["password_hash"])
        for uname, v in raw.items()
    }

from werkzeug.security import generate_password_hash, check_password_hash

def load_and_upgrade_users(db_path: Path) -> dict[str, dict]:
    if not db_path.exists():
        raise RuntimeError("users.json missing → create one first.")
    dirty = False
    data  = json.loads(db_path.read_text())

    for uname, rec in data.items():
        # If admin provided a plain password, hash & upgrade 🆙
        if "password" in rec:
            plain = rec.pop("password")
            rec["password_hash"] = generate_password_hash(
                plain, method="pbkdf2:sha256", salt_length=16
            )
            dirty = True
            log.info("🔑 Hashed password for user '%s' and removed plain text.", uname)

    if dirty:  # write the upgraded file atomically
        tmp = db_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(db_path)
        log.info("💾 users.json upgraded with hashed passwords.")

    return {
        u: User(rec["id"], u, rec["password_hash"])
        for u, rec in data.items()
    }

USERS = load_and_upgrade_users(USERS_FILE)

@login_manager.user_loader
def _load(uid: str):
    return next((u for u in USERS.values() if str(u.id) == uid), None)

# ────── per‑user path helper ─────────────────────────────────┘
def get_token_paths(tokens_dir: Path):
    """
    Returns (token_drive.json, token_gmail.json) paths inside the user's tokens/ folder.
    Ensures the directory exists.
    """
    tokens_dir.mkdir(parents=True, exist_ok=True)
    return (
        tokens_dir / "token_drive.json",
        tokens_dir / "token_gmail.json"
    )

def user_paths():
    """Return (user_dir, csv_dir, xlsx_dir, status_file, stores_json)."""
    udir = DATA_ROOT / current_user.username
    csv  = udir / "csv"
    xlsx = udir / "xlsx"
    tokens  = udir / "tokens"
    status = udir / "last_status.txt"
    stores = udir / "stores.json"
    for d in (csv, xlsx):
        d.mkdir(parents=True, exist_ok=True)
    return udir, csv, xlsx, status, stores, tokens

# ────── 1. AUTH ROUTES ────────────────────────────────────────
@APP.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form["username"]
        pw    = request.form["password"]
        user  = USERS.get(uname)
        if user and user.check_password(pw):
            login_user(user)
            (DATA_ROOT / user.username / "tokens").mkdir(parents=True, exist_ok=True)
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@APP.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ────── 2. SETUP WIZARD ───────────────────────────────────────
@APP.route("/setup", methods=["GET"])
@login_required
def setup_get():
    _, _, _, _, stores_json, _ = user_paths()
    cfg = {"username": "", "password": "", "store_map": {}}
    if stores_json.exists():
        try:
            cfg = json.loads(stores_json.read_text())
        except json.JSONDecodeError:
            log.warning("🛑 stores.json corrupted for %s", current_user.username)
    return render_template("setup.html", cfg=cfg)

@APP.route("/setup", methods=["POST"])
@login_required
def setup_post():
    _, _, _, _, stores_json, _ = user_paths()
    data = request.get_json(force=True)
    cfg  = {
        "username":  data.get("username", "").strip(),
        "password":  data.get("password", "").strip(),
        "store_map": data.get("store_map", {}),
    }
    stores_json.write_text(json.dumps(cfg, indent=2), encoding="utf‑8")
    return jsonify(ok=True, msg="Settings saved")

# ────── 3. MAIN UI ────────────────────────────────────────────
@APP.route("/")
@login_required
def index():
    _, _, _, _, stores_json, _ = user_paths()
    if not stores_json.exists():
        return redirect(url_for("setup_get"))
    return render_template("index.html")

# ────── 4. UPDATE FILES (getCatalog) ──────────────────────────
@APP.post("/update-files")
@login_required
def update_files():
    _, csv_dir, _, status_file, stores_json, tokens_dir = user_paths()
    cfg = json.loads(stores_json.read_text())

    if not (cfg.get("username") and cfg.get("password") and cfg["store_map"]):
        return jsonify(ok=False, msg="Run setup first"), 400

    for f in csv_dir.glob("*.csv"):   # clear old CSVs
        f.unlink(missing_ok=True)

    def run_store(store_name, abbr, user, pw):
        write_status(status_file, f"⏳ Scraping {store_name} …")
        cmd = [sys.executable, "getCatalog.py", str(csv_dir),
               "--username", user, "--password", pw]
        env = os.environ.copy()
        env.update(STORE_NAME=store_name, STORE_ABBR=abbr)
        try:
            subprocess.check_call(cmd, cwd=ROOT, env=env)
            write_status(status_file, f"✅ {store_name} downloaded")
        except subprocess.CalledProcessError:
            write_status(status_file, f"❌ Failed to download from {store_name}")
            return False
        except Exception as e:
            write_status(status_file, f"❌ Unexpected error: {e}")
            return False
        return True

    def worker():
        for sname, abbr in cfg["store_map"].items():
            success = run_store(sname, abbr, cfg["username"], cfg["password"])
            if not success:
                break
        else:
            write_status(status_file, "✅ All stores done")

    threading.Thread(target=worker, daemon=True).start()
    return jsonify(ok=True, msg="Scrape started"), 202
# ────── 5. BRANDS & PIPELINE ──────────────────────────────────
from inventory_core import scan_brands, run_full_pipeline

@APP.get("/brands")
@login_required
def brands():
    _, csv_dir, _, _, _, _ = user_paths()
    lst = scan_brands(csv_dir)
    log.info("🔍 %s → %d brands", current_user.username, len(lst))
    return jsonify(lst)

@APP.post("/run")
@login_required
def run_pipeline():
    _, csv_dir, xlsx_dir, status_file, _, tokens_dir = user_paths()
    data = request.get_json(force=True)

    def bg():
        try:
            st = run_full_pipeline(csv_dir, xlsx_dir, data["brands"], data["emails"], tokens_dir)
            write_status(status_file,
                ("✅ " if st["ok"] else "❌ ") + st["msg"])
        except Exception as e:
            write_status(status_file, "❌ Pipeline error: " + str(e))
    threading.Thread(target=bg, daemon=True).start()
    return jsonify(ok=True, msg="Pipeline started"), 202

@APP.get("/status")
@login_required
def status():
    _,_, _, _, status_file, _ = user_paths()
    return (status_file.read_text(encoding="utf-8") if status_file.exists() else "No status."), 200, {
        "Content-Type": "text/plain; charset=utf-8"}

# ────── util ────────────────────────────────────────────
def write_status(path: Path, txt: str):
    path.write_text(txt, encoding="utf-8")

# ────── run ─────────────────────────────────────────────
if __name__ == "__main__":
    APP.run(port=5000, threaded=True)
