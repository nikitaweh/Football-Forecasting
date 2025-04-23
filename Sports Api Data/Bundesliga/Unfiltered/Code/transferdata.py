import json
import os
import time
import http.client

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

# ---------------------------
# 1) Spieler‑IDs sammeln
# ---------------------------
with open(INPUT_JSON, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Angenommen dein JSON hat das Format:
# { ..., "players": [ { "player_id": 35845, ... }, ... ] }
player_ids = {
    str(p.get("player_id"))
    for p in data.get("players", [])
    if p.get("player_id") is not None
}

print(f"Gefundene {len(player_ids)} eindeutige Spieler‑IDs")

# ---------------------------
# 2) Transfer‑History abfragen
# ---------------------------
conn = http.client.HTTPSConnection(API_HOST)
all_transfers = {}

for pid in sorted(player_ids):
    print(f"Hole Transfers für Spieler {pid} …")
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
            # Die eigentliche Liste der Einträge unter "response"
            transfers_list = obj.get("response", [])
        except json.JSONDecodeError:
            print(f"→ Ungültiges JSON für Spieler {pid}")
            transfers_list = []

    # Jetzt alle logo-Felder entfernen
    for entry in transfers_list:
        # Jeder entry enthält eine Liste entry["transfers"]
        for move in entry.get("transfers", []):
            teams = move.get("teams", {})
            # in-team
            if "in" in teams and isinstance(teams["in"], dict):
                teams["in"].pop("logo", None)
            # out-team
            if "out" in teams and isinstance(teams["out"], dict):
                teams["out"].pop("logo", None)

        # Optional: falls es irgendwo direkt entry["team"] oder entry["league"] mit "logo" gäbe:
        if isinstance(entry.get("team"), dict):
            entry["team"].pop("logo", None)
        if isinstance(entry.get("league"), dict):
            entry["league"].pop("logo", None)

    all_transfers[pid] = transfers_list

conn.close()

# ---------------------------
# 3) Ergebnisse speichern
# ---------------------------
os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump({
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "transfers_by_player": all_transfers
    }, f, ensure_ascii=False, indent=2)

print(f"Transfer‑Historien gespeichert in:\n{OUTPUT_JSON}")
