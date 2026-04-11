# `Player Gerneral Information.py`

Source: `Sports Api Data/Player Profiles/Unfiltered/Code/Player Gerneral Information.py`

## Überblick

Dieses Skript verarbeitet Spieler- oder Profilinformationen und bereitet sie fuer die weitere Nutzung auf.

## Zweck / Responsibilities

- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Kommuniziert mit externen APIs und verarbeitet deren Antworten weiter.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `get_with_retry(url, params, headers)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `fetch_player_profiles()`: Ruft Quelldaten ab und verarbeitet die Antwort fuer die weitere Nutzung.

## Inputs / Outputs & Side-effects

**Inputs**
- Keine klar benannten Eingabepfade erkannt; Details stehen im Quelltext.

**Outputs**
- `OUTPUT_JSON`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/players_profiles"`

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Fuehrt Netzwerkzugriffe auf externe APIs aus.
- Kann als lang laufender Scheduler-Prozess gestartet werden.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- `API_KEY`: `"5fa2372f2bfcbedb8ef7b85c86f0a27a"`
- `RETRY_LIMIT`: `3`
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `apscheduler.schedulers.blocking.BlockingScheduler`
- `apscheduler.triggers.cron.CronTrigger`
- `json`
- `os`
- `requests`
- `requests.exceptions.ConnectionError`
- `requests.exceptions.HTTPError`
- `requests.exceptions.RequestException`
- `time`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Player Profiles/Unfiltered/Code/Player Gerneral Information.py"``

## Edge Cases / Notes

- Netzwerkfehler, Timeouts oder API-Limits koennen den Lauf unterbrechen oder zu leeren Ergebnissen fuehren.
- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

