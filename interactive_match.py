"""Interactive not-simulated RPGsoccer match window."""

from __future__ import annotations

from pathlib import Path
import random
from typing import Callable

from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
except Exception:  # pragma: no cover
    QAudioOutput = None
    QMediaPlayer = None

from ai_random import choose_action, choose_defender, choose_formation
from match_engine import MatchLogger, MatchResult, _apply_consequence
from rpgsoccer_core import (
    Balon,
    Crono,
    Marcador,
    accion_defensiva,
    acciones_validas,
    criterio,
    generar,
    jugadores_por_posicion,
    positions_from_formation,
    team_name,
)
from team_assets import all_teams, flag_emoji

PROJECT_DIR = Path(__file__).resolve().parent
ASSET_DIR = PROJECT_DIR / "assets"
FORMATIONS = ["4 4 2", "3 5 1", "4 3 3", "3 4 3", "5 4 1"]
DIFFICULTY_FACTORS = {"Easy": 1.15, "Normal": 1.05, "Advance": 0.95}
MATCH_MINUTES = 10.0


def formation_from_text(text: str) -> list[int]:
    return [int(part) for part in text.split()]


def dice_combo(dice: list[int]) -> int:
    if len(dice) != 2:
        return 0
    if dice[0] == dice[1] and dice[0] <= 3:
        return -1
    if dice[0] == dice[1] and dice[0] > 3:
        return 1
    return 0


class DiceButton(QPushButton):
    def __init__(self, image_path: Path, text: str) -> None:
        super().__init__(text)
        self.setMinimumSize(132, 132)
        self.setIconSize(QSize(96, 96))
        if image_path.exists():
            self.setIcon(QIcon(str(image_path)))
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("DiceButton")


class ChoiceButton(QPushButton):
    def __init__(self, index: int, callback: Callable[[int], None]) -> None:
        super().__init__("")
        self.index = index
        self.callback = callback
        self.active = False
        self.pending = False
        self.setMinimumHeight(48)
        self.setObjectName("ChoiceButton")
        self.clicked.connect(self.on_clicked)
        self.setEnabled(False)

    def configure(self, text: str, enabled: bool) -> None:
        self.setText(text)
        self.active = enabled
        self.pending = False
        self.setEnabled(enabled)
        self.setProperty("pending", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def on_clicked(self) -> None:
        if not self.active:
            return
        if not self.pending:
            for sibling in self.parent().findChildren(ChoiceButton):
                if sibling is not self:
                    sibling.pending = False
                    sibling.setProperty("pending", False)
                    sibling.style().unpolish(sibling)
                    sibling.style().polish(sibling)
            self.pending = True
            self.setProperty("pending", True)
            self.style().unpolish(self)
            self.style().polish(self)
            return
        self.pending = False
        self.setProperty("pending", False)
        self.style().unpolish(self)
        self.style().polish(self)
        self.callback(self.index)


class GoalDialog(QDialog):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Goal!")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.player = None
        self.audio_output = None

        layout = QVBoxLayout(self)
        title = QLabel("GOAAAAAAAL!")
        title.setObjectName("GoalTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        message = QLabel(text)
        message.setObjectName("PopupText")
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        layout.addWidget(message)

        button = QPushButton("Continue")
        button.clicked.connect(self.accept)
        layout.addWidget(button, alignment=Qt.AlignCenter)
        self.play_audio()

    def play_audio(self) -> None:
        audio_file = ASSET_DIR / "Voicy_Goaaaaaal!!!.mp3"
        if QMediaPlayer is None or QAudioOutput is None or not audio_file.exists():
            return
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.85)
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(str(audio_file)))
        self.player.play()


