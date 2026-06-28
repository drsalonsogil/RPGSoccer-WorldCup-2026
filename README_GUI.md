# RPGsoccer World Cup GUI

This package keeps the full World Cup competition browser from `rpgsoccer_worldcup_simulator_final` and adds the requested menu flow and interactive not-simulated game interface.

## Main features

- Initial menu with Tournament, Guess the Winner, not-simulated game, History and Exit.
- Tournament asks for the user name, difficulty and team to control, then opens the full competition window with Run, Pause, Save and Load controls. Matches involving the selected team are played in the RPGsoccer non-simulated GUI; all other matches are simulated.
- Guess the Winner asks for 1 to 48 users and their predicted podiums, then opens the full competition window with Run, Pause, Save and Load controls. The original podium-points logic is restored.
- Competition tabs: Live games, Groups, Thirds, Knockout and Podium.
- Guess the Winner mode scores each user: exact podium position = 25 points; otherwise Winner = 20, 2nd = 15, 3rd = 10, 4th = 5, QF = 3, R16 = 2, R32 = 1.
- Random seeds are generated automatically and checked against seeds found in saved games on the computer.
- Not-simulated games include:
  - a top score panel,
  - a left decision and dice panel,
  - a right current-game panel,
  - five reusable choice buttons,
  - double-click confirmation for choices,
  - two clickable dice images,
  - CPU dice value,
  - consequence pop-up after each action,
  - goal pop-up with the included `Voicy_Goaaaaaal!!!.mp3` audio.
- Formation choice before not-simulated matches: 4 4 2, 3 5 1, 4 3 3, 3 4 3 and 5 4 1.

## Installation on Windows / VS Code

From the project folder:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python download_flags.py
python run.py
```

You can also run:

```powershell
.\run_gui.bat
```

Saved games are stored in `saved_games/` and generated tournament folders are stored in `worldcup_2026_runs/`.
