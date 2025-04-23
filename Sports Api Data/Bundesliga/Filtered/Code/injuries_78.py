import json
import csv
import os

# ---------------------------
# Pfade anpassen
# ---------------------------
INPUT_JSON  = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/injuries_league_78.json"
OUTPUT_CSV  = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/injuries_league_78.csv"

# ---------------------------
# Teamnamen-Overrides
# ---------------------------
team_name_overrides = {
    "Bayern Munich": "Bayern München",
    "Hertha Berlin": "Hertha BSC",
    "Borussia Monchengladbach": "Borussia Mönchengladbach",
    "FC Nurnberg": "1. FC Nürnberg",
    "Fortuna Dusseldorf": "Fortuna Düsseldorf",
    "FC Heidenheim": "1. FC Heidenheim",
    "Vfl Bochum": "VfL Bochum",
    "SpVgg Greuther Furth": "SpVgg Greuther Fürth"
}

# ---------------------------
# 1) JSON einlesen
# ---------------------------
with open(INPUT_JSON, 'r', encoding='utf-8') as f:
    data = json.load(f)

injuries_by_fixture = data.get('injuries_by_fixture', {})

# ---------------------------
# 2) CSV schreiben (ohne leere Fixtures)
# ---------------------------
os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

fieldnames = [
    'fixture_id',
    'player_id',
    'player_name',
    'team_id',
    'team_name',
    'league_id',
    'league_name',
    'injury_type',
    'injury_detail',
    'injury_time'
]

with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    for fid, entries in injuries_by_fixture.items():
        if not entries:
            continue  # überspringe leere Fixtures
        for inj in entries:
            team_name = inj.get('team', {}).get('name') or ''
            # Override anwenden
            team_name = team_name_overrides.get(team_name, team_name)
            row = {
                'fixture_id': fid,
                'player_id': inj.get('player', {}).get('id'),
                'player_name': inj.get('player', {}).get('name'),
                'team_id': inj.get('team', {}).get('id'),
                'team_name': team_name,
                'league_id': inj.get('league', {}).get('id'),
                'league_name': inj.get('league', {}).get('name'),
                'injury_type': inj.get('injury', {}).get('type'),
                'injury_detail': inj.get('injury', {}).get('detail'),
                'injury_time': inj.get('injury', {}).get('time')
            }
            writer.writerow(row)

print(f"Injuries-CSV erstellt: {OUTPUT_CSV}")