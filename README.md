# RPGSoccer-WorldCup-2026

RPGSoccer World Cup 2026 is a Python GUI game that simulates a World Cup-style football tournament with RPG-inspired mechanics, team statistics, match history, tournament progression, and a “Guess the Winner” prediction mode.

The game includes a complete World Cup 2026 tournament structure, automatic and interactive match simulation, save/load support, history tracking, player predictions, and graphical assets such as flags, dice images, trophy images, and sound effects.

---

## Main Features

* Full World Cup 2026-style tournament simulation.
* Python GUI built with PySide6.
* Tournament mode with user-controlled team selection.
* Interactive RPG-style match interface for games involving the selected team.
* Automatic simulation for the remaining matches.
* “Guess the Winner” mode for 1 to 48 players.
* Podium prediction system: winner, runner-up, and third place.
* Points system for predictions depending on how far each chosen team progresses.
* Save and load system for tournament progress.
* Game history browser.
* Group standings, best third-place teams, knockout rounds, podium, and match results.
* Dice-based RPG mechanics for attacks, defenses, shots, fouls, and match events.
* Included graphical assets and sound effects.
* Random seeds are generated internally and hidden from the GUI.

---

## Repository Structure

```text
RPGSoccer-WorldCup-2026/
│
├── run.py                         # Main GUI entry point
├── run_gui.bat                    # Windows launcher
├── requirements.txt               # Python dependencies
├── setup_windows_venv.ps1         # Optional Windows virtual environment setup
│
├── app_gui.py                     # Main GUI application
├── interactive_match.py           # Interactive RPG-style match GUI
├── tournament.py                  # World Cup tournament logic
├── match_engine.py                # Automatic match simulation
├── rpgsoccer_core.py              # Core RPGSoccer mechanics
├── ai_random.py                   # Random AI decisions
├── worldcup_2026_data.py          # World Cup 2026 teams, groups, and pairings
├── team_assets.py                 # Team asset handling
├── history_store.py               # Game history storage
├── download_flags.py              # Optional flag download/update helper
│
├── assets/                        # Images, flags, dice, trophy, audio
├── saved_games/                   # Saved tournaments and history files
└── worldcup_2026_runs/            # Generated tournament output folders
```

---

## Requirements

The program requires Python and the PySide6 GUI library.

Recommended:

* Python 3.10 or newer
* Windows, macOS, or Linux
* A desktop environment capable of opening a Qt/PySide6 GUI window

The project was developed and tested using a local Python virtual environment.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/drsalonsogil/RPGSoccer-WorldCup-2026.git
cd RPGSoccer-WorldCup-2026
```

---

## Installation on Windows

### Option A: Automatic launcher

On Windows, you can run:

```bat
run_gui.bat
```

This script creates a virtual environment if needed, installs the required packages, prepares the assets, and launches the game.

---

### Option B: Manual installation with PowerShell

From the project folder:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python download_flags.py
python run.py
```

If you do not have Python 3.14 installed, use another installed Python version, for example:

```powershell
py -3.12 -m venv .venv
```

or:

```powershell
python -m venv .venv
```

---

## Installation on macOS / Linux