class TeamSelectionDialog(QDialog):
    """Small team-selection menu used before not-simulated games."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose teams")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)

        title = QLabel("Choose the teams for the not-simulated game")
        title.setObjectName("SectionTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.home_combo = QComboBox()
        self.away_combo = QComboBox()
        self.difficulty_combo = QComboBox()
        for team in all_teams():
            label = f"{flag_emoji(team)} {team}"
            self.home_combo.addItem(label, team)
            self.away_combo.addItem(label, team)
        if self.away_combo.count() > 1:
            self.away_combo.setCurrentIndex(1)
        for difficulty in ["Easy", "Normal", "Advance"]:
            self.difficulty_combo.addItem(difficulty, difficulty)
        self.difficulty_combo.setCurrentText("Normal")

        form = QGridLayout()
        form.addWidget(QLabel("Team 1"), 0, 0)
        form.addWidget(self.home_combo, 0, 1)
        form.addWidget(QLabel("Team 2"), 1, 0)
        form.addWidget(self.away_combo, 1, 1)
        form.addWidget(QLabel("Difficulty"), 2, 0)
        form.addWidget(self.difficulty_combo, 2, 1)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        start = QPushButton("Start game")
        cancel = QPushButton("Cancel")
        start.clicked.connect(self.accept_if_valid)
        cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(start)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        self.apply_style()

    @property
    def selected_teams(self) -> tuple[str, str]:
        return self.home_combo.currentData(), self.away_combo.currentData()

    @property
    def selected_difficulty(self) -> str:
        return self.difficulty_combo.currentData()

    def accept_if_valid(self) -> None:
        home, away = self.selected_teams
        if home == away:
            QMessageBox.warning(self, "Invalid teams", "Please choose two different teams.")
            return
        self.accept()

    def apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background: #071422; color: #f5f7fb; }
            QLabel { color: #f5f7fb; }
            QLabel#SectionTitle { font-size: 18px; font-weight: 900; color: #a8ff00; }
            QPushButton, QComboBox { background: #123f7a; color: white; border: 1px solid #1ed5a5; border-radius: 8px; padding: 8px 10px; font-weight: 700; }
            QPushButton:hover { background: #18559d; }
            """
        )



