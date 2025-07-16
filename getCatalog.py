#!/usr/bin/env python3
"""
getCatalog.py

Selenium script to scrape Dutchie back-office and download CSVs.

Usage:
    python getCatalog.py <download_folder>
"""

import sys
import os
import time
from datetime import datetime
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ── Load credentials from .env ────────────────────────────────────
load_dotenv()
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
if not USERNAME or not PASSWORD:
    print("⚠️  Please set USERNAME and PASSWORD in your .env")
    sys.exit(1)

# ── Store abbreviation map ─────────────────────────────────────────
STORE_ABBR = {
    "Buzz Cannabis - Mission Valley":      "MV",
    "Buzz Cannabis-La Mesa":               "LM",
    "Buzz Cannabis - SORRENTO VALLEY":     "SV",
    "Buzz Cannabis - Lemon Grove":         "LG",
    "Buzz Cannabis (National City)":       "NC",
}

# ── Helpers ────────────────────────────────────────────────────────
def wait_for_new_file(folder, before, timeout=60):
    """Wait up to `timeout` seconds for a new file to show up in `folder`."""
    time.sleep(1)
    end = time.time() + timeout
    while time.time() < end:
        now = set(os.listdir(folder))
        diff = now - before
        if diff:
            return diff.pop()
        time.sleep(1)
    return None

def launch_browser(download_dir):
    """Start headless Chrome, download dir = `download_dir`."""
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
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )
    driver.get("https://dusk.backoffice.dutchie.com/products/catalog")
    return driver

def login(driver):
    """Fill in username/password and submit."""
    wait = WebDriverWait(driver, 10)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='auth_input_username']"))).send_keys(USERNAME)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='auth_input_password']"))).send_keys(PASSWORD)
    login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='auth_button_go-green']")))
    login_button.click()

def open_store_dropdown(driver):
    """Open the store selector dropdown."""
    try:
        w = WebDriverWait(driver, 10)
        dd = w.until(EC.element_to_be_clickable(
            (By.XPATH, "//div[@data-testid='header_select_location']")
        ))
        driver.execute_script("arguments[0].scrollIntoView();", dd)
        dd.click()
        time.sleep(1)
    except TimeoutException:
        print("⚠️  Store dropdown not found")

def select_store(driver, name):
    """Select a store by its exact display name."""
    time.sleep(1)
    open_store_dropdown(driver)
    try:
        w = WebDriverWait(driver, 10)
        li = w.until(EC.element_to_be_clickable((
            By.XPATH,
            f"//li[@data-testid='rebrand-header_menu-item_{name}']"
        )))
        driver.execute_script("arguments[0].click();", li)
        time.sleep(1)
        return True
    except TimeoutException:
        print(f"⚠️  Could not select store '{name}'")
        return False

def export_csv(driver, download_dir, store_name):
    """Trigger Actions→Export CSV and rename the downloaded file."""
    time.sleep(8)  # let page settle
    w = WebDriverWait(driver, 10)
    before = set(os.listdir(download_dir))

    # Open Actions menu
    w.until(EC.element_to_be_clickable((By.ID, "actions-menu-button"))).click()
    # Click Export
    w.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR,
        "li[data-testid='catalog-list-actions-menu-item-export']"
    ))).click()
    # Confirm CSV
    w.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR,
        "[data-testid='export-table-modal-export-csv-button']"
    ))).click()

    fname = wait_for_new_file(download_dir, before, timeout=60)
    if not fname:
        print("⚠️  No CSV downloaded for", store_name)
        return

    abbr = STORE_ABBR.get(store_name, "UNK")
    today = datetime.now().strftime("%m-%d-%Y")
    ext = os.path.splitext(fname)[1]
    new_name = f"{today}_{abbr}{ext}"
    os.rename(
        os.path.join(download_dir, fname),
        os.path.join(download_dir, new_name)
    )
    print(f"✅ Downloaded and renamed → {new_name}")

# ── Main ────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) != 2:
        print("Usage: python getCatalog.py <download_folder>")
        sys.exit(1)

    download_dir = sys.argv[1]
    driver = launch_browser(download_dir)

    try:
        login(driver)
        for store in STORE_ABBR:
            if not select_store(driver, store):
                break
            export_csv(driver, download_dir, store)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
