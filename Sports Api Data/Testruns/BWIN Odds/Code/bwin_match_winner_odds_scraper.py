#!/usr/bin/env python3
import os
import re
import shutil
import time
from glob import glob
from datetime import datetime, timezone

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# ---------------------------
# Konfiguration
# ---------------------------
TARGET_URL = (
    "https://sports.bwin.de/de/sports/"
    "fu%C3%9Fball-4/wetten/deutschland-17/bundesliga-43"
)
OUTPUT_DIR = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Testruns/BWIN Odds/Datacollection"
PAGE_LOAD_WAIT_SECONDS = 8
WAIT_TIMEOUT_SECONDS = 35

# Optional:
# 1) per Umgebungsvariable BWIN_WEBDRIVER_PATH explizit setzen
# 2) Wenn leer, nutzt Selenium den Standard-Mechanismus
WEBDRIVER_PATH = os.getenv("BWIN_WEBDRIVER_PATH", "").strip()
PREFERRED_BROWSER = os.getenv("BWIN_BROWSER", "chrome").strip().lower()
SELENIUM_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".selenium_cache")

# Keep Selenium Manager cache inside the project to avoid permission issues on locked profiles.
os.makedirs(SELENIUM_CACHE_DIR, exist_ok=True)
os.environ.setdefault("SE_CACHE_PATH", SELENIUM_CACHE_DIR)


ODD_PATTERN = re.compile(r"^\d+[.,]\d{2}$")
TEAM_CLEANUP_PATTERN = re.compile(r"\b(?:1|X|2|\d+[.,]\d{2})\b", re.IGNORECASE)


def now_utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_local_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_decimal(text):
    cleaned = text.replace(",", ".").strip()
    if ODD_PATTERN.match(text.strip()):
        return float(cleaned)
    return None


def discover_driver_paths(browser_name):
    explicit = []

    if browser_name == "edge":
        from_path = shutil.which("msedgedriver")
        if from_path:
            explicit.append(from_path)
        winget_path = os.path.expandvars(
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Microsoft.EdgeDriver_Microsoft.Winget.Source_8wekyb3d8bbwe\msedgedriver.exe"
        )
        if os.path.exists(winget_path):
            explicit.append(winget_path)
        explicit.append(r"C:\WebDriver\msedgedriver.exe")

    if browser_name == "chrome":
        from_path = shutil.which("chromedriver")
        if from_path:
            explicit.append(from_path)
        explicit.extend(glob(os.path.expandvars(r"%USERPROFILE%\.cache\selenium\chromedriver\win64\*\chromedriver.exe")))
        explicit.append(r"C:\WebDriver\chromedriver.exe")

    deduped = []
    seen = set()
    for path in explicit:
        norm = os.path.normcase(path)
        if norm in seen:
            continue
        seen.add(norm)
        if os.path.exists(path):
            deduped.append(path)
    return deduped


def has_chrome_binary():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    return any(os.path.exists(path) for path in candidates)


def build_driver(browser_name):
    last_exception = None

    browser_order = [browser_name]
    if browser_name == "chrome":
        browser_order.append("edge")
    elif browser_name == "edge":
        browser_order.append("chrome")
    else:
        browser_order = ["chrome", "edge"]

    for candidate in browser_order:
        try:
            if candidate == "chrome":
                if not has_chrome_binary():
                    continue
                options = ChromeOptions()
                options.add_argument("--headless=new")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--disable-blink-features=AutomationControlled")
                if WEBDRIVER_PATH:
                    return webdriver.Chrome(service=ChromeService(WEBDRIVER_PATH), options=options)
                for local_driver in discover_driver_paths("chrome"):
                    try:
                        return webdriver.Chrome(service=ChromeService(local_driver), options=options)
                    except Exception:
                        pass
                return webdriver.Chrome(options=options)

            if candidate == "edge":
                options = EdgeOptions()
                options.add_argument("--headless=new")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                if WEBDRIVER_PATH:
                    return webdriver.Edge(service=EdgeService(WEBDRIVER_PATH), options=options)
                for local_driver in discover_driver_paths("edge"):
                    try:
                        return webdriver.Edge(service=EdgeService(local_driver), options=options)
                    except Exception:
                        pass
                return webdriver.Edge(options=options)

        except Exception as exc:
            last_exception = exc

    raise RuntimeError(
        "Kein WebDriver gestartet. Installiere z.B. 'winget install Microsoft.EdgeDriver' "
        "oder setze BWIN_WEBDRIVER_PATH auf chromedriver/msedgedriver."
    ) from last_exception


