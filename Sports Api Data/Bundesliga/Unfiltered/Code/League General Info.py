import http.client
import json
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

def fetch_bundesliga():
    def remove_keys(obj, keys_to_remove):
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                if key in keys_to_remove:
                    del obj[key]
                else:
                    remove_keys(obj[key], keys_to_remove)
        elif isinstance(obj, list):
            for item in obj:
                remove_keys(item, keys_to_remove)

    # API-Verbindung
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")
    headers = {
        'x-rapidapi-host': "v3.football.api-sports.io",
        'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"
    }
    conn.request("GET", "/leagues", headers=headers)
    res = conn.getresponse()
    data = res.read()
    json_data = json.loads(data.decode("utf-8"))

    # Entferne logo und flag
    remove_keys(json_data, {"logo", "flag"})

    # Filter Bundesliga
    bundesliga_data = {
        "get": json_data.get("get"),
        "parameters": json_data.get("parameters"),
        "errors": json_data.get("errors"),
        "results": 0,
        "response": []
    }
    for item in json_data.get("response", []):
        if (item.get("league",{}).get("name") == "Bundesliga" and
            item.get("country",{}).get("name") == "Germany"):
            bundesliga_data["response"].append(item)
    bundesliga_data["results"] = len(bundesliga_data["response"])

    # Speichern
    output_file = "C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(bundesliga_data, f, ensure_ascii=False, indent=4)
    print(f"[{__name__}] Daten gespeichert: {output_file}")

if __name__ == "__main__":
    sched = BlockingScheduler(timezone="Europe/Berlin")
    # Cron: TAG=1, Stunde=0, Minute=0
    sched.add_job(fetch_bundesliga,
                  trigger=CronTrigger(day="1", hour="0", minute="0"))
    print("Scheduler gestartet – nächster Lauf am 1. des nächsten Monats um 00:00 Uhr")
    sched.start()
