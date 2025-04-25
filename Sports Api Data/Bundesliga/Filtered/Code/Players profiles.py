import json
import csv
import os
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Pfade anpassen
# ---------------------------
BASE_DIR        = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection"
PROFILES_FILE   = os.path.join(BASE_DIR, "players_profiles_78.json")
SEASONS_FILE    = os.path.join(BASE_DIR, "players_activity_78.json")
TRANSFERS_FILE  = os.path.join(BASE_DIR, "transferhistory_78.json")
OUTPUT_CSV_FILE = os.path.join(r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection","player_information_78.csv")

# ---------------------------
# Funktion zur Erstellung der CSV
# ---------------------------
def convert_player_information_csv():
    # 1) JSONs laden
    try:
        with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
            profiles_data = json.load(f)
        with open(SEASONS_FILE, 'r', encoding='utf-8') as f:
            seasons_data = json.load(f)
        with open(TRANSFERS_FILE, 'r', encoding='utf-8') as f:
            transfers_data = json.load(f)
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Laden der JSON-Dateien: {e}")
        return

    # 1.1) Bestimme aktuelle Saison aus player activity
    global_years = []
    for years in seasons_data.get('players_seasons', {}).values():
        if isinstance(years, list):
            for y in years:
                if isinstance(y, int):
                    global_years.append(y)
    global_latest_season = max(global_years) if global_years else None

    # 2) Zusammenfassung pro Spieler
    rows = []
    for p in profiles_data.get('players', []):
        pid = str(p.get('player_id'))
        firstname   = p.get('firstname', '')
        lastname    = p.get('lastname', '')
        birth_date  = p.get('birth_date', '')
        nationality = p.get('nationality', '')
        height      = p.get('height', '')
        weight      = p.get('weight', '')

        seasons_list = seasons_data.get('players_seasons', {}).get(pid, [])
        active = False
        if global_latest_season and isinstance(seasons_list, list):
            active = global_latest_season in seasons_list

        transfers_list = transfers_data.get('transfers_by_player', {}).get(pid, [])
        club_history = []
        last_update  = ''
        current_club = ''
        last_transfer_date = ''
        last_transfer_type = ''
        last_transfer_from = ''
        last_transfer_to   = ''

        if transfers_list:
            entry = transfers_list[0]
            last_update = entry.get('update', '')
            moves = entry.get('transfers', [])
            try:
                sorted_moves = sorted(moves, key=lambda m: datetime.fromisoformat(m.get('date', '')))
            except Exception:
                sorted_moves = moves
            for m in sorted_moves:
                tin = m.get('teams', {}).get('in', {}).get('name')
                if tin and tin not in club_history:
                    club_history.append(tin)
            if club_history:
                current_club = club_history[-1]
            last = sorted_moves[-1]
            last_transfer_date = last.get('date', '')
            last_transfer_type = last.get('type', '')
            last_transfer_from = last.get('teams', {}).get('out', {}).get('name', '')
            last_transfer_to   = last.get('teams', {}).get('in', {}).get('name', '')

        rows.append({
            'player_id': pid,
            'firstname': firstname,
            'lastname': lastname,
            'birth_date': birth_date,
            'nationality': nationality,
            'height': height,
            'weight': weight,
            'active': active,
            'current_club': current_club,
            'club_history': ';'.join(club_history),
            'last_update': last_update,
            'last_transfer_date': last_transfer_date,
            'last_transfer_type': last_transfer_type,
            'last_transfer_from': last_transfer_from,
            'last_transfer_to': last_transfer_to
        })

    # 3) CSV schreiben
    fieldnames = [
        'player_id','firstname','lastname','birth_date','nationality',
        'height','weight','active','current_club','club_history',
        'last_update','last_transfer_date','last_transfer_type',
        'last_transfer_from','last_transfer_to'
    ]

    os.makedirs(os.path.dirname(OUTPUT_CSV_FILE), exist_ok=True)
    try:
        with open(OUTPUT_CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] CSV-Datei wurde erstellt: {OUTPUT_CSV_FILE}")
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Schreiben der CSV: {e}")

if __name__ == "__main__":
    sched = BlockingScheduler(timezone="Europe/Berlin")
    # CronTrigger: 1. des Monats um 03:00 Uhr
    sched.add_job(
        convert_player_information_csv,
        trigger=CronTrigger(day="1", hour="3", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – läuft am ersten jeden Monats um 03:00 Uhr (Europe/Berlin)")
    sched.start()
