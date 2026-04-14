# `patch_add_future_vs_reference_metrics.py`

Source: `Sports Api Data/Testruns/Code/patch_add_future_vs_reference_metrics.py`

## Ueberblick

Dieses Skript ist ein einmaliger oder wiederverwendbarer Text-Patcher fuer `AI_match_stats_prediction.py`. Es injiziert die Aenderungen, die fuer eine separate Future-vs-Reference-Evaluationshistorie noetig sind, direkt in den Quelltext und vermeidet doppelte Einfuegungen durch einfache Idempotenz-Pruefungen.

Die Datei gehoert damit nicht zur Vorhersage-Pipeline selbst, sondern zur Wartung des Codes im `Testruns`-Bereich. Der Fokus liegt darauf, eine klar umrissene Quelltextaenderung reproduzierbar und ohne manuelles Suchen/Einsetzen auszufuehren.

## Zweck / Responsibilities

- Oeffnet `Sports Api Data/Testruns/Code/AI_match_stats_prediction.py` ueber `pathlib.Path`.
- Prueft, ob der `datetime`-Import bereits vorhanden ist.
- Fuegt eine neue Konstante fuer `FUTURE_VS_REFERENCE_METRICS_PATH` ein, falls sie fehlt.
- Ergaenzt die Helper-Funktion `append_future_vs_reference_metrics(...)` vor `try_backfill_reference_from_future(...)`.
- Verdrahtet den neuen Funktionsaufruf nach dem Schreiben von `backfill_summary_df`.
- Schreibt die Datei nur neu, wenn sich der Text tatsaechlich geaendert hat.
- Bricht mit klaren `RuntimeError`-Meldungen ab, wenn erwartete Marker im Zielskript fehlen.

## Einsatzkontext

Das Skript ist nuetzlich, wenn die Aenderung an `AI_match_stats_prediction.py` nicht manuell im Editor vorgenommen werden soll oder wenn sie auf einem anderen Stand erneut angewendet werden muss. Es arbeitet rein textuell und setzt voraus, dass die Zielstruktur im Python-Skript noch zu den verwendeten Markern passt.

## Wichtige Konstanten / Konfiguration

- `FILE_PATH = Path(r"Sports Api Data/Testruns/Code/AI_match_stats_prediction.py")`
  - Definiert exakt die Datei, die gepatcht werden soll.
  - Ist relativ zum Repo-Root formuliert und funktioniert dadurch im Projektkontext stabil.

## Zentrale Funktionen

### `patch_text(text: str) -> str`

- Kernfunktion des Skripts.
- Erwartet den kompletten Quelltext der Zieldatei als String.
- Liefert den gepatchten Text zurueck.
- Arbeitet in vier Schritten:
  1. `datetime`-Import einfuegen.
  2. Konstante `FUTURE_VS_REFERENCE_METRICS_PATH` hinter `FUTURE_RUN_SUMMARY_SOURCE_PATH` einfuegen.
  3. Funktionsblock `append_future_vs_reference_metrics(...)` vor `try_backfill_reference_from_future(...)` einhaengen.
  4. Aufruf samt `print(...)`-Reporting nach dem Schreiben der Backfill-CSV einfuegen.

### `main() -> None`

- Liest den Originaltext aus `FILE_PATH`.
- Ruft `patch_text(...)` auf.
- Vergleicht Original und Patch-Ergebnis.
- Schreibt nur bei echtem Unterschied auf Platte.
- Gibt entweder `No changes needed.` oder `Patched: ...` aus.

## Patch-Strategie

Die Aenderung ist absichtlich markerbasiert statt AST-basiert umgesetzt. Das ist einfacher, aber auch fragiler:

- Vorteil:
  - leicht nachvollziehbar
  - keine Zusatzabhaengigkeiten
  - fuer kleine, exakt bekannte Quelltextmuster schnell genug
- Nachteil:
  - haengt stark an konkreten String-Mustern
  - bricht bei Refactorings im Zielskript schnell
  - erkennt semantisch aehnliche, aber anders formatierte Stellen nicht

## Welche Stellen geaendert werden

### 1. Importbereich

Gesucht wird:

```python
import random
import pandas as pd
```

Ersetzt wird durch:

```python
import random
from datetime import datetime
import pandas as pd
```

Die Einfuegung passiert nur, wenn `from datetime import datetime` noch nicht im Text vorkommt.

### 2. Konstantenblock

Gesucht wird die Zeile:

```python
FUTURE_RUN_SUMMARY_SOURCE_PATH = os.path.join(FUTURE_OUTPUT_PATH, 'prediction_weight_run_summary.csv')
```

Direkt dahinter wird die neue Konstante fuer `future_vs_reference_metrics.csv` eingefuegt.

### 3. Funktionsblock

Als Marker dient:

```python
def try_backfill_reference_from_future(ref_results):
```

Vor diesen Marker fuegt das Skript einen kompletten Raw-String-Funktionsblock fuer `append_future_vs_reference_metrics(...)` ein.

### 4. Backfill-Aufruf

