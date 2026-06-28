"""PySide6 graphical interface for the RPGsoccer World Cup 2026 simulator."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Iterable

from PySide6.QtCore import Qt, QTimer, QSize, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtSvgWidgets import QSvgWidget
except Exception:  # pragma: no cover
    QSvgWidget = None

from match_engine import MatchResult
from team_assets import asset_root, all_teams, flag_emoji, flag_path
from tournament import TeamStats, WorldCupSimulator, rank_stats
from interactive_match import InteractiveMatchWindow
from history_store import add_history, generate_unique_seed
from worldcup_2026_data import (
    FINAL,
    GROUPS,
    GROUP_MATCH_PAIRINGS,
    QUARTER_FINALS,
    ROUND32_MATCHES,
    ROUND_OF_16,
    SEMI_FINALS,
    THIRD_PLACE_MATCH,
)


PROJECT_DIR = Path(__file__).resolve().parent
SAVED_GAMES_DIR = PROJECT_DIR / "saved_games"
RUNS_DIR = PROJECT_DIR / "worldcup_2026_runs"
GUI_VERSION = "current-live-browser-podium"


def seed_status_text(minutes: float, played: int | None = None) -> str:
    if played is None:
        return f"Random seed hidden · {minutes:g} min"
    return f"Random seed hidden · {minutes:g} min · Matches played: {played}"


def find_asset_file(*names: str) -> Path:
    """Return the first existing GUI asset, accepting both packaged and local files."""
    search_dirs = [asset_root(), PROJECT_DIR]
    for directory in search_dirs:
        for name in names:
            candidate = directory / name
            if candidate.exists():
                return candidate
    return asset_root() / names[0]

ROUND_IDS = {
    "Round of 32": [f"M{i}" for i in range(73, 89)],
    "Round of 16": [f"M{i}" for i in range(89, 97)],
    "Quarter-finals": [f"M{i}" for i in range(97, 101)],
    "Semi-finals": ["M101", "M102"],
    "Third place": ["M103"],
    "Final": ["M104"],
}


BRACKET_LEFT_R32 = ["M74", "M77", "M73", "M75", "M83", "M84", "M81", "M82"]
BRACKET_RIGHT_R32 = ["M76", "M78", "M79", "M80", "M86", "M88", "M85", "M87"]
BRACKET_LEFT_R16 = ["M89", "M90", "M93", "M94"]
BRACKET_RIGHT_R16 = ["M91", "M92", "M95", "M96"]
BRACKET_LEFT_QF = ["M97", "M98"]
BRACKET_RIGHT_QF = ["M99", "M100"]
BRACKET_LEFT_SF = ["M101"]
BRACKET_RIGHT_SF = ["M102"]

MATCH_DEPENDENCIES = {match_id: (left, right) for match_id, left, right in ROUND_OF_16 + QUARTER_FINALS + SEMI_FINALS}
MATCH_DEPENDENCIES[FINAL[0]] = (FINAL[1], FINAL[2])
MATCH_DEPENDENCIES[THIRD_PLACE_MATCH[0]] = ("L101", "L102")
ROUND32_SLOTS = {item["id"]: (item["home"], item["away"]) for item in ROUND32_MATCHES}


class KnockoutBracketWidget(QWidget):
    """Custom painted World Cup knockout bracket.

    The widget is deliberately self-contained so the GUI can refresh it after
    every match without changing the tournament engine.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.simulator: WorldCupSimulator | None = None
        self.setMinimumSize(1080, 640)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(1380, 760)

    def set_simulator(self, simulator: WorldCupSimulator | None) -> None:
        self.simulator = simulator
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        base_w = 1380.0
        base_h = 760.0
        scale = min(self.width() / base_w, self.height() / base_h)
        x_offset = (self.width() - base_w * scale) / 2.0
        y_offset = (self.height() - base_h * scale) / 2.0
        painter.translate(x_offset, y_offset)
        painter.scale(scale, scale)

        self.draw_background(painter, base_w, base_h)
        self.draw_titles(painter, base_w)
        positions = self.match_positions()
        self.draw_connectors(painter, positions)
        self.draw_matches(painter, positions)
        self.draw_centerpiece(painter, base_w, base_h)

    def draw_background(self, painter: QPainter, width: float, height: float) -> None:
        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0.0, QColor("#123f7a"))
        gradient.setColorAt(0.35, QColor("#07152d"))
        gradient.setColorAt(0.75, QColor("#020819"))
        gradient.setColorAt(1.0, QColor("#051326"))
        painter.fillRect(QRectF(0, 0, width, height), gradient)

        painter.setPen(QPen(QColor(255, 255, 255, 26), 2))
        for x in [120, 300, 1080, 1260]:
            painter.drawLine(int(x), 115, int(x + 120), 720)
        painter.setPen(QPen(QColor("#1ed5a5"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(18, 18, width - 36, height - 36), 26, 26)

    def draw_titles(self, painter: QPainter, width: float) -> None:
        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 24, QFont.Black)
        font.setItalic(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 20, width, 36), Qt.AlignCenter, "WORLD CUP 2026 KNOCKOUT BRACKET")

        painter.setPen(QPen(QColor("#ff2c6d"), 6))
        painter.drawLine(360, 64, 1020, 64)

        painter.setPen(QColor("#a8ff00"))
        sub_font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(sub_font)
        method = "pending"
        if self.simulator and self.simulator.third_assignment_method:
            method = self.simulator.third_assignment_method
        painter.drawText(QRectF(0, 70, width, 22), Qt.AlignCenter, f"Round of 32 · Round of 16 · Quarter-finals · Semi-finals · Final · third-place slots: {method}")

        painter.setPen(QColor("#9fb7d8"))
        small = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(small)
        for text, x in [("R32", 58), ("R16", 258), ("QF", 451), ("SF", 586), ("FINAL", 690), ("SF", 794), ("QF", 929), ("R16", 1112), ("R32", 1272)]:
            painter.drawText(QRectF(x - 38, 92, 76, 20), Qt.AlignCenter, text)

    def match_positions(self) -> dict[str, QRectF]:
        positions: dict[str, QRectF] = {}
        box_w = 150.0
        box_h = 48.0
        left_x = {"r32": 34.0, "r16": 205.0, "qf": 376.0, "sf": 512.0}
        right_x = {"sf": 718.0, "qf": 854.0, "r16": 1025.0, "r32": 1196.0}

        r32_y = [118, 186, 254, 322, 390, 458, 526, 594]
        r32_centers = [y + box_h / 2.0 for y in r32_y]
        r16_centers = [(r32_centers[i] + r32_centers[i + 1]) / 2.0 for i in range(0, 8, 2)]
        qf_centers = [(r16_centers[i] + r16_centers[i + 1]) / 2.0 for i in range(0, 4, 2)]
        sf_centers = [(qf_centers[0] + qf_centers[1]) / 2.0]
        r16_y = [center - box_h / 2.0 for center in r16_centers]
        qf_y = [center - box_h / 2.0 for center in qf_centers]
        sf_y = [center - box_h / 2.0 for center in sf_centers]

        for match_id, y in zip(BRACKET_LEFT_R32, r32_y):
            positions[match_id] = QRectF(left_x["r32"], y, box_w, box_h)
        for match_id, y in zip(BRACKET_LEFT_R16, r16_y):
            positions[match_id] = QRectF(left_x["r16"], y, box_w, box_h)
        for match_id, y in zip(BRACKET_LEFT_QF, qf_y):
            positions[match_id] = QRectF(left_x["qf"], y, box_w, box_h)
        for match_id, y in zip(BRACKET_LEFT_SF, sf_y):
            positions[match_id] = QRectF(left_x["sf"], y, box_w, box_h)

        for match_id, y in zip(BRACKET_RIGHT_R32, r32_y):
            positions[match_id] = QRectF(right_x["r32"], y, box_w, box_h)
        for match_id, y in zip(BRACKET_RIGHT_R16, r16_y):
            positions[match_id] = QRectF(right_x["r16"], y, box_w, box_h)
        for match_id, y in zip(BRACKET_RIGHT_QF, qf_y):
            positions[match_id] = QRectF(right_x["qf"], y, box_w, box_h)
        for match_id, y in zip(BRACKET_RIGHT_SF, sf_y):
            positions[match_id] = QRectF(right_x["sf"], y, box_w, box_h)

        positions["M104"] = QRectF(615.0, 252.0, box_w, box_h)
        positions["M103"] = QRectF(615.0, 672.0, box_w, box_h)
        return positions

    def draw_connectors(self, painter: QPainter, positions: dict[str, QRectF]) -> None:
        painter.setPen(QPen(QColor(185, 215, 255, 145), 2))
        pairs = [
            ("M74", "M77", "M89"), ("M73", "M75", "M90"), ("M83", "M84", "M93"), ("M81", "M82", "M94"),
            ("M76", "M78", "M91"), ("M79", "M80", "M92"), ("M86", "M88", "M95"), ("M85", "M87", "M96"),
            ("M89", "M90", "M97"), ("M93", "M94", "M98"), ("M91", "M92", "M99"), ("M95", "M96", "M100"),
            ("M97", "M98", "M101"), ("M99", "M100", "M102"),
        ]
        for first, second, target in pairs:
            self.draw_pair_connector(painter, positions[first], positions[second], positions[target])
        self.draw_final_connector(painter, positions["M101"], positions["M102"], positions["M104"])
        self.draw_final_connector(painter, positions["M101"], positions["M102"], positions["M103"], dashed=True)

    def draw_pair_connector(self, painter: QPainter, first: QRectF, second: QRectF, target: QRectF) -> None:
        left_side = target.center().x() > first.center().x()
        if left_side:
            x1 = first.right(); x2 = target.left(); x_mid = (x1 + x2) / 2.0
            painter.drawLine(int(x1), int(first.center().y()), int(x_mid), int(first.center().y()))
            painter.drawLine(int(x1), int(second.center().y()), int(x_mid), int(second.center().y()))
            painter.drawLine(int(x_mid), int(first.center().y()), int(x_mid), int(second.center().y()))
            painter.drawLine(int(x_mid), int(target.center().y()), int(x2), int(target.center().y()))
        else:
            x1 = first.left(); x2 = target.right(); x_mid = (x1 + x2) / 2.0
            painter.drawLine(int(x1), int(first.center().y()), int(x_mid), int(first.center().y()))
            painter.drawLine(int(x1), int(second.center().y()), int(x_mid), int(second.center().y()))
            painter.drawLine(int(x_mid), int(first.center().y()), int(x_mid), int(second.center().y()))
            painter.drawLine(int(x_mid), int(target.center().y()), int(x2), int(target.center().y()))

    def draw_final_connector(self, painter: QPainter, left: QRectF, right: QRectF, target: QRectF, dashed: bool = False) -> None:
        pen = QPen(QColor(255, 255, 255, 110), 2)
        if dashed:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(left.right()), int(left.center().y()), int(target.left()), int(target.center().y()))
        painter.drawLine(int(right.left()), int(right.center().y()), int(target.right()), int(target.center().y()))

    def draw_matches(self, painter: QPainter, positions: dict[str, QRectF]) -> None:
        draw_order = [
            *BRACKET_LEFT_R32, *BRACKET_LEFT_R16, *BRACKET_LEFT_QF, *BRACKET_LEFT_SF,
            *BRACKET_RIGHT_R32, *BRACKET_RIGHT_R16, *BRACKET_RIGHT_QF, *BRACKET_RIGHT_SF,
            "M104", "M103",
        ]
        for match_id in draw_order:
            self.draw_match_box(painter, positions[match_id], match_id)

    def draw_centerpiece(self, painter: QPainter, width: float, height: float) -> None:
        del height
        trophy_file = find_asset_file("Winners_trophy.jpg")
        if trophy_file.exists():
            pixmap = QPixmap(str(trophy_file))
            if not pixmap.isNull():
                painter.setOpacity(0.9)
                painter.drawPixmap(QRectF(width / 2 - 38, 114, 76, 98).toRect(), pixmap)
                painter.setOpacity(1.0)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        champion = self.simulator.champion if self.simulator else None
        center_text = f"Champion: {champion}" if champion else "Champion: —"
        painter.drawText(QRectF(width / 2 - 180, 216, 360, 24), Qt.AlignCenter, center_text)
        painter.setPen(QColor("#9fb7d8"))
        painter.drawText(QRectF(width / 2 - 130, 646, 260, 20), Qt.AlignCenter, "Third-place match")

    def draw_match_box(self, painter: QPainter, rect: QRectF, match_id: str) -> None:
        result = self.simulator.match_results.get(match_id) if self.simulator else None
        home, away = self.match_teams(match_id)
        finished = result is not None
        winner = result.winner if result else None

        border = QColor("#a8ff00") if finished else QColor("#1ed5a5")
        fill = QColor(8, 18, 35, 236) if finished else QColor(247, 249, 255, 238)
        painter.setPen(QPen(border, 1.6))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 8, 8)

        header_rect = QRectF(rect.left() + 5, rect.top() + 1, rect.width() - 10, 10)
        painter.setPen(QColor("#ff2c6d") if finished else QColor("#143a6d"))
        painter.setFont(QFont("Segoe UI", 5, QFont.Bold))
        painter.drawText(header_rect, Qt.AlignCenter, self.match_label(match_id))

        row_h = (rect.height() - 13) / 2.0
        row1 = QRectF(rect.left() + 5, rect.top() + 12, rect.width() - 10, row_h)
        row2 = QRectF(rect.left() + 5, rect.top() + 12 + row_h, rect.width() - 10, row_h)
        self.draw_team_row(painter, row1, home, result, True, winner == home, finished)
        self.draw_team_row(painter, row2, away, result, False, winner == away, finished)

    def draw_team_row(self, painter: QPainter, rect: QRectF, team: str, result: MatchResult | None, is_home: bool, is_winner: bool, finished: bool) -> None:
        if finished:
            row_color = QColor(11, 58, 42, 200) if is_winner else QColor(18, 30, 52, 180)
            text_color = QColor("#ffffff") if is_winner else QColor("#c9d6e8")
        else:
            row_color = QColor(255, 255, 255, 0)
            text_color = QColor("#07101d")
        painter.setPen(Qt.NoPen)
        painter.setBrush(row_color)
        painter.drawRoundedRect(rect, 4, 4)

        flag_rect = QRectF(rect.left() + 2, rect.top() + 2, 16, rect.height() - 4)
        self.draw_flag(painter, flag_rect, team)

        score_text = self.score_text(result, is_home)
        score_rect = QRectF(rect.right() - 41, rect.top(), 40, rect.height())
        painter.setPen(QColor("#ffd34d") if is_winner else text_color)
        painter.setFont(QFont("Segoe UI", 7, QFont.Black))
        painter.drawText(score_rect, Qt.AlignRight | Qt.AlignVCenter, score_text)

        name_rect = QRectF(rect.left() + 21, rect.top(), rect.width() - 64, rect.height())
        painter.setPen(text_color)
        painter.setFont(QFont("Segoe UI", 6, QFont.Bold))
        display_name = self.compact_team_name(team)
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, display_name)

    def compact_team_name(self, team: str) -> str:
        if not team:
            return "TBD"
        if team.startswith(("Winner", "Loser")):
            return team.replace("Winner ", "W ").replace("Loser ", "L ")
        if team.startswith("3rd slot"):
            return team.replace("3rd slot ", "3rd ")
        if len(team) <= 13:
            return team
        return f"{team[:10].rstrip()}..."

    def draw_flag(self, painter: QPainter, rect: QRectF, team: str) -> None:
        if team and not team.startswith(("Winner", "Loser", "TBD", "1", "2", "3")):
            path = flag_path(team)
            if path.exists():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    painter.drawPixmap(rect.toRect(), pixmap)
                    return
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI Emoji", 7))
            painter.drawText(rect, Qt.AlignCenter, flag_emoji(team))
            return
        painter.setPen(QColor("#9fb7d8"))
        painter.setBrush(QColor(255, 255, 255, 55))
        painter.drawRoundedRect(rect, 3, 3)

    def score_text(self, result: MatchResult | None, is_home: bool) -> str:
        if result is None:
            return "-"
        goals = result.home_goals if is_home else result.away_goals
        if result.penalties_home is not None and result.penalties_away is not None:
            penalties = result.penalties_home if is_home else result.penalties_away
            return f"{goals} ({penalties})"
        return str(goals)

    def penalty_text(self, result: MatchResult | None, is_home: bool) -> str:
        del result, is_home
        return ""

    def match_label(self, match_id: str) -> str:
        if match_id == "M104":
            return "FINAL · M104"
        if match_id == "M103":
            return "3RD · M103"
        if match_id in BRACKET_LEFT_SF + BRACKET_RIGHT_SF:
            return f"SF · {match_id}"
        if match_id in BRACKET_LEFT_QF + BRACKET_RIGHT_QF:
            return f"QF · {match_id}"
        if match_id in BRACKET_LEFT_R16 + BRACKET_RIGHT_R16:
            return f"R16 · {match_id}"
        return f"R32 · {match_id}"

    def match_teams(self, match_id: str) -> tuple[str, str]:
        if self.simulator and match_id in self.simulator.match_results:
            result = self.simulator.match_results[match_id]
            return result.home, result.away

        if self.simulator and self.simulator.round32_matches:
            for known_id, home, away in self.simulator.round32_matches:
                if known_id == match_id:
                    return home, away

        if match_id in ROUND32_SLOTS:
            return self.slot_label(ROUND32_SLOTS[match_id][0]), self.slot_label(ROUND32_SLOTS[match_id][1])

        dependency = MATCH_DEPENDENCIES.get(match_id)
        if dependency:
            return self.dependency_label(dependency[0]), self.dependency_label(dependency[1])
        return "TBD", "TBD"

    def dependency_label(self, dependency: str) -> str:
        if dependency.startswith("L"):
            return f"Loser M{dependency[1:]}"
        if self.simulator and dependency in self.simulator.match_results:
            result = self.simulator.match_results[dependency]
            return result.winner or f"Winner {dependency}"
        return f"Winner {dependency}"

    def slot_label(self, slot: str) -> str:
        if slot.startswith("3:"):
            return f"3rd slot {slot.split(':', 1)[1]}"
        if len(slot) == 2 and slot[0] in {"1", "2"}:
            return f"{slot[0]}{slot[1]}"
        return slot


