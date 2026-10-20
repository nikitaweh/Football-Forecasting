import json
import csv
import os
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from pathlib import Path

# Repo root: KI_PROJECT_ROOT if set (VPS), else derived from this file's location.
PROJECT_ROOT = Path(os.environ.get("KI_PROJECT_ROOT") or Path(__file__).resolve().parents[5]).as_posix()


# ----------------------------
# Pfade anpassen
# ----------------------------
input_file = rf"{PROJECT_ROOT}/Sports Api Data/International/UEFA/Unfiltered/Datacollection/player_statistics_per_fixture_international.json"
output_file = rf"{PROJECT_ROOT}/Sports Api Data/International/UEFA/Filtered/Datacollection/player_statistics_per_fixture_international.csv"

# ----------------------------
# Funktion: JSON zu CSV konvertieren
# ----------------------------
def convert_player_statistics_to_csv():
    # JSON-Datei laden
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Laden der JSON: {e}")
        return

    rows = []
    outer_list = data.get('response', [])
    if not isinstance(outer_list, list):
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Unerwartetes Format: 'response' ist keine Liste.")
        return

    for outer in outer_list:
        MatchID = outer.get('parameters', {}).get('fixture') or outer.get('fixture_id')
        responses = outer.get('response', [])
        if not isinstance(responses, list):
            continue

        for entry in responses:
            team = entry.get('team', {})
            players = entry.get('players', [])
            team_id = team.get('id')
            team_name = team.get('name', '')

            for p in players:
                player = p.get('player', {})
                stats_list = p.get('statistics', [])
                stats = stats_list[0] if stats_list else {}

                games = stats.get('games', {})
                minutes = games.get('minutes')
                rating = games.get('rating')
                captain = games.get('captain')
                substitute = games.get('substitute')
                offsides = stats.get('offsides')

                shots = stats.get('shots', {})
                total_shots = shots.get('total')
                on_target = shots.get('on')

                goals = stats.get('goals', {})
                total_goals = goals.get('total')
                conceded = goals.get('conceded')
                assists = goals.get('assists')
                saves = stats.get('saves', 0) if isinstance(stats.get('saves', 0), int) else goals.get('saves')

                penalty = stats.get('penalty', {})
                pen_scored = penalty.get('scored')
                pen_missed = penalty.get('missed')
                pen_saved = penalty.get('saved')

                passes = stats.get('passes', {})
                pass_total = passes.get('total')
                pass_accuracy = passes.get('accuracy')

                tackles = stats.get('tackles', {})
                tackle_total = tackles.get('total')
                blocks = tackles.get('blocks')
                interceptions = tackles.get('interceptions')

                duels = stats.get('duels', {})
                duel_total = duels.get('total')
                duel_won = duels.get('won')

                dribbles = stats.get('dribbles', {})
                dribble_total = dribbles.get('attempts')
                dribble_success = dribbles.get('success')

                fouls = stats.get('fouls', {})
                fouls_drawn = fouls.get('drawn')
                fouls_committed = fouls.get('committed')

                cards = stats.get('cards', {})
                yellow = cards.get('yellow')
                red = cards.get('red')

                distance = stats.get('distance')

                rows.append({
                    'MatchID': MatchID,
                    'Team ID': team_id,
                    'Team Name': team_name,
                    'Player ID': player.get('id'),
                    'Player Name': player.get('name'),
                    'Minutes Played': minutes,
                    'Goals Conceded': conceded,
                    'Saves': saves,
                    'Penalties Saved': pen_saved,
                    'Total Goals': total_goals,
                    'Assists': assists,
                    'Total Shots': total_shots,
                    'Shots on Target': on_target,
                    'Penalties Scored': pen_scored,
                    'Penalties Missed': pen_missed,
                    'Passes': pass_total,
                    'Pass Accuracy': pass_accuracy,
                    'Tackles': tackle_total,
                    'Blocks': blocks,
                    'Interceptions': interceptions,
                    'Duels': duel_total,
                    'Duels Won': duel_won,
                    'Dribbles': dribble_total,
                    'Successful Dribbles': dribble_success,
                    'Fouls Committed': fouls_committed,
                    'Fouls Suffered': fouls_drawn,
                    'Yellow Cards': yellow,
                    'Red Cards': red,
                    'Offsides': offsides,
                    'Distance Traveled': distance,
                    'Rating': rating,
                    'Substitute': substitute,
                    'Captain': captain
                })

    # Schreibe CSV
    if rows:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] CSV-Datei wurde erstellt: {output_file}")
    else:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Keine Daten extrahiert.")

if __name__ == "__main__":

    convert_player_statistics_to_csv()

    sched = BlockingScheduler(timezone="Europe/Berlin")
    # CronTrigger: Dienstag, Mittwoch, Donnerstag um 03:00 Uhr
    sched.add_job(
        convert_player_statistics_to_csv,
        trigger=CronTrigger(day_of_week="tue,wed,thu", hour="3", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – läuft dienstags, mittwochs & donnerstags um 03:00 Uhr (Europe/Berlin)")
    sched.start()
