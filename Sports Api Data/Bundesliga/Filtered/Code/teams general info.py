import json
import csv

# Dateipfade
input_file_path = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga Teams.json"
output_file_path = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Teams_78.csv"

# Lade die JSON-Daten
with open(input_file_path, "r", encoding="utf-8") as infile:
    data = json.load(infile)

# Die relevanten Einträge stehen im Schlüssel "response"
teams = data.get("response", [])

# Definiere die gewünschten Spalten
fieldnames = ["Team Name", "Team ID", "Stadion ID", "Capacity"]

with open(output_file_path, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    for entry in teams:
        team_info = entry.get("team", {})
        venue_info = entry.get("venue", {})
        
        row = {
            "Team Name": team_info.get("name", ""),
            "Team ID": team_info.get("id", ""),
            "Stadion ID": venue_info.get("id", ""),
            "Capacity": venue_info.get("capacity", ""),
        }
        writer.writerow(row)

print(f"CSV-Datei wurde in '{output_file_path}' gespeichert.")