class PodiumWidget(QWidget):
    """Custom painted final podium with flags, country names and trophy."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.simulator: WorldCupSimulator | None = None
        self.setMinimumSize(920, 520)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(1180, 720)

    def set_simulator(self, simulator: WorldCupSimulator | None) -> None:
        self.simulator = simulator
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        base_w = 1180.0
        base_h = 720.0
        scale = min(self.width() / base_w, self.height() / base_h)
        x_offset = (self.width() - base_w * scale) / 2.0
        y_offset = (self.height() - base_h * scale) / 2.0
        painter.translate(x_offset, y_offset)
        painter.scale(scale, scale)

        self.draw_background(painter, base_w, base_h)
        self.draw_title(painter, base_w)
        champion, runner_up, third_place = self.simulator.podium if self.simulator else (None, None, None)

        baseline = 650.0
        self.draw_trophy(painter, base_w, champion)
        self.draw_podium_place(painter, QRectF(158, baseline - 230, 255, 230), "2", runner_up, "RUNNER-UP", QColor("#b8c3d1"))
        self.draw_podium_place(painter, QRectF(458, baseline - 315, 265, 315), "1", champion, "WINNER", QColor("#ffd34d"), winner=True)
        self.draw_podium_place(painter, QRectF(768, baseline - 185, 235, 185), "3", third_place, "THIRD PLACE", QColor("#df9b5a"))

        if champion:
            painter.setPen(QColor("#a8ff00"))
            painter.setFont(QFont("Segoe UI", 18, QFont.Black))
            painter.drawText(QRectF(0, 664, base_w, 36), Qt.AlignCenter, f"CONGRATULATIONS, {champion.upper()}!")
        else:
            painter.setPen(QColor("#9fb7d8"))
            painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
            painter.drawText(QRectF(0, 664, base_w, 36), Qt.AlignCenter, "Run the tournament to reveal the final podium.")

    def draw_background(self, painter: QPainter, width: float, height: float) -> None:
        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0.0, QColor("#0c2d5f"))
        gradient.setColorAt(0.45, QColor("#06142c"))
        gradient.setColorAt(1.0, QColor("#020714"))
        painter.fillRect(QRectF(0, 0, width, height), gradient)
        painter.setPen(QPen(QColor(255, 255, 255, 28), 2))
        for x in [120, 280, 900, 1060]:
            painter.drawLine(int(x), 115, int(x + 90), 650)
        painter.setPen(QPen(QColor("#1ed5a5"), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(18, 18, width - 36, height - 36), 28, 28)

    def draw_title(self, painter: QPainter, width: float) -> None:
        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 32, QFont.Black)
        font.setItalic(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 26, width, 48), Qt.AlignCenter, "WORLD CUP 2026 PODIUM")
        painter.setPen(QPen(QColor("#ff2c6d"), 7))
        painter.drawLine(315, 82, 865, 82)

    def draw_trophy(self, painter: QPainter, width: float, champion: str | None) -> None:
        trophy_file = find_asset_file("Winners_trophy.jpg")
        trophy_rect = QRectF(width / 2 - 80, 106, 160, 150)
        if trophy_file.exists():
            pixmap = QPixmap(str(trophy_file))
            if not pixmap.isNull():
                painter.setOpacity(0.96)
                painter.drawPixmap(trophy_rect.toRect(), pixmap)
                painter.setOpacity(1.0)
                painter.setPen(QPen(QColor("#ffd34d"), 1.5))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(trophy_rect.adjusted(-3, -3, 3, 3), 10, 10)
                return
        painter.setPen(QColor("#ffd34d"))
        painter.setFont(QFont("Segoe UI Emoji", 64))
        painter.drawText(trophy_rect, Qt.AlignCenter, "🏆")

    def draw_podium_place(
        self,
        painter: QPainter,
        rect: QRectF,
        number: str,
        team: str | None,
        title: str,
        accent: QColor,
        winner: bool = False,
    ) -> None:
        team_text = team.upper() if team else "—"
        flag_y = rect.top() - (76 if winner else 68)
        flag_rect = QRectF(rect.center().x() - 42, flag_y, 84, 48)
        name_rect = QRectF(rect.left() - 22, flag_y + 52, rect.width() + 44, 34)

        painter.setPen(QPen(accent, 2.0))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawRoundedRect(flag_rect, 8, 8)
        if team:
            self.draw_flag(painter, flag_rect.adjusted(8, 7, -8, -7), team)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 13 if winner else 11, QFont.Black))
        painter.drawText(name_rect, Qt.AlignCenter | Qt.TextWordWrap, self.compact_country_name(team_text, 18 if winner else 16))

        pod_gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        pod_gradient.setColorAt(0.0, accent.lighter(130))
        pod_gradient.setColorAt(0.55, QColor("#111923"))
        pod_gradient.setColorAt(1.0, QColor("#050912"))
        painter.setPen(QPen(accent, 2.8 if winner else 2.2))
        painter.setBrush(pod_gradient)
        painter.drawRoundedRect(rect, 18, 18)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 54 if winner else 46, QFont.Black))
        painter.drawText(QRectF(rect.left(), rect.top() + 18, rect.width(), 72), Qt.AlignCenter, number)

        painter.setPen(accent)
        painter.setFont(QFont("Segoe UI", 16 if winner else 13, QFont.Black))
        painter.drawText(QRectF(rect.left(), rect.top() + rect.height() * 0.48, rect.width(), 32), Qt.AlignCenter, title)

        painter.setPen(QColor("#dbe8ff"))
        painter.setFont(QFont("Segoe UI", 13 if winner else 11, QFont.Bold))
        painter.drawText(QRectF(rect.left() + 10, rect.bottom() - 72, rect.width() - 20, 52), Qt.AlignCenter | Qt.TextWordWrap, self.compact_country_name(team_text, 20))

    def compact_country_name(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return f"{text[:max_chars - 3].rstrip()}..."

    def draw_flag(self, painter: QPainter, rect: QRectF, team: str) -> None:
        path = flag_path(team)
        if path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                painter.drawPixmap(rect.toRect(), pixmap)
                return
        painter.setPen(QColor("#07101d"))
        painter.setFont(QFont("Segoe UI Emoji", 22))
        painter.drawText(rect, Qt.AlignCenter, flag_emoji(team))


class WorldCupWindow(QMainWindow):
    def __init__(
        self,
        mode: str = "Tournament",
        seed: int = 2026,
        minutes: float = 10.0,
        selected_team: str | None = None,
        difficulty: str = "Normal",
        user_name: str = "Player 1",
        guess_players: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.initial_seed = seed
        self.initial_minutes = minutes
        self.selected_team = selected_team
        self.difficulty = difficulty
        self.user_name = user_name or "Player 1"
        self.guess_players = guess_players or []
        self.manual_match_window: InteractiveMatchWindow | None = None
        self.tournament_history_saved = False
        self.guess_history_saved = False
        self.setWindowTitle(f"RPGsoccer World Cup 2026 Simulator · {mode} · {GUI_VERSION}")
        self.resize(1440, 920)

        self.simulator: WorldCupSimulator | None = None
        self.running = False
        self.paused = False
        self.step_delay_ms = 650
        self.autosave_file = SAVED_GAMES_DIR / "autosave.rpgsave"
        self.group_page = 0
        self.last_seed_warning_shown = False

        self.timer = QTimer(self)
        self.timer.setInterval(self.step_delay_ms)
        self.timer.timeout.connect(self.play_next_step)

        self.build_ui()
        self.seed_spin.setValue(self.initial_seed)
        self.minutes_spin.setValue(self.initial_minutes)
        self.apply_style()
        self.new_tournament(confirm=False)

    def build_ui(self) -> None:
        root = QWidget()
        main = QVBoxLayout(root)
        main.setContentsMargins(14, 14, 14, 14)
        main.setSpacing(10)

        main.addLayout(self.build_header())
        main.addLayout(self.build_controls())

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_live_tab(), "Live match")
        self.tabs.addTab(self.build_groups_tab(), "Groups")
        self.tabs.addTab(self.build_thirds_tab(), "Thirds")
        self.tabs.addTab(self.build_knockout_tab(), "Knockout")
        self.tabs.addTab(self.build_podium_tab(), "Podium")
        main.addWidget(self.tabs, 1)

        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("StatusLabel")
        main.addWidget(self.status_label)

        self.setCentralWidget(root)

    def build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(16)

        logo_file = find_asset_file("worldcup_2026_logo.svg", "mundial-2026-world-cup_logo.svg")
        if QSvgWidget is not None and logo_file.exists():
            logo = QSvgWidget(str(logo_file))
            logo.setFixedSize(210, 90)
            layout.addWidget(logo)
        else:
            label = QLabel("FIFA WORLD CUP 2026")
            label.setObjectName("BigTitle")
            label.setFixedWidth(280)
            layout.addWidget(label)

        title_box = QVBoxLayout()
        title = QLabel(f"RPGsoccer World Cup 2026 · {GUI_VERSION}")
        title.setObjectName("BigTitle")
        selected_text = ""
        if self.selected_team:
            role = "Podium game" if self.mode == "Guess the Winner" else "User team"
            selected_text = f" · {role}: {flag_emoji(self.selected_team)} {self.selected_team}"
        extra = f" · Difficulty: {self.difficulty}" if self.mode == "Tournament" else ""
        subtitle = QLabel(f"{self.mode}{selected_text}{extra} · Random RPGsoccer match engine · group stage · best thirds · knockout bracket · save/load")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, 1)
        return layout

    def build_controls(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999999)
        self.seed_spin.setValue(2026)
        self.seed_spin.setPrefix("Seed ")
        self.seed_spin.setToolTip("Generated automatically. Previous saved-game seeds are not reused.")
        self.seed_spin.setEnabled(False)
        self.seed_spin.setVisible(False)

        self.minutes_spin = QDoubleSpinBox()
        self.minutes_spin.setRange(1.0, 90.0)
        self.minutes_spin.setDecimals(1)
        self.minutes_spin.setValue(10.0)
        self.minutes_spin.setSuffix(" min")
        self.minutes_spin.setToolTip("RPGsoccer match duration. 10 minutes is recommended for GUI tests.")

        self.new_button = QPushButton("New tournament")
        self.run_button = QPushButton("Run")
        self.pause_button = QPushButton("Pause")
        self.save_button = QPushButton("Save")
        self.load_button = QPushButton("Load")

        self.new_button.clicked.connect(lambda: self.new_random_tournament(confirm=True))
        self.run_button.clicked.connect(self.run_tournament)
        self.pause_button.clicked.connect(self.pause_tournament)
        self.save_button.clicked.connect(self.save_game)
        self.load_button.clicked.connect(self.load_game)
        self.seed_spin.valueChanged.connect(self.on_seed_or_minutes_changed)
        self.minutes_spin.valueChanged.connect(self.on_seed_or_minutes_changed)

        for widget in [self.minutes_spin, self.new_button, self.run_button, self.pause_button, self.save_button, self.load_button]:
            layout.addWidget(widget)

        self.seed_state_label = QLabel("Random seed hidden")
        self.seed_state_label.setObjectName("StatusLabel")
        self.seed_state_label.setMinimumWidth(320)
        layout.addWidget(self.seed_state_label)
        layout.addStretch(1)
        return layout

    def build_live_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal)

        games_box = QGroupBox("Games M1-M104")
        games_layout = QVBoxLayout(games_box)
        games_layout.setContentsMargins(8, 14, 8, 8)
        self.games_table = QTableWidget(0, 4)
        headers = ["#", "Round", "Match", "Result"]
        self.games_table.setHorizontalHeaderLabels(headers)
        self.games_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.games_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.games_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.games_table.verticalHeader().setVisible(False)
        self.games_table.verticalHeader().setDefaultSectionSize(28)
        self.games_table.itemSelectionChanged.connect(self.on_game_selection_changed)
        games_layout.addWidget(self.games_table, 1)
        splitter.addWidget(games_box)

        report_box = QGroupBox("Match report")
        report_layout = QVBoxLayout(report_box)
        report_layout.setContentsMargins(8, 14, 8, 8)
        self.current_match_label = QLabel("No match played yet.")
        self.current_match_label.setObjectName("SectionTitle")
        self.current_score_label = QLabel("—")
        self.current_score_label.setObjectName("ScoreLabel")
        report_layout.addWidget(self.current_match_label)
        report_layout.addWidget(self.current_score_label)

        self.guess_panel = QGroupBox("Guess the Podium")
        guess_layout = QVBoxLayout(self.guess_panel)
        self.guess_summary_label = QLabel("Podium predictions will be scored when the tournament finishes.")
        self.guess_summary_label.setObjectName("Subtitle")
        self.guess_table = QTableWidget(0, 5)
        self.guess_table.setHorizontalHeaderLabels(["User", "1st", "2nd", "3rd", "Points"])
        self.guess_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        guess_layout.addWidget(self.guess_summary_label)
        guess_layout.addWidget(self.guess_table)
        report_layout.addWidget(self.guess_panel)
        self.guess_panel.setVisible(self.mode == "Guess the Winner")

        self.match_detail = QTextEdit()
        self.match_detail.setReadOnly(True)
        self.match_detail.setLineWrapMode(QTextEdit.NoWrap)
        self.live_log = self.match_detail
        report_layout.addWidget(self.match_detail, 1)
        splitter.addWidget(report_box)
        splitter.setSizes([520, 860])

        layout.addWidget(splitter, 1)

        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)
        filter_label = QLabel("Filters:")
        filter_label.setObjectName("Subtitle")
        self.round_filter_combo = QComboBox()
        self.country_filter_combo = QComboBox()
        self.clear_filters_button = QPushButton("Clear filters")
        self.round_filter_combo.currentIndexChanged.connect(self.refresh_game_list)
        self.country_filter_combo.currentIndexChanged.connect(self.refresh_game_list)
        self.clear_filters_button.clicked.connect(self.clear_live_filters)
        filter_bar.addWidget(filter_label)
        filter_bar.addWidget(self.round_filter_combo)
        filter_bar.addWidget(self.country_filter_combo)
        filter_bar.addWidget(self.clear_filters_button)
        filter_bar.addStretch(1)
        layout.addLayout(filter_bar)

        self.populate_live_filters()
        self.selected_game_display_id: str | None = None
        self.current_live_display_id: str | None = None
        return tab

    def populate_live_filters(self) -> None:
        self.round_filter_combo.blockSignals(True)
        self.country_filter_combo.blockSignals(True)
        self.round_filter_combo.clear()
        self.country_filter_combo.clear()
        for label in [
            "All rounds",
            "Group stage",
            *[f"Group {group}" for group in GROUPS],
            "Round of 32",
            "Round of 16",
            "Quarter-finals",
            "Semi-finals",
            "Third-place match",
            "Final",
        ]:
            self.round_filter_combo.addItem(label)
        self.country_filter_combo.addItem("All countries")
        for team in self.all_teams():
            self.country_filter_combo.addItem(f"{flag_emoji(team)} {team}", team)
        if self.selected_team:
            selected_index = self.country_filter_combo.findData(self.selected_team)
            if selected_index >= 0:
                self.country_filter_combo.setCurrentIndex(selected_index)
        self.round_filter_combo.blockSignals(False)
        self.country_filter_combo.blockSignals(False)

    def clear_live_filters(self) -> None:
        self.round_filter_combo.setCurrentIndex(0)
        self.country_filter_combo.setCurrentIndex(0)
        self.refresh_game_list()

    def all_teams(self) -> list[str]:
        teams: list[str] = []
        for group_teams in GROUPS.values():
            teams.extend(group_teams)
        return sorted(teams)

    def group_display_id_to_engine_id(self, display_number: int) -> tuple[str, str, str, str, str]:
        group_index = (display_number - 1) // len(GROUP_MATCH_PAIRINGS)
        game_index = (display_number - 1) % len(GROUP_MATCH_PAIRINGS)
        group = list(GROUPS)[group_index]
        teams = GROUPS[group]
        home_idx, away_idx = GROUP_MATCH_PAIRINGS[game_index]
        return (
            f"M{display_number}",
            f"{group}{game_index + 1}",
            f"Group {group}",
            teams[home_idx],
            teams[away_idx],
        )

    def knockout_stage_name(self, match_id: str) -> str:
        number = int(match_id[1:])
        if 73 <= number <= 88:
            return "Round of 32"
        if 89 <= number <= 96:
            return "Round of 16"
        if 97 <= number <= 100:
            return "Quarter-finals"
        if number in {101, 102}:
            return "Semi-finals"
        if number == 103:
            return "Third-place match"
        if number == 104:
            return "Final"
        return "Knockout"

    def game_entries(self) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for display_number in range(1, 73):
            display_id, engine_id, stage, home, away = self.group_display_id_to_engine_id(display_number)
            entries.append({"display_id": display_id, "engine_id": engine_id, "stage": stage, "home": home, "away": away})

        for number in range(73, 105):
            match_id = f"M{number}"
            home, away = self.resolve_match_teams(match_id)
            entries.append({"display_id": match_id, "engine_id": match_id, "stage": self.knockout_stage_name(match_id), "home": home, "away": away})
        return entries

    def resolve_match_teams(self, match_id: str) -> tuple[str, str]:
        if hasattr(self, "knockout_bracket"):
            return self.knockout_bracket.match_teams(match_id)
        if match_id in ROUND32_SLOTS:
            return ROUND32_SLOTS[match_id]
        return "TBD", "TBD"

    def selected_round_filter(self) -> str:
        return self.round_filter_combo.currentText() if hasattr(self, "round_filter_combo") else "All rounds"

    def selected_country_filter(self) -> str | None:
        if not hasattr(self, "country_filter_combo"):
            return None
        return self.country_filter_combo.currentData()

    def filtered_game_entries(self) -> list[dict[str, str]]:
        round_filter = self.selected_round_filter()
        country_filter = self.selected_country_filter()
        filtered: list[dict[str, str]] = []
        for entry in self.game_entries():
            if round_filter != "All rounds":
                if round_filter == "Group stage":
                    if not entry["stage"].startswith("Group "):
                        continue
                elif entry["stage"] != round_filter:
                    continue
            if country_filter:
                if country_filter not in {entry["home"], entry["away"]}:
                    continue
            filtered.append(entry)
        return filtered

    def refresh_game_list(self, *args) -> None:
        if not hasattr(self, "games_table"):
            return
        entries = self.filtered_game_entries()
        previous = self.selected_game_display_id or self.current_live_display_id
        self.games_table.blockSignals(True)
        self.games_table.setRowCount(len(entries))
        self.game_row_entries = entries
        selected_row = -1
        for row, entry in enumerate(entries):
            result = self.match_result_for_entry(entry)
            result_text = self.short_result_text(result)
            match_text = f"{flag_emoji(entry['home'])} {entry['home']} vs {flag_emoji(entry['away'])} {entry['away']}"
            values = [entry["display_id"], entry["stage"], match_text, result_text]
            is_selected_team_match = self.selected_team in {entry["home"], entry["away"]} if self.selected_team else False
            for col, value in enumerate(values):
                align = Qt.AlignLeft | Qt.AlignVCenter if col in {1, 2} else Qt.AlignCenter
                item = self.apply_item_contrast(self.table_item(value, align), row)
                if is_selected_team_match:
                    item.setBackground(QBrush(QColor("#173d19")))
                    item.setForeground(QBrush(QColor("#f7ffe6")))
                self.games_table.setItem(row, col, item)
            if entry["display_id"] == previous:
                selected_row = row
        self.games_table.setColumnWidth(0, 56)
        self.games_table.setColumnWidth(1, 132)
        self.games_table.setColumnWidth(2, 260)
        if self.mode == "Guess the Winner":
            self.games_table.setColumnWidth(4, 120)
        self.games_table.horizontalHeader().setStretchLastSection(True)
        if selected_row >= 0:
            self.games_table.selectRow(selected_row)
        self.games_table.blockSignals(False)

    def match_result_for_entry(self, entry: dict[str, str]) -> MatchResult | None:
        if self.simulator is None:
            return None
        return self.simulator.match_results.get(entry["engine_id"])

    def short_result_text(self, result: MatchResult | None) -> str:
        if result is None:
            return "—"
        text = f"{result.home_goals}-{result.away_goals}"
        if result.penalties_home is not None and result.penalties_away is not None:
            text += f" ({result.penalties_home}-{result.penalties_away} pens)"
        return text

    def on_game_selection_changed(self) -> None:
        if self.running:
            return
        rows = self.games_table.selectionModel().selectedRows() if hasattr(self, "games_table") else []
        if not rows:
            return
        row = rows[0].row()
        if row < 0 or row >= len(getattr(self, "game_row_entries", [])):
            return
        entry = self.game_row_entries[row]
        self.selected_game_display_id = entry["display_id"]
        self.show_game_detail(entry)

    def select_game_in_list(self, display_id: str) -> None:
        if not hasattr(self, "games_table"):
            return
        self.selected_game_display_id = display_id
        for row, entry in enumerate(getattr(self, "game_row_entries", [])):
            if entry["display_id"] == display_id:
                self.games_table.blockSignals(True)
                self.games_table.selectRow(row)
                self.games_table.blockSignals(False)
                return

    def display_id_for_result(self, result: MatchResult) -> str:
        if result.match_id and len(result.match_id) >= 2 and result.match_id[0] in GROUPS:
            group_index = list(GROUPS).index(result.match_id[0])
            game_no = int(result.match_id[1:])
            return f"M{group_index * len(GROUP_MATCH_PAIRINGS) + game_no}"
        return result.match_id

    def entry_for_result(self, result: MatchResult) -> dict[str, str]:
        return {
            "display_id": self.display_id_for_result(result),
            "engine_id": result.match_id,
            "stage": result.stage,
            "home": result.home,
            "away": result.away,
        }

    def show_game_detail(self, entry: dict[str, str]) -> None:
        result = self.match_result_for_entry(entry)
        if result is None:
            self.current_match_label.setText(f"{entry['stage']} · {entry['display_id']} · pending")
            self.current_score_label.setText(f"{flag_emoji(entry['home'])} {entry['home']} vs {flag_emoji(entry['away'])} {entry['away']}")
            self.match_detail.setPlainText(
                f"{entry['display_id']} · {entry['stage']}\n"
                f"{entry['home']} vs {entry['away']}\n\n"
                "This match has not been played yet. Press Run to continue the simulation."
            )
            return
        self.show_match_detail(result, entry["display_id"])

    def show_match_detail(self, result: MatchResult, display_id: str | None = None) -> None:
        display_id = display_id or self.display_id_for_result(result)
        header = [
            f"{result.stage} · {display_id}",
            f"{flag_emoji(result.home)} {result.home} {result.home_goals} - {result.away_goals} {flag_emoji(result.away)} {result.away}",
        ]
        if result.penalties_home is not None and result.penalties_away is not None:
            header.append(f"Penalties: {result.penalties_home} - {result.penalties_away}")
        if result.winner:
            header.append(f"Winner: {flag_emoji(result.winner)} {result.winner}")
        text = "\n".join(header) + "\n" + "=" * 96 + "\n" + "\n".join(result.log_lines)
        self.match_detail.setPlainText(text)
        self.match_detail.verticalScrollBar().setValue(0)

    def build_groups_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        version_banner = QLabel("GROUPS VIEW · 6 groups per page · 3 columns × 2 rows")
        version_banner.setObjectName("SectionTitle")
        version_banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_banner)

        header = QLabel(
            "Live group classifications. Use the arrows to switch between Groups A-F and Groups G-L. "
            "Each table is expanded to show all four teams without internal scrolling."
        )
        header.setObjectName("Subtitle")
        header.setWordWrap(True)
        layout.addWidget(header)

        page_controls = QHBoxLayout()
        page_controls.setSpacing(12)
        self.group_prev_button = QPushButton("<")
        self.group_next_button = QPushButton(">")
        self.group_prev_button.setFixedWidth(54)
        self.group_next_button.setFixedWidth(54)
        self.group_page_label = QLabel("Groups A-F")
        self.group_page_label.setObjectName("SectionTitle")
        self.group_page_label.setAlignment(Qt.AlignCenter)
        self.group_prev_button.clicked.connect(self.show_previous_group_page)
        self.group_next_button.clicked.connect(self.show_next_group_page)
        page_controls.addWidget(self.group_prev_button)
        page_controls.addWidget(self.group_page_label, 1)
        page_controls.addWidget(self.group_next_button)
        layout.addLayout(page_controls)

        self.group_page_boxes: list[QGroupBox] = []
        self.group_page_tables: list[QTableWidget] = []

        grid_container = QWidget()
        grid = QGridLayout(grid_container)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        for slot in range(6):
            group_box = QGroupBox("Group")
            group_layout = QVBoxLayout(group_box)
            group_layout.setContentsMargins(8, 14, 8, 8)
            group_layout.setSpacing(4)

            table = QTableWidget(4, 11)
            table.setHorizontalHeaderLabels(["#", "", "Team", "Pts", "P", "W", "D", "L", "GF", "GA", "GD"])
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setSelectionMode(QAbstractItemView.NoSelection)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(29)
            table.setAlternatingRowColors(False)
            table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.setStyleSheet(
                "QTableWidget { background-color: #050912; color: #eaf2ff; } "
                "QTableWidget::item { background-color: #050912; color: #eaf2ff; } "
                "QTableWidget::item:selected { background-color: #1e5596; color: #ffffff; }"
            )
            table.setMinimumHeight(176)
            table.setMaximumHeight(190)
            table.setMinimumWidth(420)

            self.group_page_boxes.append(group_box)
            self.group_page_tables.append(table)

            group_layout.addWidget(table)
            grid.addWidget(group_box, slot // 3, slot % 3)

        layout.addWidget(grid_container, 1)
        return tab

    def visible_group_names(self) -> list[str]:
        group_names = list(GROUPS)
        start = self.group_page * 6
        return group_names[start:start + 6]

    def show_previous_group_page(self) -> None:
        self.group_page = max(0, self.group_page - 1)
        self.refresh_groups()

    def show_next_group_page(self) -> None:
        max_page = (len(GROUPS) - 1) // 6
        self.group_page = min(max_page, self.group_page + 1)
        self.refresh_groups()

    def update_group_page_controls(self) -> None:
        if not hasattr(self, "group_page_label"):
            return
        visible = self.visible_group_names()
        first = visible[0]
        last = visible[-1]
        self.group_page_label.setText(f"Groups {first}-{last}")
        max_page = (len(GROUPS) - 1) // 6
        self.group_prev_button.setEnabled(self.group_page > 0)
        self.group_next_button.setEnabled(self.group_page < max_page)

    def build_thirds_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.thirds_table = QTableWidget(12, 12)
        self.thirds_table.setHorizontalHeaderLabels(["#", "Flag", "Team", "Group", "Status", "Pts", "P", "W", "D", "L", "GF", "GD"])
        self.thirds_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.thirds_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.thirds_table, 1)
        return tab

    def build_knockout_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        banner = QLabel("KNOCKOUT VIEW · compact bracket · flags · goals (penalties)")
        banner.setObjectName("SectionTitle")
        banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(banner)

        self.knockout_bracket = KnockoutBracketWidget()
        layout.addWidget(self.knockout_bracket, 1)
        return tab

    def build_podium_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        self.podium_widget = PodiumWidget()
        layout.addWidget(self.podium_widget, 1)
        return tab

    def apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #07101d; color: #f4f7fb; font-family: Segoe UI, Arial; }
            QPushButton { background: #143a6d; border: 1px solid #2d6fb8; padding: 7px 14px; border-radius: 8px; font-weight: 600; }
            QPushButton:hover { background: #1e5596; }
            QPushButton:pressed { background: #0f2d54; }
            QPushButton[active="true"] { border: 3px solid #ff9700; background: #23190a; color: #ffffff; }
            QSpinBox, QDoubleSpinBox, QComboBox { background: #0d1b2e; border: 1px solid #2d6fb8; border-radius: 6px; padding: 5px; }
            QTabWidget::pane { border: 1px solid #233a5e; border-radius: 8px; }
            QTabBar::tab { background: #0d1b2e; padding: 8px 16px; border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QTabBar::tab:selected { background: #1e5596; }
            QTextEdit, QTableWidget { background: #050912; color: #eaf2ff; border: 1px solid #233a5e; border-radius: 8px; gridline-color: #233a5e; alternate-background-color: #0d1b2e; }
            QTableWidget::item { color: #eaf2ff; padding: 2px; }
            QTableWidget::item:alternate { background: #0d1b2e; color: #eaf2ff; }
            QTableWidget::item:selected { background: #1e5596; color: #ffffff; }
            QHeaderView::section { background: #143a6d; color: #ffffff; padding: 5px; border: 0px; }
            QGroupBox { border: 1px solid #233a5e; border-radius: 8px; margin-top: 12px; padding: 12px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
            #BigTitle { font-size: 30px; font-weight: 900; }
            #Subtitle { color: #9fb7d8; font-size: 14px; }
            #SectionTitle { font-size: 18px; font-weight: 700; }
            #ScoreLabel { font-size: 24px; font-weight: 900; color: #a8ff00; }
            #StatusLabel { color: #9fb7d8; }
            #ChampionLabel { font-size: 26px; font-weight: 900; color: #ffd34d; }
            #PodiumLabel { font-size: 20px; font-weight: 700; }
            #CongratsLabel { font-size: 18px; color: #a8ff00; }
            """
        )

    def set_button_active(self, button: QPushButton, active: bool) -> None:
        button.setProperty("active", "true" if active else "false")
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

    def update_run_pause_button_styles(self) -> None:
        if not hasattr(self, "run_button") or not hasattr(self, "pause_button"):
            return
        self.set_button_active(self.run_button, self.running and not self.paused)
        self.set_button_active(self.pause_button, self.paused and not self.running)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.refresh_images()
        self.update_seed_state_label()

    def refresh_images(self) -> None:
        groups_file = find_asset_file("image_groups_WC2026.jpg")
        trophy_file = find_asset_file("Winners_trophy.jpg")
        if groups_file.exists() and hasattr(self, "groups_image"):
            pixmap = QPixmap(str(groups_file))
            if not pixmap.isNull():
                self.groups_image.setPixmap(pixmap.scaled(self.groups_image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if trophy_file.exists() and hasattr(self, "trophy_label"):
            pixmap = QPixmap(str(trophy_file))
            if not pixmap.isNull():
                self.trophy_label.setPixmap(pixmap.scaled(self.trophy_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def current_seed_value(self) -> int:
        return int(self.seed_spin.value())

    def current_minutes_value(self) -> float:
        return float(self.minutes_spin.value())

    def settings_pending(self) -> bool:
        if self.simulator is None:
            return True
        if self.simulator.seed != self.current_seed_value():
            return True
        if abs(float(self.simulator.minutes) - self.current_minutes_value()) > 1.0e-9:
            return True
        return False


    def sync_mode_state_from_simulator(self) -> None:
        if self.simulator is None:
            return
        self.selected_team = getattr(self.simulator, "selected_team", self.selected_team)
        self.difficulty = getattr(self.simulator, "difficulty", self.difficulty)
        self.user_name = getattr(self.simulator, "user_name", self.user_name)
        self.guess_players = getattr(self.simulator, "guess_players", self.guess_players)

    def set_controls_from_simulator(self) -> None:
        if self.simulator is None:
            return
        self.seed_spin.blockSignals(True)
        self.minutes_spin.blockSignals(True)
        try:
            if self.simulator.seed is not None:
                self.seed_spin.setValue(int(self.simulator.seed))
            self.minutes_spin.setValue(float(self.simulator.minutes))
        finally:
            self.seed_spin.blockSignals(False)
            self.minutes_spin.blockSignals(False)

    def on_seed_or_minutes_changed(self) -> None:
        self.update_seed_state_label()
        if self.simulator is None:
            self.status_label.setText(
                f"{GUI_VERSION} · Press Run or New tournament to create a tournament."
            )
            return
        if not self.settings_pending():
            return
        if self.simulator.match_results:
            self.status_label.setText(
                "Match duration changed. Press New tournament, or press Run and confirm a fresh tournament."
            )
        else:
            self.status_label.setText(
                "Match duration changed. Press Run to start a fresh tournament."
            )

    def update_seed_state_label(self) -> None:
        if not hasattr(self, "seed_state_label"):
            return
        control_minutes = self.current_minutes_value()
        if self.simulator is None:
            self.seed_state_label.setText(seed_status_text(control_minutes))
            return
        active_minutes = float(self.simulator.minutes)
        played = len(self.simulator.match_results)
        if self.settings_pending():
            self.seed_state_label.setText(f"Random seed hidden · Active {active_minutes:g} min · Pending {control_minutes:g} min")
        else:
            self.seed_state_label.setText(seed_status_text(active_minutes, played))


    def new_random_tournament(self, confirm: bool = True) -> None:
        self.seed_spin.blockSignals(True)
        try:
            self.seed_spin.setValue(generate_unique_seed())
        finally:
            self.seed_spin.blockSignals(False)
        self.new_tournament(confirm=confirm)

    def new_tournament(self, confirm: bool = True) -> None:
        if confirm and self.simulator and self.simulator.match_results:
            answer = QMessageBox.question(self, "New tournament", "Start a new tournament? Unsaved progress may be lost.")
            if answer != QMessageBox.Yes:
                return
        seed = int(self.seed_spin.value())
        minutes = float(self.minutes_spin.value())
        run_name = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        output_dir = RUNS_DIR / run_name
        self.simulator = WorldCupSimulator(output_dir=output_dir, seed=seed, minutes=minutes, print_to_console=False)
        setattr(self.simulator, "selected_team", self.selected_team)
        setattr(self.simulator, "difficulty", self.difficulty)
        setattr(self.simulator, "user_name", self.user_name)
        setattr(self.simulator, "guess_players", self.guess_players)
        self.tournament_history_saved = False
        self.guess_history_saved = False
        self.running = False
        self.paused = False
        self.timer.stop()
        self.update_run_pause_button_styles()
        self.live_log.clear()
        self.current_match_label.setText("New tournament ready.")
        if self.selected_team:
            role = "User team" if self.mode == "Tournament" else "Selected"
            self.current_score_label.setText(f"{role}: {flag_emoji(self.selected_team)} {self.selected_team}. Press Run to start.")
        else:
            self.current_score_label.setText("Press Run to start.")
        selected_info = f" · Selected team: {self.selected_team}" if self.selected_team else ""
        self.status_label.setText(f"{GUI_VERSION} · Random seed hidden{selected_info} · Output folder: {output_dir}")
        self.update_seed_state_label()
        self.refresh_all()

    def run_tournament(self) -> None:
        if self.simulator is None:
            self.new_tournament(confirm=False)
        elif self.settings_pending():
            if self.simulator.match_results:
                answer = QMessageBox.question(
                    self,
                    "Seed or minutes changed",
                    "The match duration no longer matches the active tournament.\n\n"
                    "Start a fresh tournament with the current duration?",
                )
                if answer != QMessageBox.Yes:
                    self.update_seed_state_label()
                    return
            self.new_tournament(confirm=False)

        if self.simulator and self.simulator.is_complete:
            if self.settings_pending():
                self.new_tournament(confirm=False)
            else:
                QMessageBox.information(self, "Tournament completed", f"Champion: {self.simulator.champion}")
                return

        show_group_intro = self.simulator is not None and not self.simulator.match_results
        self.running = True
        self.paused = False
        self.update_run_pause_button_styles()
        if self.simulator:
            self.status_label.setText(
                "Running with hidden random seed. Pause will take effect after the current match has finished."
            )
        self.update_seed_state_label()

        if show_group_intro:
            self.show_group_stage_intro(start_after=True)
            return

        self.start_timer_if_needed()

    def start_timer_if_needed(self) -> None:
        if self.running and not self.timer.isActive():
            self.timer.start()

    def show_group_stage_intro(self, start_after: bool = False) -> None:
        groups_file = find_asset_file("image_groups_WC2026.jpg")

        dialog = QDialog(self)
        dialog.setWindowTitle("World Cup 2026 group stage")
        dialog.setModal(True)
        dialog.setMinimumWidth(720)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("The group stage is ready")
        title.setObjectName("BigTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(str(groups_file))
        if not pixmap.isNull():
            image_label.setPixmap(pixmap.scaled(QSize(760, 620), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(image_label, 1)

        message = QLabel("The simulation will start automatically in 5 seconds.")
        message.setObjectName("Subtitle")
        message.setAlignment(Qt.AlignCenter)
        layout.addWidget(message)

        def finish_intro() -> None:
            dialog.accept()
            if start_after:
                self.start_timer_if_needed()

        QTimer.singleShot(5000, finish_intro)
        dialog.show()

    def pause_tournament(self) -> None:
        self.paused = True
        self.running = False
        self.timer.stop()
        self.update_run_pause_button_styles()
        self.status_label.setText("Paused after the last completed match.")
        self.update_seed_state_label()

    def save_game(self) -> None:
        if self.simulator is None:
            return
        SAVED_GAMES_DIR.mkdir(parents=True, exist_ok=True)
        default_name = SAVED_GAMES_DIR / datetime.now().strftime("worldcup_2026_%Y%m%d_%H%M%S.rpgsave")
        filename, _ = QFileDialog.getSaveFileName(self, "Save tournament", str(default_name), "RPGsoccer save (*.rpgsave)")
        if not filename:
            return
        self.simulator.save_game(filename)
        self.status_label.setText(f"Saved game: {filename}")
        self.update_seed_state_label()

    def load_game(self) -> None:
        SAVED_GAMES_DIR.mkdir(parents=True, exist_ok=True)
        filename, _ = QFileDialog.getOpenFileName(self, "Load tournament", str(SAVED_GAMES_DIR), "RPGsoccer save (*.rpgsave)")
        if not filename:
            return
        try:
            self.simulator = WorldCupSimulator.load_game(filename)
            self.sync_mode_state_from_simulator()
            self.set_controls_from_simulator()
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return
        self.running = False
        self.paused = True
        self.timer.stop()
        self.update_run_pause_button_styles()
        self.live_log.clear()
        self.live_log.append(f"Loaded game: {filename}")
        self.current_match_label.setText("Saved tournament loaded.")
        self.current_score_label.setText(f"Matches played: {len(self.simulator.match_results)}")
        self.status_label.setText(f"Loaded game: {filename}")
        self.update_seed_state_label()
        self.refresh_all()


    def guess_store(self) -> dict[str, str]:
        if self.simulator is None:
            return {}
        if not hasattr(self.simulator, "guesses") or getattr(self.simulator, "guesses") is None:
            setattr(self.simulator, "guesses", {})
        return getattr(self.simulator, "guesses")

    def guess_label_for_entry(self, entry: dict[str, str]) -> str:
        guess = self.guess_store().get(entry["engine_id"], "")
        if guess == "1":
            return entry["home"]
        if guess == "X":
            return "Draw"
        if guess == "2":
            return entry["away"]
        return "—"

    def guess_summary(self) -> tuple[int, int]:
        correct = 0
        total = 0
        for match_id, guess in self.guess_store().items():
            result = self.simulator.match_results.get(match_id) if self.simulator else None
            if result is None:
                continue
            total += 1
            actual = "1" if result.home_goals > result.away_goals else "2" if result.home_goals < result.away_goals else "X"
            if guess == actual:
                correct += 1
        return correct, total

    def next_match_for_guess(self) -> dict[str, str] | None:
        if self.simulator is None:
            return None
        if self.simulator.thirds_ranking and not self.simulator.round32_matches:
            try:
                self.simulator.build_round32()
            except Exception:
                pass
        teams = set(all_teams())
        for entry in self.game_entries():
            if entry["engine_id"] in self.simulator.match_results:
                continue
            if entry["home"] in teams and entry["away"] in teams:
                return entry
        return None

    def record_guess(self, guess: str) -> None:
        if self.simulator is None:
            return
        entry = self.next_match_for_guess()
        if entry is None:
            QMessageBox.information(self, "No match", "There is no pending match ready for a prediction yet.")
            return
        store = self.guess_store()
        if entry["engine_id"] in store:
            return
        store[entry["engine_id"]] = guess
        label = self.guess_label_for_entry(entry)
        self.status_label.setText(f"Prediction saved for {entry['display_id']}: {label}.")
        self.paused = False
        self.refresh_all()

    def refresh_guess_panel(self) -> None:
        if not hasattr(self, "guess_panel"):
            return
        guessing = self.mode == "Guess the Winner"
        self.guess_panel.setVisible(guessing)
        if not guessing:
            return
        results = self.guess_results()
        self.guess_table.setRowCount(len(results))
        for row_idx, row in enumerate(results):
            values = [
                row.get("name", ""),
                row.get("first", ""),
                row.get("second", ""),
                row.get("third", ""),
                row.get("points", 0),
            ]
            for col_idx, value in enumerate(values):
                item = self.apply_item_contrast(self.table_item(value, Qt.AlignLeft | Qt.AlignVCenter if col_idx in {0, 1, 2, 3} else Qt.AlignCenter), row_idx)
                self.guess_table.setItem(row_idx, col_idx, item)
        self.guess_table.resizeColumnsToContents()
        self.guess_table.horizontalHeader().setStretchLastSection(True)
        if self.simulator and self.simulator.is_complete:
            champion, runner_up, third = self.simulator.podium
            self.guess_summary_label.setText(
                f"Final podium: 1st {champion or '—'} · 2nd {runner_up or '—'} · 3rd {third or '—'}. Points saved in History."
            )
        else:
            self.guess_summary_label.setText("Podium predictions are ready. Press Run to simulate the tournament.")



    def next_user_playable_match(self) -> dict[str, str] | None:
        if self.simulator is None or not self.selected_team:
            return None
        if self.simulator.thirds_ranking and not self.simulator.round32_matches:
            try:
                self.simulator.build_round32()
            except Exception:
                pass
        teams = set(all_teams())
        for entry in self.game_entries():
            if entry["engine_id"] in self.simulator.match_results:
                continue
            if entry["home"] not in teams or entry["away"] not in teams:
                continue
            if self.selected_team in {entry["home"], entry["away"]}:
                return entry
            return None
        return None

    def open_user_tournament_match(self, entry: dict[str, str]) -> None:
        if self.simulator is None or self.selected_team is None:
            return
        self.status_label.setText(
            f"User match ready: {entry['display_id']} · {entry['home']} vs {entry['away']}. "
            "Play it in RPGsoccer mode; then press Run to continue."
        )
        self.tabs.setCurrentIndex(0)
        knockout = not entry["stage"].startswith("Group ")
        self.manual_match_window = InteractiveMatchWindow(
            entry["home"],
            entry["away"],
            self,
            user_team=self.selected_team,
            difficulty=self.difficulty,
            knockout=knockout,
            stage=entry["stage"],
            match_id=entry["engine_id"],
            seed=None,
            minutes=float(self.simulator.minutes),
            result_callback=self.record_manual_tournament_result,
        )
        self.manual_match_window.show()

    def record_manual_tournament_result(self, result: MatchResult) -> None:
        if self.simulator is None:
            return
        try:
            self.simulator.record_external_result(result)
        except Exception as exc:
            QMessageBox.critical(self, "Manual match error", str(exc))
            return
        self.show_match(result)
        self.refresh_all()
        self.paused = True
        self.running = False
        self.update_run_pause_button_styles()
        if self.simulator.is_complete:
            self.save_mode_history_if_needed()
            self.tabs.setCurrentWidget(self.tabs.widget(4))
            self.status_label.setText(f"Tournament completed. Champion: {self.simulator.champion}")
        else:
            self.status_label.setText("User match saved in the current tournament state. Press Save to keep it, or Run to continue.")

    def score_guess_player(self, player: dict[str, str]) -> int:
        if self.simulator is None:
            return 0
        champion, runner_up, third_place = self.simulator.podium
        status = self.simulator.final_status_map()
        exact = [("first", champion), ("second", runner_up), ("third", third_place)]
        points = 0
        weighted = {"Winner": 20, "Runner-up": 15, "Third": 10, "Fourth": 5, "QF": 3, "R16": 2, "R32": 1}
        for key, exact_team in exact:
            team = player.get(key, "")
            if team and team == exact_team:
                points += 25
            else:
                points += weighted.get(status.get(team, ""), 0)
        return points

    def guess_results(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for player in self.guess_players:
            row = dict(player)
            row["points"] = self.score_guess_player(player) if self.simulator and self.simulator.is_complete else 0
            rows.append(row)
        return sorted(rows, key=lambda row: int(row.get("points", 0)), reverse=True)

    def save_mode_history_if_needed(self) -> None:
        if self.simulator is None or not self.simulator.is_complete:
            return
        if self.mode == "Tournament" and self.selected_team and not self.tournament_history_saved:
            status = self.simulator.final_status_map().get(self.selected_team, "Unknown")
            add_history("tournament", {
                "user": self.user_name,
                "team": self.selected_team,
                "final_position": status,
                "difficulty": self.difficulty,
                "seed": self.simulator.seed,
            })
            self.tournament_history_saved = True
        if self.mode == "Guess the Winner" and not self.guess_history_saved:
            for row in self.guess_results():
                guess = f"1st {row.get('first')} / 2nd {row.get('second')} / 3rd {row.get('third')}"
                add_history("guess_the_winner", {
                    "user": row.get("name", "Player"),
                    "points": row.get("points", 0),
                    "guess": guess,
                    "seed": self.simulator.seed,
                })
            self.guess_history_saved = True
            self.refresh_guess_panel()

    def play_next_step(self) -> None:
        if self.simulator is None or self.paused or not self.running:
            self.timer.stop()
            return
        if self.mode == "Tournament":
            playable = self.next_user_playable_match()
            if playable is not None:
                self.timer.stop()
                self.running = False
                self.paused = True
                self.update_run_pause_button_styles()
                self.show_game_detail(playable)
                self.open_user_tournament_match(playable)
                return
        try:
            step = self.simulator.next_step()
        except Exception as exc:
            self.timer.stop()
            self.running = False
            self.update_run_pause_button_styles()
            QMessageBox.critical(self, "Simulation error", str(exc))
            return

        if step.result is not None:
            self.show_match(step.result)
        else:
            self.live_log.append(f"\n{step.message}")
            self.current_match_label.setText(step.stage or step.kind.title())
            self.current_score_label.setText(step.message)

        self.refresh_all()
        # Manual Save button controls saved progress; no automatic post-match save is made.

        if step.completed or self.simulator.is_complete:
            self.timer.stop()
            self.running = False
            self.paused = False
            self.update_run_pause_button_styles()
            champion = self.simulator.champion
            self.status_label.setText(f"Tournament completed. Champion: {champion}")
            self.update_seed_state_label()
            self.tabs.setCurrentWidget(self.tabs.widget(4))
            self.save_mode_history_if_needed()

    def autosave(self) -> None:
        if self.simulator is None:
            return
        try:
            SAVED_GAMES_DIR.mkdir(parents=True, exist_ok=True)
            self.simulator.save_game(self.autosave_file)
        except Exception:
            pass

    def show_match(self, result: MatchResult) -> None:
        display_id = self.display_id_for_result(result)
        self.current_live_display_id = display_id
        self.current_match_label.setText(
            f"{result.stage} · {display_id} · {self.flag_text(result.home)} {result.home} vs {self.flag_text(result.away)} {result.away}"
        )
        score = result.scoreline()
        if result.winner:
            score += f" · Winner: {self.flag_text(result.winner)} {result.winner}"
        self.current_score_label.setText(score)
        self.refresh_game_list()
        self.select_game_in_list(display_id)
        self.show_match_detail(result, display_id)

    def refresh_all(self) -> None:
        self.refresh_game_list()
        self.refresh_groups()
        self.refresh_thirds()
        self.refresh_knockout()
        self.refresh_podium()
        self.refresh_images()
        self.refresh_guess_panel()
        self.update_seed_state_label()

    def flag_text(self, team: str) -> str:
        return flag_emoji(team)

    def flag_item(self, team: str) -> QTableWidgetItem:
        item = QTableWidgetItem(flag_emoji(team))
        path = flag_path(team)
        if path.exists():
            item.setIcon(QIcon(str(path)))
            item.setText("")
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def table_item(self, text: object, align: Qt.AlignmentFlag = Qt.AlignCenter) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(align)
        return item

    def apply_item_contrast(self, item: QTableWidgetItem, row: int) -> QTableWidgetItem:
        """Force readable colors in every cell, independently of the OS theme."""
        background = QColor("#050912") if row % 2 == 0 else QColor("#0d1b2e")
        item.setBackground(QBrush(background))
        item.setForeground(QBrush(QColor("#eaf2ff")))
        return item

    def group_stats_for_display(self, group: str) -> list[TeamStats]:
        if self.simulator and group in self.simulator.group_stats:
            stats = list(self.simulator.group_stats[group].values())
        else:
            stats = [TeamStats(name=team, group=group) for team in GROUPS[group]]
        ranked, _ = rank_stats(stats, None, random_tiebreak=False)
        return ranked

    def refresh_groups(self) -> None:
        if not hasattr(self, "group_page_tables"):
            return
        self.update_group_page_controls()
        visible_groups = self.visible_group_names()
        for slot, table in enumerate(self.group_page_tables):
            if slot >= len(visible_groups):
                table.clearContents()
                self.group_page_boxes[slot].setTitle("Group")
                continue

            group = visible_groups[slot]
            self.group_page_boxes[slot].setTitle(f"Group {group}")
            ranked = self.group_stats_for_display(group)
            table.setRowCount(len(ranked))
            table.clearContents()

            for row, team in enumerate(ranked):
                values = [
                    row + 1,
                    None,
                    team.name,
                    team.points,
                    team.played,
                    team.wins,
                    team.draws,
                    team.losses,
                    team.goals_for,
                    team.goals_against,
                    team.goal_difference,
                ]
                table.setRowHeight(row, 29)
                for col, value in enumerate(values):
                    if col == 1:
                        item = self.flag_item(team.name)
                    elif col == 2:
                        item = self.table_item(value, Qt.AlignLeft | Qt.AlignVCenter)
                    else:
                        item = self.table_item(value)
                    table.setItem(row, col, self.apply_item_contrast(item, row))

            table.setColumnWidth(0, 28)
            table.setColumnWidth(1, 34)
            table.setColumnWidth(2, 134)
            for col in range(3, 11):
                table.setColumnWidth(col, 34)
            table.horizontalHeader().setStretchLastSection(True)

    def refresh_thirds(self) -> None:
        if not hasattr(self, "thirds_table"):
            return
        rows: list[TeamStats] = []
        qualified = set()
        if self.simulator and self.simulator.thirds_ranking:
            rows = list(self.simulator.thirds_ranking)
            qualified = {team.name for team in self.simulator.thirds_qualified}
        elif self.simulator and self.simulator.group_rankings:
            rows = [ranking[2] for ranking in self.simulator.group_rankings.values() if len(ranking) >= 3]
            rows, _ = rank_stats(rows, None, random_tiebreak=False)
        self.thirds_table.setRowCount(max(12, len(rows)))
        for row in range(self.thirds_table.rowCount()):
            if row >= len(rows):
                for col in range(self.thirds_table.columnCount()):
                    self.thirds_table.setItem(row, col, self.apply_item_contrast(QTableWidgetItem(""), row))
                continue
            team = rows[row]
            status = "QUALIFIED" if team.name in qualified else "—"
            values = [row + 1, None, team.name, team.group, status, team.points, team.played, team.wins, team.draws, team.losses, team.goals_for, team.goal_difference]
            for col, value in enumerate(values):
                if col == 1:
                    item = self.flag_item(team.name)
                elif col == 2:
                    item = self.table_item(value, Qt.AlignLeft | Qt.AlignVCenter)
                else:
                    item = self.table_item(value)
                self.thirds_table.setItem(row, col, self.apply_item_contrast(item, row))
        self.thirds_table.resizeColumnsToContents()
        self.thirds_table.horizontalHeader().setStretchLastSection(True)

    def refresh_knockout(self) -> None:
        if hasattr(self, "knockout_bracket"):
            self.knockout_bracket.set_simulator(self.simulator)

    def match_line(self, match_id: str, home: str, away: str) -> str:
        result = self.simulator.match_results.get(match_id) if self.simulator else None
        if result:
            return self.result_line(result)
        return f"{match_id}: {flag_emoji(home)} {home} vs {flag_emoji(away)} {away}"

    def result_line(self, result: MatchResult) -> str:
        text = f"{result.match_id}: {flag_emoji(result.home)} {result.home} {result.home_goals} - {result.away_goals} {flag_emoji(result.away)} {result.away}"
        if result.penalties_home is not None and result.penalties_away is not None:
            text += f" | Penalties {result.penalties_home}-{result.penalties_away}"
        if result.winner:
            text += f" | Winner: {flag_emoji(result.winner)} {result.winner}"
        return text

    def refresh_podium(self) -> None:
        if hasattr(self, "podium_widget"):
            self.podium_widget.set_simulator(self.simulator)



def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("RPGsoccer World Cup 2026")
    window = WorldCupWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