def click_cookie_banner_if_present(driver):
    cookie_xpaths = [
        "//button[contains(., 'Akzeptieren')]",
        "//button[contains(., 'Alle akzeptieren')]",
        "//button[contains(., 'Accept all')]",
        "//button[contains(., 'Accept All')]",
    ]
    for xp in cookie_xpaths:
        try:
            btn = WebDriverWait(driver, 4).until(EC.element_to_be_clickable((By.XPATH, xp)))
            btn.click()
            time.sleep(1)
            return
        except Exception:
            continue


def normalized_lines(text):
    lines = []
    for raw in text.splitlines():
        t = raw.strip()
        if not t:
            continue
        lines.append(t)
    return lines


def extract_teams_from_row_text(row_text):
    candidates = []
    for line in normalized_lines(row_text):
        if ODD_PATTERN.match(line):
            continue
        compact = TEAM_CLEANUP_PATTERN.sub("", line).strip()
        if len(compact) < 2:
            continue
        if any(char.isalpha() for char in compact):
            candidates.append(compact)

    unique = []
    seen = set()
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)

    if len(unique) >= 2:
        return unique[0], unique[1]
    return None, None


def find_event_rows(driver):
    ms_events = driver.find_elements(By.CSS_SELECTOR, "ms-event")
    if ms_events:
        return ms_events

    selector_candidates = [
        "[data-test-id*='event']",
        "[data-testid*='event']",
        "ms-event",
        "article",
        "li",
    ]

    rows = []
    for selector in selector_candidates:
        found = driver.find_elements(By.CSS_SELECTOR, selector)
        if found:
            rows.extend(found)

    # Deduplizieren
    deduped = []
    seen_ids = set()
    for row in rows:
        rid = row.id
        if rid not in seen_ids:
            seen_ids.add(rid)
            deduped.append(row)
    return deduped


def extract_match_winner_rows(driver):
    extracted = []
    seen_match_keys = set()

    for row in find_event_rows(driver):
        row_text = row.text or ""
        row_lines = normalized_lines(row_text)
        if len(row_lines) < 2:
            continue

        # BWIN-Layout: erste zwei Zeilen sind Teamnamen
        home_team = row_lines[0]
        away_team = row_lines[1]
        if not any(ch.isalpha() for ch in home_team) or not any(ch.isalpha() for ch in away_team):
            # Fallback auf heuristische Team-Erkennung
            home_team, away_team = extract_teams_from_row_text(row_text)
        if not home_team or not away_team:
            continue

        odds_found = []
        for line in row_lines:
            odd = parse_decimal(line)
            if odd is not None:
                odds_found.append(odd)

        if len(odds_found) < 3:
            continue
        odds_1x2 = odds_found[:3]

        match_key = f"{home_team.lower()}::{away_team.lower()}"
        if match_key in seen_match_keys:
            continue
        seen_match_keys.add(match_key)

        date_text = ""
        for line in row_lines[2:8]:
            if parse_decimal(line) is not None:
                break
            if (":" in line or "/" in line or "." in line) and any(ch.isdigit() for ch in line):
                date_text = line
                break

        extracted.append(
            {
                "scraped_at_utc": now_utc_iso(),
                "match_date_raw": date_text,
                "home_team": home_team,
                "away_team": away_team,
                "odd_home_win_1": odds_1x2[0],
                "odd_draw_x": odds_1x2[1],
                "odd_away_win_2": odds_1x2[2],
                "market": "match_winner_1x2",
                "source": "bwin",
                "source_url": TARGET_URL,
            }
        )

    return extracted


def write_output(rows):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = now_local_stamp()
    out_file = os.path.join(OUTPUT_DIR, f"bwin_match_winner_odds_{stamp}.csv")
    df = pd.DataFrame(rows)
    df.to_csv(out_file, index=False, encoding="utf-8-sig")
    return out_file, len(df)


def main():
    driver = None
    try:
        driver = build_driver(PREFERRED_BROWSER)
        driver.get(TARGET_URL)
        click_cookie_banner_if_present(driver)
        try:
            WebDriverWait(driver, WAIT_TIMEOUT_SECONDS).until(
                lambda d: len(d.find_elements(By.TAG_NAME, "button")) > 15
            )
        except TimeoutException:
            pass

        time.sleep(PAGE_LOAD_WAIT_SECONDS)

        rows = extract_match_winner_rows(driver)
        if not rows:
            raise RuntimeError(
                "Keine 1X2-Quoten gefunden. "
                "Pruefe BWIN-Layout, Cookie-Banner oder WebDriver-Konfiguration."
            )

        out_file, count = write_output(rows)
        print(f"OK: {count} Spiele gespeichert in {out_file}")

    except WebDriverException as exc:
        raise RuntimeError(
            "WebDriver-Fehler. Falls Selenium Manager blockiert wird, "
            "setze BWIN_WEBDRIVER_PATH auf einen lokalen chromedriver/msedgedriver."
        ) from exc
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
