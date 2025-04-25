import json
import os
import time
import http.client
from datetime import datetime, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Pfade anpassen
# ---------------------------
OUTPUT_FILE = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"

# ---------------------------
# API-Konfiguration
# ---------------------------
API_HOST   = "v3.football.api-sports.io"
API_KEY    = "5fa2372f2bfcbedb8ef7b85c86f0a27a"
HEADERS    = {
    'x-rapidapi-host': API_HOST,
    'x-rapidapi-key':  API_KEY
}

LEAGUE_ID = 78

def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def iso_date(dt: datetime):
    return dt.strftime("%Y-%m-%d")

def load_existing():
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        existing = data.get("response", [])
        last_run_str = data.get("last_run")
        if last_run_str:
            # parse ISO Zulu timestamp
            lr = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
        else:
            lr = None
        return existing, lr
    except FileNotFoundError:
        return [], None

def save_all(existing, last_run):
    out = {
        "last_run": last_run,
        "response": existing
    }
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=4)

def remove_keys(obj, keys_to_remove):
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            if k in keys_to_remove:
                del obj[k]
            else:
                remove_keys(obj[k], keys_to_remove)
    elif isinstance(obj, list):
        for item in obj:
            remove_keys(item, keys_to_remove)

def fetch_new_fixtures():
    # 1) Bestehende Daten und letzten Lauf laden
    existing, last_run = load_existing()
    existing_ids = {fix["fixture"]["id"] for fix in existing if "fixture" in fix and "id" in fix["fixture"]}

    now = datetime.now(timezone.utc)
    # Wenn nie gelaufen, hole alle Fixtures seit 2017-01-01
    if last_run is None:
        from_date = "2017-01-01"
    else:
        # nur Tag teilen, damit auch spätere Uhrzeiten erfasst werden
        from_date = iso_date(last_run)
    to_date = iso_date(now)

    print(f"[{now.isoformat()}] Letzter Lauf: {last_run}, hole neue Fixtures von {from_date} bis {to_date}")

    # 2) API-Call mit Datumsfilter
    conn = http.client.HTTPSConnection(API_HOST)
    endpoint = f"/fixtures?league={LEAGUE_ID}&from={from_date}&to={to_date}"
    conn.request("GET", endpoint, headers=HEADERS)
    res = conn.getresponse()
    raw = res.read().decode("utf-8")
    conn.close()

    try:
        body = json.loads(raw)
        fixtures = body.get("response", [])
    except json.JSONDecodeError:
        print(f"Ungültiges JSON erhalten, Abbruch.")
        return

    # 3) Filtere nur die wirklich neuen Fixtures
    new = []
    for fixture in fixtures:
        fid = fixture.get("fixture", {}).get("id")
        if fid is not None and fid not in existing_ids:
            remove_keys(fixture, {"logo", "flag"})
            new.append(fixture)
            existing_ids.add(fid)

    if new:
        print(f"[{datetime.now().isoformat()}] {len(new)} neue Fixtures gefunden.")
        existing.extend(new)
    else:
        print(f"[{datetime.now().isoformat()}] Keine neuen Fixtures seit {from_date}.")

    # 4) Speichern und letzten Lauf aktualisieren
    save_all(existing, iso_now())
    print(f"[{datetime.now().isoformat()}] Datei aktualisiert: {OUTPUT_FILE}")

if __name__ == "__main__":
    sched = BlockingScheduler(timezone="Europe/Berlin")
    # CronTrigger: Samstag, Sonntag und Montag um 00:00 Uhr
    sched.add_job(
        fetch_new_fixtures,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="0", minute="0")
    )
    print(f"[{datetime.now().isoformat()}] Scheduler gestartet – läuft samstags, sonntags & montags um 00:00 Uhr (Europe/Berlin)")
    sched.start()
