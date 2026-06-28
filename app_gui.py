"""Main menu for the RPGsoccer World Cup program."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from interactive_match import InteractiveMatchWindow, TeamSelectionDialog
from team_assets import all_teams, flag_emoji
from tournament import WorldCupSimulator
from worldcup_gui import RUNS_DIR, SAVED_GAMES_DIR, WorldCupWindow
from history_store import add_history, generate_unique_seed, top_history

PROJECT_DIR = Path(__file__).resolve().parent


def mask_seed_text(text: str) -> str:
    """Hide seed values before showing saved/run details in the GUI."""
    lines = []
    for line in text.splitlines():
        if line.strip().lower().startswith("seed:"):
            prefix = line[:len(line) - len(line.lstrip())]
            lines.append(f"{prefix}Seed: hidden")
        else:
            lines.append(line)
    return "\n".join(lines)


class CompetitionSetupDialog(QDialog):
    def __init__(self, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle(mode)
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        title = QLabel(mode)
        title.setObjectName("MenuTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        info = QLabel(
            "The World Cup mode uses the official 48-team group structure included in the program. "
            "The complete competition browser will open with Live games, Groups, Thirds, Knockout and Podium tabs."
        )
        info.setObjectName("MenuSubtitle")
        info.setWordWrap(True)
        layout.addWidget(info)

        settings = QGroupBox("Competition settings")
        grid = QGridLayout(settings)
        self.minutes_spin = QDoubleSpinBox()
        self.minutes_spin.setRange(1.0, 90.0)
        self.minutes_spin.setDecimals(1)
        self.minutes_spin.setValue(10.0)
        self.minutes_spin.setSuffix(" min")
        self.team_combo = QComboBox()
        self.difficulty_combo = QComboBox()
        for difficulty in ["Easy", "Normal", "Advance"]:
            self.difficulty_combo.addItem(difficulty, difficulty)
        self.difficulty_combo.setCurrentText("Normal")
        self.user_name_edit = QLineEdit()
        self.user_name_edit.setPlaceholderText("Player name")
        self.user_name_edit.setText("Player 1")
        for team in all_teams():
            self.team_combo.addItem(f"{flag_emoji(team)} {team}", team)
        team_label = "Predicted champion" if self.mode == "Guess the Winner" else "Team to follow"
        grid.addWidget(QLabel("Player name"), 0, 0)
        grid.addWidget(self.user_name_edit, 0, 1)
        grid.addWidget(QLabel("Match duration"), 1, 0)
        grid.addWidget(self.minutes_spin, 1, 1)
        grid.addWidget(QLabel(team_label), 2, 0)
        grid.addWidget(self.team_combo, 2, 1)
        grid.addWidget(QLabel("Difficulty"), 3, 0)
        grid.addWidget(self.difficulty_combo, 3, 1)
        layout.addWidget(settings)

        note_text = (
            "The Live games tab will open filtered to your selected team. "
            "You can clear the filter or choose another team inside the competition browser."
        )
        if self.mode == "Guess the Winner":
            note_text = (
                "This team is saved as your champion prediction. The match-by-match Guess the Winner panel "
                "will still pause before each game so you can predict Home / Draw / Away."
            )
        note = QLabel(note_text)
        note.setObjectName("MenuSubtitle")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QHBoxLayout()
        open_button = QPushButton("Open competition window")
        cancel_button = QPushButton("Cancel")
        open_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(open_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        self.apply_style()

    @property
    def settings(self) -> tuple[int, float, str]:
        return self.minutes_spin.value(), self.team_combo.currentData(), self.difficulty_combo.currentData(), self.user_name_edit.text().strip() or "Player 1"


    def apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background: #071422; color: #f5f7fb; }
            QLabel { color: #f5f7fb; }
            QLabel#MenuTitle { font-size: 28px; font-weight: 900; color: #ffd34d; }
            QLabel#MenuSubtitle { color: #b8c9dd; font-size: 13px; }
            QGroupBox { border: 1px solid #1ed5a5; border-radius: 12px; margin-top: 10px; padding: 10px; font-weight: 700; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #a8ff00; }
            QPushButton, QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox { background: #123f7a; color: white; border: 1px solid #1ed5a5; border-radius: 8px; padding: 8px 10px; font-weight: 700; }
            QPushButton:hover { background: #18559d; }
            """
        )



class GuessSetupDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guess the Winner")
        self.resize(900, 700)
        self._teams = all_teams()
        self._updating_podium_combos = False
        layout = QVBoxLayout(self)
        title = QLabel("Guess the podium")
        title.setObjectName("MenuTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        info = QLabel(
            "Add between 1 and 48 users. Each user chooses the predicted 1st, 2nd and 3rd teams. "
            "The seed is generated automatically and is never reused from saved games on this computer."
        )
        info.setObjectName("MenuSubtitle")
        info.setWordWrap(True)
        layout.addWidget(info)

        settings = QHBoxLayout()
        self.minutes_spin = QDoubleSpinBox()
        self.minutes_spin.setRange(1.0, 90.0)
        self.minutes_spin.setDecimals(1)
        self.minutes_spin.setValue(10.0)
        self.minutes_spin.setSuffix(" min")
        self.user_count_spin = QSpinBox()
        self.user_count_spin.setRange(1, 48)
        self.user_count_spin.setValue(1)
        self.user_count_spin.valueChanged.connect(self.rebuild_rows)
        settings.addWidget(QLabel("Users"))
        settings.addWidget(self.user_count_spin)
        settings.addWidget(QLabel("Match duration"))
        settings.addWidget(self.minutes_spin)
        settings.addStretch(1)
        layout.addLayout(settings)

        self.rows_widget = QWidget()
        self.rows_layout = QGridLayout(self.rows_widget)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.rows_widget)
        layout.addWidget(self.scroll, 1)
        self.rows: list[tuple[QLineEdit, QComboBox, QComboBox, QComboBox]] = []
        self.rebuild_rows()

        buttons = QHBoxLayout()
        start = QPushButton("Start simulation")
        cancel = QPushButton("Cancel")
        start.clicked.connect(self.accept_if_valid)
        cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(start)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        self.apply_style()

    def rebuild_rows(self) -> None:
        previous_rows = []
        for name, first, second, third in getattr(self, "rows", []):
            previous_rows.append((
                name.text(),
                first.currentData() or "",
                second.currentData() or "",
                third.currentData() or "",
            ))

        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.rows.clear()
        headers = ["User", "1st", "2nd", "3rd"]
        for col, text in enumerate(headers):
            label = QLabel(text)
            label.setObjectName("SectionTitle")
            self.rows_layout.addWidget(label, 0, col)
        for row in range(self.user_count_spin.value()):
            name = QLineEdit()
            name.setText(previous_rows[row][0] if row < len(previous_rows) else f"Player {row + 1}")
            combos = []
            for offset in range(3):
                combo = QComboBox()
                combo.addItem("", "")
                for team in self._teams:
                    combo.addItem(f"{flag_emoji(team)} {team}", team)
                if row < len(previous_rows):
                    value = previous_rows[row][offset + 1]
                    index = combo.findData(value)
                    combo.setCurrentIndex(index if index >= 0 else 0)
                else:
                    combo.setCurrentIndex(0)
                combo.currentIndexChanged.connect(lambda _index, self=self: self.update_podium_combo_options())
                combos.append(combo)
            self.rows_layout.addWidget(name, row + 1, 0)
            for col, combo in enumerate(combos, 1):
                self.rows_layout.addWidget(combo, row + 1, col)
            self.rows.append((name, combos[0], combos[1], combos[2]))
        self.update_podium_combo_options()

    def update_podium_combo_options(self) -> None:
        if self._updating_podium_combos:
            return
        self._updating_podium_combos = True
        try:
            for position in range(3):
                combos = [row[position + 1] for row in self.rows]
                selected = {combo.currentData() for combo in combos if combo.currentData()}
                for combo in combos:
                    current = combo.currentData() or ""
                    combo.blockSignals(True)
                    try:
                        combo.clear()
                        combo.addItem("", "")
                        for team in self._teams:
                            if team == current or team not in selected:
                                combo.addItem(f"{flag_emoji(team)} {team}", team)
                        index = combo.findData(current)
                        combo.setCurrentIndex(index if index >= 0 else 0)
                    finally:
                        combo.blockSignals(False)
        finally:
            self._updating_podium_combos = False

    def accept_if_valid(self) -> None:
        position_labels = ["1st", "2nd", "3rd"]
        for name, first, second, third in self.rows:
            user = name.text().strip() or "A user"
            picks = [first.currentData() or "", second.currentData() or "", third.currentData() or ""]
            if not all(picks):
                QMessageBox.warning(self, "Invalid podium", f"{user} must choose a 1st, 2nd and 3rd team.")
                return
            if len(set(picks)) != 3:
                QMessageBox.warning(self, "Invalid podium", f"{user} must choose three different teams.")
                return
        for position, label in enumerate(position_labels):
            picks = [row[position + 1].currentData() or "" for row in self.rows]
            if len(set(picks)) != len(picks):
                QMessageBox.warning(self, "Invalid podium", f"The same team cannot be chosen twice as {label}.")
                return
        self.accept()

    @property
    def settings(self) -> tuple[float, list[dict[str, str]]]:
        guesses = []
        for name, first, second, third in self.rows:
            guesses.append({
                "name": name.text().strip() or "Player",
                "first": first.currentData() or "",
                "second": second.currentData() or "",
                "third": third.currentData() or "",
            })
        return self.minutes_spin.value(), guesses

    def apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background: #071422; color: #f5f7fb; }
            QLabel { color: #f5f7fb; }
            QLabel#MenuTitle { font-size: 28px; font-weight: 900; color: #ffd34d; }
            QLabel#MenuSubtitle { color: #b8c9dd; font-size: 13px; }
            QLabel#SectionTitle { color: #a8ff00; font-weight: 900; }
            QPushButton, QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox { background: #123f7a; color: white; border: 1px solid #1ed5a5; border-radius: 8px; padding: 8px 10px; font-weight: 700; }
            QPushButton:hover { background: #18559d; }
            """
        )


class HistoryDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("History")
        self.resize(900, 620)
        layout = QVBoxLayout(self)

        title = QLabel("History")
        title.setObjectName("MenuTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        body = QHBoxLayout()
        self.saved_list = QListWidget()
        self.runs_list = QListWidget()
        body.addWidget(self.build_list_box("Saved tournaments", self.saved_list), 1)
        body.addWidget(self.build_list_box("Generated run folders", self.runs_list), 1)
        layout.addLayout(body, 1)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select a saved game or a run folder to see details.")
        layout.addWidget(self.preview, 1)

        self.history_tabs = QTabWidget()
        self.single_table = QTableWidget(0, 5)
        self.tournament_table = QTableWidget(0, 5)
        self.guess_table = QTableWidget(0, 4)
        self.single_table.setHorizontalHeaderLabels(["User", "Match", "Result", "Difficulty", "Date/time"])
        self.tournament_table.setHorizontalHeaderLabels(["User", "Team", "Final position", "Difficulty", "Date/time"])
        self.guess_table.setHorizontalHeaderLabels(["User", "Points", "Podium guess", "Date/time"])
        self.history_tabs.addTab(self.single_table, "Single game TOP 50")
        self.history_tabs.addTab(self.tournament_table, "Tournaments TOP 50")
        self.history_tabs.addTab(self.guess_table, "Guess the Winner TOP 50")
        layout.addWidget(self.history_tabs, 1)

        buttons = QHBoxLayout()
        load_button = QPushButton("Load selected save")
        open_button = QPushButton("Choose save file")
        close_button = QPushButton("Close")
        load_button.clicked.connect(self.load_selected_save)
        open_button.clicked.connect(self.load_external_save)
        close_button.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(load_button)
        buttons.addWidget(open_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.loaded_window: WorldCupWindow | None = None
        self.saved_list.itemSelectionChanged.connect(self.preview_saved)
        self.runs_list.itemSelectionChanged.connect(self.preview_run)
        self.populate()
        self.populate_historical_tables()
        self.apply_style()

    def build_list_box(self, title: str, widget: QListWidget) -> QGroupBox:
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(widget)
        return box

    def populate(self) -> None:
        self.saved_list.clear()
        self.runs_list.clear()
        SAVED_GAMES_DIR.mkdir(parents=True, exist_ok=True)
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        for path in sorted(SAVED_GAMES_DIR.glob("*.rpgsave"), key=lambda p: p.stat().st_mtime, reverse=True):
            item = QListWidgetItem(path.name)
            item.setData(Qt.UserRole, str(path))
            self.saved_list.addItem(item)
        for path in sorted((p for p in RUNS_DIR.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True):
            item = QListWidgetItem(path.name)
            item.setData(Qt.UserRole, str(path))
            self.runs_list.addItem(item)

    def preview_saved(self) -> None:
        item = self.saved_list.currentItem()
        if not item:
            return
        path = Path(item.data(Qt.UserRole))
        try:
            simulator = WorldCupSimulator.load_game(path)
            champion, runner_up, third = simulator.podium
            self.preview.setPlainText(
                f"Saved file: {path}\n"
                "Seed: hidden\n"
                f"Minutes: {simulator.minutes}\n"
                f"Matches played: {len(simulator.match_results)}\n"
                f"Champion: {champion or '—'}\n"
                f"Runner-up: {runner_up or '—'}\n"
                f"Third place: {third or '—'}\n"
            )
        except Exception as exc:
            self.preview.setPlainText(f"Could not read saved game:\n{path}\n\n{exc}")

    def preview_run(self) -> None:
        item = self.runs_list.currentItem()
        if not item:
            return
        path = Path(item.data(Qt.UserRole))
        summary = path / "worldcup_summary.txt"
        if summary.exists():
            self.preview.setPlainText(mask_seed_text(summary.read_text(encoding="utf-8", errors="replace")))
        else:
            files = sorted(str(p.relative_to(path)) for p in path.rglob("*.txt"))[:80]
            self.preview.setPlainText(f"Run folder: {path}\n\n" + "\n".join(files))

    def load_selected_save(self) -> None:
        item = self.saved_list.currentItem()
        if not item:
            QMessageBox.information(self, "No save selected", "Select a saved tournament first.")
            return
        self.open_saved_game(Path(item.data(Qt.UserRole)))

    def load_external_save(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Load tournament", str(SAVED_GAMES_DIR), "RPGsoccer save (*.rpgsave)")
        if filename:
            self.open_saved_game(Path(filename))

    def open_saved_game(self, path: Path) -> None:
        try:
            simulator = WorldCupSimulator.load_game(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return
        window = WorldCupWindow(mode="Tournament")
        window.simulator = simulator
        window.sync_mode_state_from_simulator()
        window.set_controls_from_simulator()
        window.running = False
        window.paused = True
        window.timer.stop()
        window.live_log.clear()
        window.live_log.append(f"Loaded game: {path}")
        window.current_match_label.setText("Saved tournament loaded.")
        window.current_score_label.setText(f"Matches played: {len(window.simulator.match_results)}")
        window.status_label.setText(f"Loaded game: {path}")
        window.refresh_all()
        window.show()
        self.loaded_window = window


    def populate_historical_tables(self) -> None:
        self.fill_table(self.single_table, [
            [row.get("user", ""), row.get("match", ""), row.get("result", ""), row.get("difficulty", ""), row.get("date_time", "")]
            for row in top_history("single_game")
        ])
        self.fill_table(self.tournament_table, [
            [row.get("user", ""), row.get("team", ""), row.get("final_position", ""), row.get("difficulty", ""), row.get("date_time", "")]
            for row in top_history("tournament")
        ])
        self.fill_table(self.guess_table, [
            [row.get("user", ""), row.get("points", ""), row.get("guess", ""), row.get("date_time", "")]
            for row in top_history("guess_the_winner")
        ])

    def fill_table(self, table: QTableWidget, rows: list[list[object]]) -> None:
        table.setRowCount(len(rows))
        for row_idx, row_values in enumerate(rows):
            for col_idx, value in enumerate(row_values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter if col_idx != 2 else Qt.AlignLeft | Qt.AlignVCenter)
                table.setItem(row_idx, col_idx, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background: #071422; color: #f5f7fb; }
            QLabel { color: #f5f7fb; }
            QLabel#MenuTitle { font-size: 28px; font-weight: 900; color: #ffd34d; }
            QGroupBox { border: 1px solid #1ed5a5; border-radius: 12px; margin-top: 10px; padding: 10px; font-weight: 700; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #a8ff00; }
            QPushButton, QListWidget { background: #123f7a; color: white; border: 1px solid #1ed5a5; border-radius: 8px; padding: 8px 10px; font-weight: 700; }
            QTabWidget::pane { border: 1px solid #1ed5a5; border-radius: 8px; }
            QTabBar::tab { background: white; color: black; border: 1px solid #1ed5a5; border-bottom: none; padding: 8px 12px; font-weight: 800; }
            QTabBar::tab:selected { background: #e8f4ff; color: black; }
            QTableWidget, QHeaderView::section { background: white; color: black; border: 1px solid #c4d4e4; }
            QTextEdit { background: #020819; color: #d8e6f8; border: 1px solid #1ed5a5; border-radius: 12px; padding: 8px; }
            QPushButton:hover { background: #18559d; }
            """
        )


class MainMenuWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RPGsoccer World Cup")
        self.resize(760, 560)
        self.child_windows: list[QWidget] = []
        self.build_ui()
        self.apply_style()

    def build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(40, 34, 40, 34)
        layout.setSpacing(16)

        title = QLabel("RPGsoccer World Cup")
        title.setObjectName("MainTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Choose a game style. The original competition browser and History menu are kept available from here.")
        subtitle.setObjectName("MainSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        menu = QGroupBox("Main menu")
        menu_layout = QVBoxLayout(menu)
        buttons = [
            ("Tournament", self.open_tournament),
            ("Guess the Winner", self.open_guess),
            ("Play not-simulated game", self.open_interactive),
            ("History", self.open_history),
            ("Exit", self.close),
        ]
        for text, callback in buttons:
            button = QPushButton(text)
            button.setMinimumHeight(52)
            button.clicked.connect(callback)
            menu_layout.addWidget(button)
        layout.addWidget(menu, 1)

        self.setCentralWidget(root)

    def open_competition(self, mode: str) -> None:
        if mode == "Guess the Winner":
            guess_dialog = GuessSetupDialog(self)
            if guess_dialog.exec() != QDialog.Accepted:
                return
            minutes, guesses = guess_dialog.settings
            window = WorldCupWindow(
                mode=mode,
                seed=generate_unique_seed(),
                minutes=minutes,
                selected_team=None,
                guess_players=guesses,
            )
        else:
            dialog = CompetitionSetupDialog(mode, self)
            if dialog.exec() != QDialog.Accepted:
                return
            minutes, selected_team, difficulty, user_name = dialog.settings
            window = WorldCupWindow(
                mode=mode,
                seed=generate_unique_seed(),
                minutes=minutes,
                selected_team=selected_team,
                difficulty=difficulty,
                user_name=user_name,
            )
        window.show()
        self.child_windows.append(window)

    def open_tournament(self) -> None:
        self.open_competition("Tournament")

    def open_guess(self) -> None:
        self.open_competition("Guess the Winner")

    def open_interactive(self) -> None:
        dialog = TeamSelectionDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        home, away = dialog.selected_teams
        difficulty = dialog.selected_difficulty
        def save_single_history(result):
            add_history("single_game", {
                "user": "Player 1",
                "match": f"{result.home} vs {result.away}",
                "result": result.scoreline(),
                "difficulty": difficulty,
            })
        window = InteractiveMatchWindow(home, away, self, difficulty=difficulty, result_callback=save_single_history)
        window.show()
        self.child_windows.append(window)

    def open_history(self) -> None:
        dialog = HistoryDialog(self)
        dialog.exec()


    def apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #071422; color: #f5f7fb; }
            QLabel { color: #f5f7fb; }
            QLabel#MainTitle { font-size: 38px; font-weight: 900; color: #ffd34d; }
            QLabel#MainSubtitle { color: #b8c9dd; font-size: 14px; }
            QGroupBox { border: 1px solid #1ed5a5; border-radius: 18px; margin-top: 12px; padding: 18px; font-size: 16px; font-weight: 900; }
            QGroupBox::title { subcontrol-origin: margin; left: 18px; padding: 0 8px; color: #a8ff00; }
            QPushButton { background: #123f7a; color: white; border: 1px solid #1ed5a5; border-radius: 14px; padding: 10px 14px; font-size: 16px; font-weight: 800; }
            QPushButton:hover { background: #18559d; }
            """
        )


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("RPGsoccer World Cup")
    window = MainMenuWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
