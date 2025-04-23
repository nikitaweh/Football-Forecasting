import json
import csv
import os

# Pfade anpassen
input_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/player_statistics_per_fixture_league_78.json"
output_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/player_statistics_per_fixture_league_78.csv"

# Mapping zur Anpassung der Teamnamen
team_name_overrides = {
    "Bayern Munich":              "Bayern München",
    "Hertha Berlin":              "Hertha BSC",
    "Borussia Monchengladbach":   "Borussia Mönchengladbach",
    "FC Nurnberg":                "1. FC Nürnberg",
    "Fortuna Dusseldorf":         "Fortuna Düsseldorf",
    "FC Heidenheim":              "1. FC Heidenheim",
    "Vfl Bochum":                 "VfL Bochum",
    "SpVgg Greuther Furth":       "SpVgg Greuther Fürth"
}

# JSON-Datei laden
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

rows = []
# Äußere Response-Liste
outer_list = data.get('response', [])
if not isinstance(outer_list, list):
    raise ValueError("Erwartet data['response'] als Liste")

for outer in outer_list:
    # Fixture ID
    fixture_id = outer.get('parameters', {}).get('fixture') or outer.get('fixture_id')
    # Innere Spieler-Liste
    responses = outer.get('response', [])
    if not isinstance(responses, list):
        continue
    for entry in responses:
        team = entry.get('team', {})
        players = entry.get('players', [])
        team_id = team.get('id')
        team_name = team.get('name')
        # Durch jede Spieler-Statistik
        for p in players:
            player = p.get('player', {})
            stats_list = p.get('statistics', [])
            # Nimm ersten Statistik-Eintrag
            stats = stats_list[0] if stats_list else {}
            games = stats.get('games', {})
            # Messwerte
            minutes = games.get('minutes')
            rating = games.get('rating')
            captain = games.get('captain')
            substitute = games.get('substitute')
            # Offsides
            offsides = stats.get('offsides')
            # Shots
            shots = stats.get('shots', {})
            total_shots = shots.get('total')
            on_target = shots.get('on')
            # Goals
            goals = stats.get('goals', {})
            total_goals = goals.get('total')
            conceded = goals.get('conceded')
            assists = goals.get('assists')
            saves = goals.get('saves')
            # Penalties
            penalty = stats.get('penalty', {})
            pen_scored = penalty.get('scored')
            pen_missed = penalty.get('missed')
            pen_saved = penalty.get('saved')
            # Passes
            passes = stats.get('passes', {})
            pass_total = passes.get('total')
            pass_accuracy = passes.get('accuracy')
            # Tackles
            tackles = stats.get('tackles', {})
            tackle_total = tackles.get('total')
            blocks = tackles.get('blocks')
            interceptions = tackles.get('interceptions')
            # Duels
            duels = stats.get('duels', {})
            duel_total = duels.get('total')
            duel_won = duels.get('won')
            # Dribbles
            dribbles = stats.get('dribbles', {})
            dribble_total = dribbles.get('attempts')
            dribble_success = dribbles.get('success')
            # Fouls
            fouls = stats.get('fouls', {})
            fouls_drawn = fouls.get('drawn')
            fouls_committed = fouls.get('committed')
            # Cards
            cards = stats.get('cards', {})
            yellow = cards.get('yellow')
            red = cards.get('red')
            # Distance traveled if exists
            distance = stats.get('distance')

            rows.append({
                'Fixture ID': fixture_id,
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
        fieldnames = [
            'Fixture ID','Team ID','Team Name','Player ID','Player Name',
            'Minutes Played','Goals Conceded','Saves','Penalties Saved',
            'Total Goals','Assists','Total Shots','Shots on Target',
            'Penalties Scored','Penalties Missed','Passes','Pass Accuracy',
            'Tackles','Blocks','Interceptions','Duels','Duels Won',
            'Dribbles','Successful Dribbles','Fouls Committed','Fouls Suffered',
            'Yellow Cards','Red Cards','Offsides','Distance Traveled',
            'Rating','Substitute','Captain'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV-Datei wurde erstellt: {output_file}")
else:
    print("Keine Daten extrahiert.")