From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python download_flags.py
python run.py
```

---

## Running the Game

After installation, activate the virtual environment and run:

```bash
python run.py
```

On Windows, you can also double-click or execute:

```bat
run_gui.bat
```

---

## Game Modes

### Tournament Mode

Tournament mode starts a complete World Cup tournament.

The user chooses:

1. Player name.
2. Difficulty.
3. Team to control.

Matches involving the selected team are played through the interactive RPGSoccer match interface. Other matches are simulated automatically.

The tournament window includes:

* Live games.
* Group standings.
* Best third-place classification.
* Knockout rounds.
* Podium.
* Save and load controls.
* Match history.

---

### Guess the Winner Mode

Guess the Winner is a prediction game for 1 to 48 players.

Each player chooses:

1. Predicted World Cup winner.
2. Predicted runner-up.
3. Predicted third-place team.

The same team cannot be repeated in the same podium position across players. For example, if one player chooses a team as champion, that team is no longer available as champion for the other players.

Each player must select three different teams.

The prediction scoring system is:

```text
Exact podium position: 25 points
Champion reaches winner position but not exact prediction: 20 points
Team finishes 2nd: 15 points
Team finishes 3rd: 10 points
Team finishes 4th: 5 points
Team reaches quarterfinals: 3 points
Team reaches round of 16: 2 points
Team reaches round of 32: 1 point
```

---

### Interactive Match Mode

Interactive matches use RPG-style decisions and dice mechanics.

The player can make tactical decisions during the game, including:

* Passing.
* Attacking.
* Defending.
* Shooting.
* Choosing formations.
* Reacting to match situations.

The interface includes:

* Score panel.
* Current game status.
* Choice buttons.
* Dice panel.
* CPU dice value.
* Consequence pop-ups.
* Goal pop-up with audio.

---

## Saving and Loading

Saved games are stored in:

```text
saved_games/
```

The GUI allows tournaments to be saved and loaded during play.

Generated tournament logs and output files are stored in:

```text
worldcup_2026_runs/
```

These folders may grow over time as you play more tournaments.

---

## Command-Line World Cup Simulation

The project also includes a command-line simulator.

Run:

```bash
python run_worldcup_2026.py --seed 123 --output-dir worldcup_2026_simulation
```

Use quiet mode to generate only the output files without the full terminal play-by-play:

```bash
python run_worldcup_2026.py --seed 123 --quiet
```

Use a longer match clock with:

```bash
python run_worldcup_2026.py --seed 123 --minutes 90
```

By default, matches use a shorter RPGSoccer time format to keep a full World Cup simulation readable.

---

## Generated Output Files

A tournament run may generate folders and files such as:

```text
groupA/
groupB/
groupC/
...
round32/
round16/
quarterfinals/
semifinals/
third_place/
final/
class_thirds.txt
round32_bracket.txt
worldcup_summary.txt
```

Each match can generate files such as:

```text
Mexico_South_Africa_game.txt
Mexico_South_Africa_result.txt
full_class.txt
```

These files contain the match play-by-play, result summaries, group classifications, knockout results, and final tournament summary.

---

## Updating or Downloading Flags

The project already includes flag assets in the `assets/flags/` folder.

To refresh or download the flags again, run:

```bash
python download_flags.py
```

This step is also included in the Windows launcher.

---

## Troubleshooting

### The GUI does not open

Make sure the virtual environment is activated and PySide6 is installed:

```bash
python -m pip install -r requirements.txt
```

Then run:

```bash
python run.py
```

---

### PowerShell blocks script execution on Windows

If PowerShell does not allow activation of the virtual environment, run PowerShell as your user and execute:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate the environment again:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

### Python is not recognized

Install Python from the official Python website or from the Microsoft Store.

After installation, check that Python is available:

```bash
python --version
```

or on Windows:

```powershell
py --version
```

---

### PySide6 installation fails

Upgrade pip first:

```bash
python -m pip install --upgrade pip
```

Then reinstall the requirements:

```bash
python -m pip install -r requirements.txt
```

---

## Recommended `.gitignore`

For GitHub, it is recommended not to upload local virtual environments, cache files, or generated run folders.

A useful `.gitignore` would be:

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd

# Virtual environments
.venv/
venv/
env/

# IDE files
.vscode/
.idea/

# OS files
.DS_Store
Thumbs.db

# Generated game data
worldcup_2026_runs/
*.rpgsave

# Optional local logs
*.log
```

If you want to keep example saved games in the repository, do not ignore the full `saved_games/` folder. If you want a clean repository without local saved progress, you can also add:

```gitignore
saved_games/
```

---

## License

Add your preferred license here.

For example:

```text
MIT License
```

or:

```text
All rights reserved.
```

---

## Author

Developed by Santiago Galdor Alongil.

---

## Acknowledgements

This project was built as a Python GUI game inspired by football tournaments, World Cup-style competition structures, and RPG-style dice mechanics.