Gesucht wird das Ankerpaar:

```python
backfill_pred_df.to_csv(PREDICTION_OUT_PATH, index=False)
backfill_summary_df.to_csv(RUN_SUMMARY_OUT_PATH, index=False)
```

Danach fuegt das Skript:

- den Funktionsaufruf fuer die neue Evaluationshistorie,
- eine Statusausgabe,
- sowie einen kurzen `head(10)`-Print relevanter Evaluationsspalten

ein.

## Inputs / Outputs / Side Effects

### Inputs

- Die vorhandene Datei `Sports Api Data/Testruns/Code/AI_match_stats_prediction.py`.
- Der komplette Textinhalt dieser Datei.

### Outputs

- Kein separates Artefakt.
- Die veraenderte Zieldatei selbst, falls der Patch angewendet werden konnte.

### Side Effects

- Ueberschreibt das Zielskript in-place.
- Veraendert keine weiteren Dateien.
- Gibt Statusmeldungen auf `stdout` aus.
- Kann Exceptions werfen, wenn erwartete Marker nicht mehr existieren.

## Interne Abhaengigkeiten / Imports

- `from __future__ import annotations`: macht Typannotationen unkritischer fuer Vorwaertsreferenzen.
- `pathlib.Path`: Dateizugriff und Pfaddefinition.

Es gibt absichtlich keine weiteren Bibliotheksabhaengigkeiten; die Datei bleibt damit sehr portabel.

## Wichtige Textmarker

Die Robustheit des Skripts haengt an diesen exakten String-Mustern:

- `from datetime import datetime`
- `FUTURE_VS_REFERENCE_METRICS_PATH`
- `FUTURE_RUN_SUMMARY_SOURCE_PATH = ...`
- `def try_backfill_reference_from_future(ref_results):`
- `backfill_pred_df.to_csv(PREDICTION_OUT_PATH, index=False)`
- `backfill_summary_df.to_csv(RUN_SUMMARY_OUT_PATH, index=False)`

Wenn einer dieser Marker im Zielskript verschoben, umbenannt oder reformatiert wurde, kann der Patch fehlschlagen.

## Fehlerfaelle / Edge Cases

- Wenn der Importblock nicht mehr exakt `import random` gefolgt von `import pandas as pd` enthaelt, wird der `datetime`-Import nicht eingefuegt.
- Wenn `FUTURE_RUN_SUMMARY_SOURCE_PATH` umbenannt wurde, scheitert die Konstanteninjektion mit `RuntimeError`.
- Wenn `try_backfill_reference_from_future(...)` nicht existiert, wird die Helper-Funktion nicht positioniert und das Skript bricht ab.
- Wenn der CSV-Schreibanker nicht gefunden wird, kann der neue Funktionsaufruf nicht eingefuegt werden.
- Eine Datei mit semantisch gleicher Logik, aber anderem Layout, wird nicht erkannt.
- Das Skript prueft nicht, ob der eingefuegte Funktionsblock syntaktisch oder fachlich zum restlichen Code passt; es setzt das voraus.

## Idempotenz

Das Skript ist auf einfache Wiederholbarkeit ausgelegt:

- Vor jedem Eingriff prueft es, ob die jeweilige Zielstruktur schon vorhanden ist.
- Falls alles bereits enthalten ist, bleibt der Text unveraendert.
- `main()` schreibt in diesem Fall nichts und meldet `No changes needed.`.

Diese Eigenschaft ist wichtig, wenn das Skript mehrfach in derselben Branch oder in automatisierten Ablaufen aufgerufen wird.

## Beispiel

```bash
python "Sports Api Data/Testruns/Code/patch_add_future_vs_reference_metrics.py"
```

Typischer Ablauf:

1. Das Skript liest `AI_match_stats_prediction.py`.
2. `patch_text(...)` baut den Zieltext.
3. Bei echten Aenderungen wird die Datei neu geschrieben.
4. Danach kann die geaenderte Pipeline direkt ausgefuehrt oder weiter versioniert werden.

## Beziehung zur Zieldatei

Die erzeugte Aenderung in `AI_match_stats_prediction.py` fuehrt fachlich zu drei neuen Faehigkeiten:

- Speichern einer eigenen `future_vs_reference_metrics.csv`.
- Berechnung von Delta-Metriken zwischen vorhergesagten und tatsaechlich evaluierten Run-Kennzahlen.
- Sichtbares Reporting der evaluierten Runs nach erfolgreichem Backfill.

Das Patch-Skript dokumentiert damit indirekt auch, welche minimalen Eingriffe noetig waren, um die bestehende Pipeline um eine Evaluationshistorie zu erweitern.

## Notes

- Die Datei ist eher ein Migrations- oder Hilfsskript als Teil des operativen Produktivcodes.
- Fuer groessere oder langfristig wiederkehrende Refactorings waere ein AST-basierter Ansatz belastbarer.
- Fuer den aktuellen, klar begrenzten Anwendungsfall ist die markerbasierte Strategie jedoch ausreichend schnell und einfach zu warten.
