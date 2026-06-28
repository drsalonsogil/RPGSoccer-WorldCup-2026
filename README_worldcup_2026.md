# RPGsoccer World Cup 2026 simulator

This folder contains a modular automatic World Cup simulator based on the RPGsoccer idea.

## Files

- `rpgsoccer_core.py`: players, dice, ball, clock, score, formations and action criteria.
- `ai_random.py`: random choices for formations, attacks, defenders, receivers and penalties.
- `match_engine.py`: automatic match simulation and penalty shoot-outs.
- `worldcup_2026_data.py`: World Cup 2026 groups, group pairings and knockout slots.
- `tournament.py`: group tables, best thirds, round of 32, knockouts and output files.
- `run_worldcup_2026.py`: command-line entry point.

## Run

```bash
python run_worldcup_2026.py --seed 123 --output-dir worldcup_2026_simulation
```

Use `--quiet` if you only want the files and not the terminal play-by-play.

```bash
python run_worldcup_2026.py --seed 123 --quiet
```

## Output

The simulator writes one folder per group, for example:

```text
groupA/Mexico_South_Africa_game.txt
groupA/Mexico_South_Africa_result.txt
groupA/full_class.txt
```

It also writes:

```text
class_thirds.txt
round32_bracket.txt
round32/
round16/
quarterfinals/
semifinals/
third_place/
final/
worldcup_summary.txt
```

The default match length is 10 RPGsoccer minutes to keep a complete World Cup readable. Use `--minutes 90` if you want the original long clock.
