#!/usr/bin/env python3
"""
getCatalog.py (single‑store version)

• With --list-stores          → prints JSON list of store keys
• With STORE_NAME/STORE_ABBR  → downloads *one* store’s CSV
"""

import argparse, json, os, sys, time
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ─── CLI args ────────────────────────────────────────────
def cli():
    p = argparse.ArgumentParser()
    p.add_argument("download_folder", help="Folder for CSVs")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--list-stores", action="store_true")
    return p.parse_args()

# ─── Setup browser ───────────────────────────────────────
def launch_browser(download_dir):
    os.makedirs(download_dir, exist_ok=True)
    opts = Options()
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("start-maximized")
    opts.add_argument("--headless=new")
    opts.add_experimental_option('excludeSwitches', ['enable-logging'])
    opts.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    })
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

# ─── Selenium actions ─────────────────────────────────────
def login(driver, user, pw):
    driver.get("https://dusk.backoffice.dutchie.com/products/catalog")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='auth_input_username']"))).send_keys(user)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='auth_input_password']"))).send_keys(pw)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='auth_button_go-green']"))).click()
    time.sleep(2)

def open_store_dropdown(driver):
    try:
        wait = WebDriverWait(driver, 10)
        dd = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@data-testid='header_select_location']")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dd)
        dd.click()
        time.sleep(1)
    except TimeoutException:
        print("⚠️  Could not open store dropdown")

def list_store_keys(driver):
    open_store_dropdown(driver)
    items = driver.find_elements(By.CSS_SELECTOR, "li[data-testid^='rebrand-header_menu-item_']")
    return [i.get_attribute("data-testid").split("_", 1)[1] for i in items]

def select_store(driver, store_name):
    open_store_dropdown(driver)
    try:
        wait = WebDriverWait(driver, 10)
        # Find <li> where .text matches the visible name
        options = driver.find_elements(By.CSS_SELECTOR, "li[data-testid^='rebrand-header_menu-item_']")
        for option in options:
            if option.text.strip() == store_name:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", option)
                driver.execute_script("arguments[0].click();", option)
                print(f"✅ Selected store: {store_name}", flush=True)
                time.sleep(2)
                return
        raise TimeoutException(f"No matching <li> for: {store_name}")
    except Exception as e:
        print(f"❌ Store selection failed: {e}", file=sys.stderr)
        raise

def wait_for_new_file(folder, before, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        diff = set(os.listdir(folder)) - before
        if diff:
            return diff.pop()
        time.sleep(1)
    return None

def export_csv(driver, folder, abbr):
    time.sleep(6)  # Let catalog settle
    wait = WebDriverWait(driver, 10)
    before = set(os.listdir(folder))

    wait.until(EC.element_to_be_clickable((By.ID, "actions-menu-button"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "li[data-testid='catalog-list-actions-menu-item-export']"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='export-table-modal-export-csv-button']"))).click()

    fname = wait_for_new_file(folder, before)
    if not fname:
        raise RuntimeError("❌ CSV download timed out")

    today = datetime.now().strftime("%m-%d-%Y")
    new_name = f"{today}_{abbr}{Path(fname).suffix}"
    Path(folder, fname).rename(Path(folder, new_name))
    print(f"✅ CSV saved → {new_name}")

# ─── Main ─────────────────────────────────────────────────
def main():
    args = cli()
    folder = args.download_folder
    user   = args.username
    pw     = args.password

    store_name = os.getenv("STORE_NAME")
    store_abbr = os.getenv("STORE_ABBR")

    driver = launch_browser(folder)

    try:
        login(driver, user, pw)

        if args.list_stores:
            print(json.dumps(list_store_keys(driver)))
            return

        if not (store_name and store_abbr):
            print("❌ STORE_NAME and STORE_ABBR must be set in env", file=sys.stderr)
            sys.exit(1)

        select_store(driver, store_name)
        export_csv(driver, folder, store_abbr)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
