# `test_player_workload_features.py`

Source: `Sports Api Data/Testruns/Code/test_player_workload_features.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Berechnet zeitlich vorgelagerte Spielerbelastung aus Bundesliga- und kompetitiven internationalen Spielminuten.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `class PlayerWorkloadFeatureTests(unittest.TestCase)`
  Verwendet `pd.DataFrame`, `build_player_workload_index`, `player_workload_at`, `self.assertGreater`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `fixtures.to_csv(fixtures_path, index=False)`
- `lineups.to_csv(lineups_path, index=False)`

### Konfiguration und Environment

- `SCRIPT_DIR = Path(__file__).resolve().parent`

### Imports und interne Abhaengigkeiten

- `import sys`
- `import tempfile`
- `import unittest`
- `from pathlib import Path`
- `import pandas as pd`
- `from player_workload_features import build_player_workload_index, player_workload_at`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Testruns/Code/test_player_workload_features.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Keine expliziten `except`-Handler im Modul; Fehler koennen an den Aufrufer weitergegeben werden.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.

### Ergaenzende Implementierungshinweise

Quellcode-Kommentare zu einzelnen Verarbeitungsschritten:


Im Code explizit gepruefte Bedingungen (keine Zusicherung vollstaendiger Validierung):

- `str(SCRIPT_DIR) not in sys.path`
- `__name__ == '__main__'`

### Nachvollziehbarer Implementierungsausschnitt

Die folgende Auswahl zeigt zentrale Berechnungen bzw. die Ausfuehrungsfolge direkt aus der Quelldatei.
Sie dient als Lesebeispiel und ist ohne Modulkontext nicht eigenstaendig ausfuehrbar.

```python
# PlayerWorkloadFeatureTests
class PlayerWorkloadFeatureTests(unittest.TestCase):
    def test_target_match_minutes_are_excluded(self):
        domestic = pd.DataFrame([
            {'MatchID': 1, 'PlayerID': 10, 'MatchDate': '2026-01-01', 'MinutesPlayed': 90},
            {'MatchID': 2, 'PlayerID': 10, 'MatchDate': '2026-01-10', 'MinutesPlayed': 90},
        ])
        index, _ = build_player_workload_index(domestic, None, None, None)
        workload, minutes_14, minutes_30 = player_workload_at(index, 10, '2026-01-10')
        self.assertGreater(workload, 0.0)
        self.assertEqual(minutes_14, 90.0)
        self.assertEqual(minutes_30, 90.0)

    def test_only_competitive_starters_enter_international_proxy(self):
        domestic = pd.DataFrame(columns=['MatchID', 'PlayerID', 'MatchDate', 'MinutesPlayed'])
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            fixtures_path = temp / 'fixtures.csv'
            lineups_path = temp / 'lineups.csv'
            fixtures = pd.DataFrame([
                {'MatchID': 100, 'Date': '2026-03-01', 'League Name': 'World Cup'},
                {'MatchID': 101, 'Date': '2026-03-02', 'League Name': 'Friendlies'},
            ])
            lineups = pd.DataFrame([
                {'MatchID': 100, 'Player ID': 20, 'StartXI': True},
                {'MatchID': 100, 'Player ID': 21, 'StartXI': False},
                {'MatchID': 101, 'Player ID': 22, 'StartXI': True},
            ])
            fixtures.to_csv(fixtures_path, index=False)
            lineups.to_csv(lineups_path, index=False)

            index, metadata = build_player_workload_index(
                domestic,
                fixtures_path,
                lineups_path,
                temp / 'missing_player_stats.csv',
            )

        self.assertIn(20, index)
        self.assertNotIn(21, index)
        self.assertNotIn(22, index)
        self.assertEqual(metadata['international_proxy_events'], 1)

```
