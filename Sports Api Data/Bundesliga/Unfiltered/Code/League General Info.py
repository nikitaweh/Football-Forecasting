import http.client
import json

def remove_keys(obj, keys_to_remove):
    """
    Entfernt rekursiv alle Schlüssel, die in keys_to_remove enthalten sind, 
    aus Dictionaries und Listen.
    """
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key in keys_to_remove:
                del obj[key]
            else:
                remove_keys(obj[key], keys_to_remove)
    elif isinstance(obj, list):
        for item in obj:
            remove_keys(item, keys_to_remove)

# Aufbau der HTTPS-Verbindung zur API
conn = http.client.HTTPSConnection("v3.football.api-sports.io")

headers = {
    'x-rapidapi-host': "v3.football.api-sports.io",
    'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"
}

# Sende den GET-Request an den /leagues-Endpunkt
conn.request("GET", "/leagues", headers=headers)
res = conn.getresponse()
data = res.read()

# Umwandeln der empfangenen Daten in ein Python-Dictionary
json_data = json.loads(data.decode("utf-8"))

# Entferne rekursiv die Schlüssel "logo" und "flag"
remove_keys(json_data, {"logo", "flag"})

# Filtere nur die Ligainformationen zur deutschen 1. Bundesliga
bundesliga_data = {
    "get": json_data.get("get"),
    "parameters": json_data.get("parameters"),
    "errors": json_data.get("errors"),
    "results": 0,
    "response": []
}

for item in json_data.get("response", []):
    league_name = item.get("league", {}).get("name")
    country_name = item.get("country", {}).get("name")
    if league_name == "Bundesliga" and country_name == "Germany":
        bundesliga_data["response"].append(item)

bundesliga_data["results"] = len(bundesliga_data["response"])

# Ausgabe-Dateipfad anpassen
output_file_path = "C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga.json"

# Speichern der gefilterten Daten in der JSON-Datei
with open(output_file_path, "w", encoding="utf-8") as f:
    json.dump(bundesliga_data, f, ensure_ascii=False, indent=4)

print(f"Die Ergebnisse zur deutschen 1. Bundesliga wurden in '{output_file_path}' gespeichert.")
