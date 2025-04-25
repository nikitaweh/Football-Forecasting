import json
import os
import time
import http.client
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Konfiguration
# ---------------------------
INPUT_JSON  = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/players_profiles_78.json"
OUTPUT_JSON = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/transferhistory_78.json"

API_HOST    = "v3.football.api-sports.io"
API_KEY     = "5fa2372f2bfcbedb8ef7b85c86f0a27a"
HEADERS     = {
    'x-rapidapi-host': API_HOST,
    'x-rapidapi-key':  API_KEY
}

def fetch_transfer_history():
    # 1) Spieler-IDs sammeln
    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    player_ids = {
        str(p.get("player_id"))
        for p in data.get("players", [])
        if p.get("player_id") is not None
    }
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Gefundene {len(player_ids)} eindeutige Spieler-IDs")

    # 2) Transfer-History abfragen
    conn = http.client.HTTPSConnection(API_HOST)
    all_transfers = {}

    for pid in sorted(player_ids):
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Hole Transfers für Spieler {pid} …")
        path = f"/transfers?player={pid}"
        conn.request("GET", path, headers=HEADERS)
        res = conn.getresponse()
        raw = res.read().decode('utf-8')

        if res.status != 200:
            print(f"→ Fehler {res.status} für Spieler {pid}")
            transfers_list = []
        else:
            try:
                obj = json.loads(raw)
                transfers_list = obj.get("response", [])
            except json.JSONDecodeError:
                print(f"→ Ungültiges JSON für Spieler {pid}")
                transfers_list = []

        # logo-Felder entfernen
        for entry in transfers_list:
            for move in entry.get("transfers", []):
                teams = move.get("teams", {})
                if isinstance(teams.get("in"), dict):
                    teams["in"].pop("logo", None)
                if isinstance(teams.get("out"), dict):
                    teams["out"].pop("logo", None)
            if isinstance(entry.get("team"), dict):
                entry["team"].pop("logo", None)
            if isinstance(entry.get("league"), dict):
                entry["league"].pop("logo", None)

        all_transfers[pid] = transfers_list

    conn.close()

    # 3) Ergebnisse speichern
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": generated_at,
            "transfers_by_player": all_transfers
        }, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Transfer-Historien gespeichert in: {OUTPUT_JSON}")


if __name__ == "__main__":
    # Scheduler initialisieren
    sched = BlockingScheduler(timezone="Europe/Berlin")
    # CronTrigger: am 1. jedes Monats um 01:00 Uhr
    sched.add_job(
        fetch_transfer_history,
        trigger=CronTrigger(day="1", hour="1", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – nächster Lauf am 1. des Monats um 01:00 Uhr (Europe/Berlin)")
    sched.start()