class PenaltyChoiceDialog(QDialog):
    def __init__(self, title: str, message: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.choice = "Center"
        self.setModal(True)
        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setObjectName("PopupText")
        layout.addWidget(label)
        buttons = QHBoxLayout()
        for choice in ["Left", "Center", "Right"]:
            button = QPushButton(choice)
            button.clicked.connect(lambda checked=False, value=choice: self.choose(value))
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def choose(self, value: str) -> None:
        self.choice = value
        self.accept()

class InteractiveMatchWindow(QDialog):
    """Three-panel human match using the RPGsoccer core rules."""

    def __init__(
        self,
        home: str,
        away: str,
        parent: QWidget | None = None,
        *,
        user_team: str | None = None,
        difficulty: str = "Normal",
        knockout: bool = False,
        stage: str = "Single game",
        match_id: str = "",
        seed: int | None = None,
        minutes: float = MATCH_MINUTES,
        result_callback: Callable[[MatchResult], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("RPGsoccer not-simulated match")
        self.resize(1180, 760)
        self.home = home
        self.away = away
        self.user_team = user_team or home
        self.user_team_index = 0 if self.user_team == self.home else 1
        self.difficulty = difficulty if difficulty in DIFFICULTY_FACTORS else "Normal"
        self.difficulty_factor = DIFFICULTY_FACTORS[self.difficulty]
        self.knockout = knockout
        self.stage = stage
        self.match_id = match_id
        self.match_minutes = float(minutes)
        self.result_callback = result_callback
        self.finished_result: MatchResult | None = None
        self.rng = random.Random(seed)
        self.logger = MatchLogger(print_to_console=False)
        self.score = Marcador()
        self.clock = Crono(0.0)
        self.ball = Balon(0, 1, 11, False)
        self.positions: list[list[str]] = []
        self.teams: list[list] = []
        self.user_formation = ""
        self.cpu_formation = ""
        self.home_formation = ""
        self.away_formation = ""
        self.attacking_team = 0
        self.attacker = 1
        self.defender = 11
        self.defensive_action = ""
        self.selected_action = ""
        self.state = "formation"
        self.choice_mode = "formation"
        self.current_options: list[str] = []
        self.current_values: list[object] = []
        self.user_dice: list[int | None] = [None, None]
        self.cpu_dice: list[int] = []
        self.last_log_index = 0

        self.build_ui()
        self.apply_style()
        self.start_formation_selection()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.score_label = QLabel()
        self.score_label.setObjectName("InteractiveScore")
        self.score_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.score_label)

        bottom = QSplitter(Qt.Horizontal)
        bottom.addWidget(self.build_decision_panel())
        bottom.addWidget(self.build_match_panel())
        bottom.setSizes([520, 640])
        layout.addWidget(bottom, 1)

    def build_decision_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        title = QLabel("Decision and dice board")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        help_label = QLabel("Click once to mark a choice in red. Click the same button again to confirm it.")
        help_label.setObjectName("Subtitle")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self.choice_container = QWidget()
        choice_layout = QVBoxLayout(self.choice_container)
        choice_layout.setContentsMargins(0, 0, 0, 0)
        self.choice_buttons: list[ChoiceButton] = []
        for idx in range(5):
            button = ChoiceButton(idx, self.confirm_choice)
            self.choice_buttons.append(button)
            choice_layout.addWidget(button)
        layout.addWidget(self.choice_container)

        dice_group = QGroupBox("Dice")
        dice_layout = QGridLayout(dice_group)
        self.dice_1_button = DiceButton(ASSET_DIR / "dice_yellow.png", "Dice 1")
        self.dice_2_button = DiceButton(ASSET_DIR / "dice_red.png", "Dice 2")
        self.dice_1_button.clicked.connect(lambda: self.roll_user_die(0))
        self.dice_2_button.clicked.connect(lambda: self.roll_user_die(1))
        self.dice_1_label = QLabel("User dice 1: —")
        self.dice_2_label = QLabel("User dice 2: —")
        self.cpu_label = QLabel("CPU dice: —")
        for label in [self.dice_1_label, self.dice_2_label, self.cpu_label]:
            label.setObjectName("DiceValue")
            label.setAlignment(Qt.AlignCenter)
        dice_layout.addWidget(self.dice_1_button, 0, 0)
        dice_layout.addWidget(self.dice_2_button, 0, 1)
        dice_layout.addWidget(self.dice_1_label, 1, 0)
        dice_layout.addWidget(self.dice_2_label, 1, 1)
        dice_layout.addWidget(self.cpu_label, 2, 0, 1, 2)
        layout.addWidget(dice_group)

        self.phase_label = QLabel("Choose your formation.")
        self.phase_label.setObjectName("StatusLabel")
        self.phase_label.setWordWrap(True)
        layout.addWidget(self.phase_label)
        layout.addStretch(1)
        return panel

    def build_match_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        title = QLabel("Current game")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.field_label = QLabel()
        self.field_label.setMinimumHeight(240)
        self.field_label.setObjectName("FieldLabel")
        self.field_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.field_label)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("GameLog")
        layout.addWidget(self.log_box, 1)
        return panel

    def apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background: #071422; color: #f5f7fb; }
            QLabel { color: #f5f7fb; }
            QGroupBox { border: 1px solid #1ed5a5; border-radius: 12px; margin-top: 10px; padding: 10px; font-weight: 700; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #a8ff00; }
            QPushButton { background: #123f7a; color: white; border: 1px solid #1ed5a5; border-radius: 10px; padding: 8px 12px; font-weight: 700; }
            QPushButton:hover { background: #18559d; }
            QPushButton:disabled { background: #263241; color: #78889a; border: 1px solid #394758; }
            QPushButton#ChoiceButton[pending="true"] { background: #d92545; border: 2px solid #ffe066; }
            QLabel#InteractiveScore { font-size: 28px; font-weight: 900; color: #ffd34d; padding: 14px; border-radius: 16px; background: #0c2240; border: 2px solid #1ed5a5; }
            QLabel#SectionTitle { font-size: 18px; font-weight: 900; color: #a8ff00; }
            QLabel#Subtitle { color: #b8c9dd; }
            QLabel#StatusLabel { color: #ffd34d; font-weight: 700; }
            QLabel#DiceValue { font-size: 16px; font-weight: 800; color: #ffffff; }
            QLabel#FieldLabel { background: #0d612f; border: 2px solid #e8f5e9; border-radius: 20px; font-size: 20px; font-weight: 900; color: white; }
            QTextEdit#GameLog { background: #020819; color: #d8e6f8; border: 1px solid #1ed5a5; border-radius: 12px; padding: 8px; }
            QLabel#GoalTitle { color: #ffd34d; font-size: 34px; font-weight: 900; }
            QLabel#PopupText { font-size: 18px; }
            """
        )

    def start_formation_selection(self) -> None:
        self.state = "formation"
        self.choice_mode = "formation"
        self.phase_label.setText("Choose your formation before the match starts.")
        self.set_choices(FORMATIONS, FORMATIONS)
        self.disable_dice()
        self.update_score()

    def start_match(self, formation: str) -> None:
        self.user_formation = formation
        self.cpu_formation = " ".join(str(x) for x in choose_formation(self.rng))
        user_form = formation_from_text(self.user_formation)
        cpu_form = formation_from_text(self.cpu_formation)
        if self.user_team_index == 0:
            form_home, form_away = user_form, cpu_form
            self.home_formation, self.away_formation = self.user_formation, self.cpu_formation
        else:
            form_home, form_away = cpu_form, user_form
            self.home_formation, self.away_formation = self.cpu_formation, self.user_formation
        self.positions = [positions_from_formation(form_home), positions_from_formation(form_away)]
        self.teams = [generar(0, form_home, self.rng), generar(1, form_away, self.rng)]
        self.apply_user_difficulty_factor()
        self.attacking_team = self.rng.randint(0, 1)
        self.attacker = 1
        self.defender = 11
        self.ball = Balon(self.attacking_team, self.attacker, self.defender, False)
        self.score = Marcador()
        self.clock = Crono(0.0)
        self.logger = MatchLogger(print_to_console=False)
        self.log_line(f"Partido: {self.home} vs {self.away}")
        self.log_line(f"Formación {self.home}: {self.home_formation.replace(' ', '-')}")
        self.log_line(f"Formación {self.away}: {self.away_formation.replace(' ', '-')}")
        self.log_line(f"Equipo de usuario: {self.user_team}. Dificultad: {self.difficulty} (factor {self.difficulty_factor:.2f}).")
        self.log_line(f"Empieza sacando {team_name(self.attacking_team, self.home, self.away)}.")
        self.next_decision()


    def apply_user_difficulty_factor(self) -> None:
        for player in self.teams[self.user_team_index]:
            for skill in list(player.skills):
                player.skills[skill] *= self.difficulty_factor

    def set_choices(self, labels: list[str], values: list[object] | None = None) -> None:
        self.current_options = labels[:5]
        self.current_values = (values if values is not None else labels)[:5]
        for idx, button in enumerate(self.choice_buttons):
            if idx < len(self.current_options):
                button.configure(self.current_options[idx], True)
            else:
                button.configure("", False)

    def confirm_choice(self, index: int) -> None:
        if index >= len(self.current_options):
            return
        value = self.current_values[index]
        if self.state == "formation":
            self.start_match(str(value))
            return
        if self.state != "decision":
            return
        if self.choice_mode == "attack_action":
            self.selected_action = str(value)
            attacker_position = self.positions[self.attacking_team][self.attacker - 1]
            self.defender, self.defensive_action = choose_defender(attacker_position, self.positions[1 - self.attacking_team], self.rng)
        elif self.choice_mode == "defender_choice":
            self.defender = int(value)
            attacker_position = self.positions[self.attacking_team][self.attacker - 1]
            _, self.defensive_action = accion_defensiva(attacker_position)
        else:
            return
        self.start_dice_roll()

    def start_dice_roll(self) -> None:
        self.state = "dice"
        self.user_dice = [None, None]
        self.cpu_dice = []
        self.dice_1_label.setText("User dice 1: —")
        self.dice_2_label.setText("User dice 2: —")
        self.cpu_label.setText("CPU dice: roll your dice")
        self.set_choices([], [])
        self.enable_dice()
        if self.attacking_team == self.user_team_index:
            self.phase_label.setText(f"Action selected: {self.selected_action}. Press both dice to resolve the attacking action.")
        else:
            self.phase_label.setText(f"Defender selected: #{self.defender}. Press both dice to resolve the defensive action.")

    def next_decision(self) -> None:
        if self.clock.minuto > self.match_minutes:
            self.finish_match()
            return
        self.state = "decision"
        self.disable_dice()
        self.dice_1_label.setText("User dice 1: —")
        self.dice_2_label.setText("User dice 2: —")
        self.cpu_label.setText("CPU dice: —")

        attacker_position = self.positions[self.attacking_team][self.attacker - 1]
        attacking_name = team_name(self.attacking_team, self.home, self.away)
        defending_name = team_name(1 - self.attacking_team, self.home, self.away)

        if self.attacking_team == self.user_team_index:
            self.choice_mode = "attack_action"
            actions = acciones_validas(attacker_position)
            self.phase_label.setText(
                f"Minute {self.clock.reloj()}. {attacking_name} attacks with {attacker_position} #{self.attacker}. Choose the RPGsoccer action."
            )
            self.set_choices(actions, actions)
        else:
            self.choice_mode = "defender_choice"
            self.selected_action = choose_action(attacker_position, self.rng)
            defender_position, defensive_action = accion_defensiva(attacker_position)
            defender_numbers = jugadores_por_posicion(self.positions[self.user_team_index], defender_position)
            labels = [f"#{number} {defender_position}" for number in defender_numbers]
            self.defensive_action = defensive_action
            self.phase_label.setText(
                f"Minute {self.clock.reloj()}. {attacking_name} attacks with {attacker_position} #{self.attacker} and chooses {self.selected_action}. "
                f"Choose the {defender_position} who will defend with {defensive_action}."
            )
            self.set_choices(labels, defender_numbers)

        self.log_line("")
        self.log_line(f"Minuto {self.clock.reloj()}.")
        self.log_line(f"{attacking_name} ataca con su {attacker_position} #{self.attacker}.")
        self.log_line(f"Defiende {defending_name}.")
        self.update_score()

    def enable_dice(self) -> None:
        self.dice_1_button.setEnabled(True)
        self.dice_2_button.setEnabled(True)

    def disable_dice(self) -> None:
        self.dice_1_button.setEnabled(False)
        self.dice_2_button.setEnabled(False)

    def roll_user_die(self, index: int) -> None:
        if self.state != "dice" or self.user_dice[index] is not None:
            return
        value = self.rng.randint(1, 6)
        self.user_dice[index] = value
        if index == 0:
            self.dice_1_label.setText(f"User dice 1: {value}")
            self.dice_1_button.setEnabled(False)
        else:
            self.dice_2_label.setText(f"User dice 2: {value}")
            self.dice_2_button.setEnabled(False)
        if all(value is not None for value in self.user_dice):
            self.resolve_core_action()

    def resolve_core_action(self) -> None:
        if not self.positions or not self.teams:
            return
        self.cpu_dice = [self.rng.randint(1, 6), self.rng.randint(1, 6)]
        user_dice = [int(self.user_dice[0] or 0), int(self.user_dice[1] or 0)]
        user_combo = dice_combo(user_dice)
        cpu_combo = dice_combo(self.cpu_dice)
        user_total = sum(user_dice)
        cpu_total = sum(self.cpu_dice)
        self.cpu_label.setText(f"CPU dice: {self.cpu_dice[0]} + {self.cpu_dice[1]} = {cpu_total}")

        attacker_position = self.positions[self.attacking_team][self.attacker - 1]
        defending_team = 1 - self.attacking_team
        if self.attacking_team == self.user_team_index:
            dice_at, combo_at = user_dice, user_combo
            dice_def, combo_def = self.cpu_dice, cpu_combo
        else:
            dice_at, combo_at = self.cpu_dice, cpu_combo
            dice_def, combo_def = user_dice, user_combo

        attacking_player = self.teams[self.attacking_team][self.attacker - 1]
        defending_player = self.teams[defending_team][self.defender - 1]
        f_at = attacking_player.accion(self.selected_action, dice_at)
        f_def = defending_player.accion(self.defensive_action, dice_def)
        fact = criterio(combo_at - combo_def, f_at - f_def, attacker_position, self.selected_action)

        before_home = self.score.local
        before_away = self.score.visitante
        self.log_line(
            f"Acción: {self.selected_action}. Defensa: #{self.defender} con {self.defensive_action}."
        )
        self.log_line(f"Dados usuario {user_dice}; dados CPU {self.cpu_dice}.")
        self.log_line(f"Dados ataque {dice_at}; dados defensa {dice_def}.")
        self.log_line(f"Diferencia de fuerza: {f_at - f_def:.2f}. Consecuencia RPGsoccer: {fact}.")
        start_index = len(self.logger.lines)

        try:
            self.attacking_team, self.attacker, self.defender, action_for_clock = _apply_consequence(
                fact,
                self.attacking_team,
                self.attacker,
                self.defender,
                self.score,
                self.ball,
                self.positions,
                self.teams,
                self.rng,
                self.logger,
                self.home,
                self.away,
                self.selected_action,
            )
        except Exception as exc:
            QMessageBox.critical(self, "RPGsoccer error", str(exc))
            self.finish_match()
            return

        self.clock.lapso(action_for_clock)
        for line in self.logger.lines[start_index:]:
            if line and self.log_box.toPlainText().splitlines()[-1:] != [line]:
                self.log_box.append(line)
        consequence_lines = [line for line in self.logger.lines[start_index:] if line]
        consequence_text = "\n".join(consequence_lines[-8:]) or "The action has been resolved."
        self.update_score()
        goal = self.score.local != before_home or self.score.visitante != before_away
        if goal:
            GoalDialog(consequence_text, self).exec()
        else:
            QMessageBox.information(self, "Action consequence", consequence_text)
        self.next_decision()

    def finish_match(self) -> None:
        self.state = "finished"
        self.disable_dice()
        self.set_choices([], [])
        penalties_home = None
        penalties_away = None
        if self.knockout and self.score.local == self.score.visitante:
            penalties_home, penalties_away = self.resolve_penalties()

        winner = None
        loser = None
        if self.score.local > self.score.visitante or (penalties_home is not None and penalties_home > penalties_away):
            winner, loser = self.home, self.away
            text = f"Final del partido: {self.home} wins {self.score.local}-{self.score.visitante}."
        elif self.score.local < self.score.visitante or (penalties_away is not None and penalties_away > penalties_home):
            winner, loser = self.away, self.home
            text = f"Final del partido: {self.away} wins {self.score.visitante}-{self.score.local}."
        else:
            text = f"Final del partido: Draw {self.score.local}-{self.score.visitante}."
        if penalties_home is not None and penalties_away is not None:
            text += f" Penalties: {penalties_home}-{penalties_away}."
        self.phase_label.setText(text)
        self.log_line("")
        self.log_line(text)
        self.update_score()
        self.finished_result = MatchResult(
            home=self.home,
            away=self.away,
            home_goals=self.score.local,
            away_goals=self.score.visitante,
            winner=winner,
            loser=loser,
            penalties_home=penalties_home,
            penalties_away=penalties_away,
            stage=self.stage,
            match_id=self.match_id,
            log_lines=list(self.logger.lines),
        )
        if self.result_callback is not None:
            self.result_callback(self.finished_result)

    def resolve_penalties(self) -> tuple[int, int]:
        self.log_line("Penalty shoot-out.")
        home_pens = 0
        away_pens = 0
        kicks = 0
        options = ["Left", "Center", "Right"]
        while kicks < 5 or home_pens == away_pens:
            kicks += 1
            # Home kick
            if self.user_team_index == 0:
                shot = self.ask_penalty_choice("Penalty for " + self.home, "Choose where to shoot.")
                keeper = self.rng.choice(options)
            else:
                shot = self.rng.choice(options)
                keeper = self.ask_penalty_choice("Penalty for " + self.home, "Choose where your goalkeeper jumps.")
            if shot != keeper:
                home_pens += 1
                self.log_line(f"{self.home} penalty {kicks}: goal ({shot} vs keeper {keeper}).")
            else:
                self.log_line(f"{self.home} penalty {kicks}: saved ({shot}).")

            # Away kick
            if self.user_team_index == 1:
                shot = self.ask_penalty_choice("Penalty for " + self.away, "Choose where to shoot.")
                keeper = self.rng.choice(options)
            else:
                shot = self.rng.choice(options)
                keeper = self.ask_penalty_choice("Penalty for " + self.away, "Choose where your goalkeeper jumps.")
            if shot != keeper:
                away_pens += 1
                self.log_line(f"{self.away} penalty {kicks}: goal ({shot} vs keeper {keeper}).")
            else:
                self.log_line(f"{self.away} penalty {kicks}: saved ({shot}).")

            if kicks >= 5 and home_pens != away_pens:
                break
        return home_pens, away_pens

    def ask_penalty_choice(self, title: str, message: str) -> str:
        dialog = PenaltyChoiceDialog(title, message, self)
        dialog.exec()
        return dialog.choice

    def update_score(self) -> None:
        self.score_label.setText(f"{self.score.local}   {self.home}    -    {self.away}   {self.score.visitante}")
        possession = team_name(self.attacking_team, self.home, self.away) if self.state != "formation" else "—"
        attacker_text = "—"
        defender_text = "—"
        if self.positions and self.state != "formation":
            attacker_position = self.positions[self.attacking_team][self.attacker - 1]
            attacker_text = f"{team_name(self.attacking_team, self.home, self.away)} {attacker_position} #{self.attacker}"
            defender_text = f"#{self.defender}"
        self.field_label.setText(
            f"{self.home} ({self.home_formation or 'formation pending'})\n"
            f"vs\n{self.away} ({self.away_formation or 'formation pending'})\n\n"
            f"Minute {self.clock.reloj()} / {self.match_minutes:g}:00 · Ball: {possession}\n"
            f"Attacker: {attacker_text} · Defender: {defender_text}"
        )

    def log_line(self, text: str) -> None:
        self.logger.write(text)
        self.log_box.append(text)
