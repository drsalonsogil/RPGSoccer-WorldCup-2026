"""World Cup 2026 tournament layer for the automatic RPGsoccer engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import pickle
import random
import re
from typing import Dict, Iterable, List, Optional, Sequence

from match_engine import MatchResult, simulate_match
from worldcup_2026_data import (
    FINAL,
    GROUP_MATCH_PAIRINGS,
    GROUPS,
    QUARTER_FINALS,
    ROUND32_MATCHES,
    ROUND_OF_16,
    SEMI_FINALS,
    THIRD_PLACE_MATCH,
    allocate_third_place_groups,
)


@dataclass
class TeamStats:
    name: str
    group: str
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    tie_notes: List[str] = field(default_factory=list)

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    def ranking_key(self) -> tuple[int, int, int, int]:
        return (self.points, self.goal_difference, self.goals_for, -self.goals_against)

    def row(self, position: int) -> str:
        return (
            f"{position:>2}. {self.name:<28} "
            f"PJ {self.played:>2}  G {self.wins:>2}  E {self.draws:>2}  P {self.losses:>2}  "
            f"GF {self.goals_for:>2}  GC {self.goals_against:>2}  DG {self.goal_difference:>3}  Pts {self.points:>2}"
        )


@dataclass
class StepResult:
    kind: str
    message: str
    stage: str = ""
    match_id: str = ""
    result: Optional[MatchResult] = None
    completed: bool = False


def slugify(text: str) -> str:
    text = text.strip().replace(" ", "_")
    text = re.sub(r"[^A-Za-z0-9_\-]", "", text)
    return text or "team"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def result_file_text(result: MatchResult) -> str:
    lines = [
        f"Stage: {result.stage}",
        f"Match: {result.match_id}",
        f"Home: {result.home}",
        f"Away: {result.away}",
        f"Score: {result.home_goals} - {result.away_goals}",
        f"Quiniela: {'1' if result.home_goals > result.away_goals else '2' if result.home_goals < result.away_goals else 'X'}",
    ]
    if result.penalties_home is not None and result.penalties_away is not None:
        lines.append(f"Penalties: {result.penalties_home} - {result.penalties_away}")
    if result.winner:
        lines.append(f"Winner: {result.winner}")
    if result.loser:
        lines.append(f"Loser: {result.loser}")
    return "\n".join(lines) + "\n"


def update_stats(stats: Dict[str, TeamStats], result: MatchResult) -> None:
    home = stats[result.home]
    away = stats[result.away]
    home.played += 1
    away.played += 1
    home.goals_for += result.home_goals
    home.goals_against += result.away_goals
    away.goals_for += result.away_goals
    away.goals_against += result.home_goals

    if result.home_goals > result.away_goals:
        home.wins += 1
        away.losses += 1
        home.points += 3
    elif result.home_goals < result.away_goals:
        away.wins += 1
        home.losses += 1
        away.points += 3
    else:
        home.draws += 1
        away.draws += 1
        home.points += 1
        away.points += 1


def rank_stats(
    stats: Sequence[TeamStats],
    rng: random.Random | None = None,
    random_tiebreak: bool = True,
) -> tuple[List[TeamStats], List[str]]:
    by_key: Dict[tuple[int, int, int, int], List[TeamStats]] = {}
    for item in stats:
        by_key.setdefault(item.ranking_key(), []).append(item)

    ordered_keys = sorted(by_key.keys(), reverse=True)
    ordered: List[TeamStats] = []
    notes: List[str] = []
    for key in ordered_keys:
        tied = list(by_key[key])
        if len(tied) == 1:
            ordered.extend(tied)
            continue
        if random_tiebreak:
            if rng is None:
                raise ValueError("random_tiebreak=True requires an rng")
            rng.shuffle(tied)
            names = ", ".join(team.name for team in tied)
            notes.append(
                "Empate total tras puntos, diferencia de goles, goles a favor y goles en contra: "
                f"{names}. Orden decidido por moneda/lotería."
            )
        else:
            tied.sort(key=lambda team: team.name)
        ordered.extend(tied)
    return ordered, notes


def group_table_text(group: str, ordered: Sequence[TeamStats], notes: Sequence[str]) -> str:
    lines = [
        f"Group {group} full classification",
        "Criteria used here: points, goal difference, goals for, fewer goals against, then random coin toss.",
        "",
    ]
    for idx, team in enumerate(ordered, 1):
        lines.append(team.row(idx))
    if notes:
        lines.append("")
        lines.append("Tie decisions:")
        lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines) + "\n"


class WorldCupSimulator:
    def __init__(
        self,
        output_dir: str | Path = "worldcup_2026_simulation",
        seed: int | None = None,
        minutes: float = 10.0,
        print_to_console: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.seed = seed
        self.rng = random.Random(seed)
        self.minutes = minutes
        self.print_to_console = print_to_console
        self.group_stats: Dict[str, Dict[str, TeamStats]] = {}
        self.group_rankings: Dict[str, List[TeamStats]] = {}
        self.group_tie_notes: Dict[str, List[str]] = {}
        self.thirds_ranking: List[TeamStats] = []
        self.thirds_qualified: List[TeamStats] = []
        self.thirds_eliminated: List[TeamStats] = []
        self.third_assignment: Dict[str, str] = {}
        self.third_assignment_method: str = ""
        self.round32_matches: List[tuple[str, str, str]] = []
        self.match_results: Dict[str, MatchResult] = {}
        self.summary_lines: List[str] = []

    @property
    def is_complete(self) -> bool:
        return "M104" in self.match_results

    @property
    def champion(self) -> Optional[str]:
        result = self.match_results.get("M104")
        return result.winner if result else None

    @property
    def podium(self) -> tuple[Optional[str], Optional[str], Optional[str]]:
        final = self.match_results.get("M104")
        third = self.match_results.get("M103")
        champion = final.winner if final else None
        runner_up = final.loser if final else None
        third_place = third.winner if third else None
        return champion, runner_up, third_place

    def log_summary(self, text: str) -> None:
        self.summary_lines.append(text)
        if self.print_to_console:
            print(text)

    def save_game(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            pickle.dump(self, handle, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load_game(cls, path: str | Path) -> "WorldCupSimulator":
        with Path(path).open("rb") as handle:
            simulator = pickle.load(handle)
        if not isinstance(simulator, cls):
            raise TypeError("The selected file is not a WorldCupSimulator saved game.")
        return simulator

    def _group_dir(self, group: str) -> Path:
        return self.output_dir / f"group{group}"

    def _ensure_group_stats(self, group: str) -> Dict[str, TeamStats]:
        if group not in self.group_stats:
            self.group_stats[group] = {team: TeamStats(name=team, group=group) for team in GROUPS[group]}
        return self.group_stats[group]

    def _write_group_table(self, group: str, final: bool) -> None:
        stats = self._ensure_group_stats(group)
        if final:
            ordered, notes = rank_stats(list(stats.values()), self.rng, random_tiebreak=True)
            self.group_rankings[group] = ordered
            self.group_tie_notes[group] = notes
        else:
            ordered, notes = rank_stats(list(stats.values()), None, random_tiebreak=False)
        write_text(self._group_dir(group) / "full_class.txt", group_table_text(group, ordered, notes))

    def _all_group_matches_are_done(self, group: str) -> bool:
        return all(f"{group}{game_no}" in self.match_results for game_no in range(1, len(GROUP_MATCH_PAIRINGS) + 1))

    def _all_groups_are_ranked(self) -> bool:
        return all(group in self.group_rankings for group in GROUPS)

    def _play_group_match(self, group: str, game_no: int, home: str, away: str) -> MatchResult:
        group_dir = self._group_dir(group)
        base = f"{slugify(home)}_{slugify(away)}"
        game_file = group_dir / f"{base}_game.txt"
        result_file = group_dir / f"{base}_result.txt"
        match_id = f"{group}{game_no}"
        result = simulate_match(
            home,
            away,
            minutes=self.minutes,
            knockout=False,
            rng=self.rng,
            print_to_console=self.print_to_console,
            output_path=game_file,
            stage=f"Group {group}",
            match_id=match_id,
        )
        update_stats(self._ensure_group_stats(group), result)
        write_text(result_file, result_file_text(result))
        self.match_results[match_id] = result
        self._write_group_table(group, final=self._all_group_matches_are_done(group))
        self.log_summary(result.scoreline())
        return result

    def _next_group_step(self) -> Optional[StepResult]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for group, teams in GROUPS.items():
            self._ensure_group_stats(group)
            for game_no, (home_idx, away_idx) in enumerate(GROUP_MATCH_PAIRINGS, 1):
                match_id = f"{group}{game_no}"
                if match_id in self.match_results:
                    continue
                home = teams[home_idx]
                away = teams[away_idx]
                self.log_summary(f"\n=== Group {group} | Match {game_no} ===")
                result = self._play_group_match(group, game_no, home, away)
                return StepResult(
                    kind="match",
                    stage=f"Group {group}",
                    match_id=match_id,
                    result=result,
                    message=result.scoreline(),
                )
            if self._all_group_matches_are_done(group) and group not in self.group_rankings:
                self._write_group_table(group, final=True)
                return StepResult(kind="classification", stage=f"Group {group}", message=f"Group {group} classification completed.")
        return None

    def write_thirds_classification(self) -> None:
        thirds = [ranking[2] for ranking in self.group_rankings.values()]
        ordered, notes = rank_stats(thirds, self.rng, random_tiebreak=True)
        self.thirds_ranking = ordered
        self.thirds_qualified = ordered[:8]
        self.thirds_eliminated = ordered[8:]

        lines = [
            "Third-place classification",
            "Criteria used here: points, goal difference, goals for, fewer goals against, then random coin toss.",
            "The top eight third-placed teams qualify for the round of 32.",
            "",
        ]
        for idx, team in enumerate(ordered, 1):
            status = "QUALIFIED" if idx <= 8 else "ELIMINATED"
            lines.append(f"{team.row(idx)}  [{team.group}3 | {status}]")
        if notes:
            lines.append("")
            lines.append("Tie decisions:")
            lines.extend(f"- {note}" for note in notes)
        text = "\n".join(lines) + "\n"
        write_text(self.output_dir / "class_thirds.txt", text)
        write_text(self.output_dir / "thirds" / "class_thirds.txt", text)

    def slot_to_team(self, slot: str, third_assignment: Dict[str, str]) -> str:
        if slot.startswith("1") or slot.startswith("2"):
            position = int(slot[0]) - 1
            group = slot[1]
            return self.group_rankings[group][position].name
        if slot.startswith("3:"):
            winner_slot = slot.split(":", 1)[1]
            group = third_assignment[winner_slot]
            return self.group_rankings[group][2].name
        raise ValueError(f"Unknown slot: {slot}")

    def build_round32(self) -> List[tuple[str, str, str]]:
        if self.round32_matches:
            return list(self.round32_matches)

        qualified_groups = [team.group for team in self.thirds_qualified]
        ranked_groups = [team.group for team in self.thirds_ranking]
        assignment, assignment_method = allocate_third_place_groups(qualified_groups, ranked_groups)
        self.third_assignment = assignment
        self.third_assignment_method = assignment_method

        lines = [
            "Round of 32 bracket",
            f"Third-place assignment method: {assignment_method}",
            "",
            "Third-place slot assignment:",
        ]
        for slot, group in sorted(assignment.items()):
            lines.append(f"{slot} receives 3{group}: {self.group_rankings[group][2].name}")
        lines.append("")
        lines.append("Matches:")

        matches: List[tuple[str, str, str]] = []
        for item in ROUND32_MATCHES:
            match_id = item["id"]
            home = self.slot_to_team(item["home"], assignment)
            away = self.slot_to_team(item["away"], assignment)
            matches.append((match_id, home, away))
            lines.append(f"{match_id}: {home} vs {away}")

        self.round32_matches = matches
        write_text(self.output_dir / "round32_bracket.txt", "\n".join(lines) + "\n")
        return matches

    def _play_knockout_match(self, round_dir_name: str, stage_name: str, match_id: str, home: str, away: str) -> MatchResult:
        round_dir = self.output_dir / round_dir_name
        base = f"{match_id}_{slugify(home)}_{slugify(away)}"
        game_file = round_dir / f"{base}_game.txt"
        result_file = round_dir / f"{base}_result.txt"
        result = simulate_match(
            home,
            away,
            minutes=self.minutes,
            knockout=True,
            rng=self.rng,
            print_to_console=self.print_to_console,
            output_path=game_file,
            stage=stage_name,
            match_id=match_id,
        )
        write_text(result_file, result_file_text(result))
        self.match_results[match_id] = result
        self.log_summary(result.scoreline())
        return result

    def winners_from_pairs(self, definitions: Sequence[tuple[str, str, str]]) -> List[tuple[str, str, str]]:
        matches: List[tuple[str, str, str]] = []
        for match_id, previous_a, previous_b in definitions:
            home = self.match_results[previous_a].winner
            away = self.match_results[previous_b].winner
            if home is None or away is None:
                raise RuntimeError(f"Missing winner for {previous_a} or {previous_b}")
            matches.append((match_id, home, away))
        return matches

    def _next_from_matches(self, round_dir: str, stage_name: str, matches: Iterable[tuple[str, str, str]]) -> Optional[StepResult]:
        for match_id, home, away in matches:
            if match_id in self.match_results:
                continue
            self.log_summary(f"\n=== {stage_name} | {match_id} ===")
            result = self._play_knockout_match(round_dir, stage_name, match_id, home, away)
            return StepResult(kind="match", stage=stage_name, match_id=match_id, result=result, message=result.scoreline())
        return None

    def _next_knockout_step(self) -> Optional[StepResult]:
        step = self._next_from_matches("round32", "Round of 32", self.build_round32())
        if step:
            return step
        step = self._next_from_matches("round16", "Round of 16", self.winners_from_pairs(ROUND_OF_16))
        if step:
            return step
        step = self._next_from_matches("quarterfinals", "Quarter-finals", self.winners_from_pairs(QUARTER_FINALS))
        if step:
            return step
        step = self._next_from_matches("semifinals", "Semi-finals", self.winners_from_pairs(SEMI_FINALS))
        if step:
            return step

        third_id, _, _ = THIRD_PLACE_MATCH
        if third_id not in self.match_results:
            third_home = self.match_results["M101"].loser
            third_away = self.match_results["M102"].loser
            if third_home is None or third_away is None:
                raise RuntimeError("Missing semi-final losers for third-place match.")
            return self._next_from_matches("third_place", "Third-place match", [(third_id, third_home, third_away)])

        final_id, prev_a, prev_b = FINAL
        if final_id not in self.match_results:
            final_home = self.match_results[prev_a].winner
            final_away = self.match_results[prev_b].winner
            if final_home is None or final_away is None:
                raise RuntimeError("Missing finalists.")
            return self._next_from_matches("final", "Final", [(final_id, final_home, final_away)])
        return None

    def write_summary(self) -> None:
        champion, runner_up, third_place = self.podium
        lines = [
            "World Cup 2026 RPGsoccer simulation summary",
            f"Seed: {self.seed}",
            f"Champion: {champion}",
            f"Runner-up: {runner_up}",
            f"Third place: {third_place}",
            "",
            "All knockout results:",
        ]
        for match_id in [
            *[f"M{i}" for i in range(73, 89)],
            *[f"M{i}" for i in range(89, 97)],
            *[f"M{i}" for i in range(97, 101)],
            "M101",
            "M102",
            "M103",
            "M104",
        ]:
            result = self.match_results.get(match_id)
            if result:
                lines.append(f"{match_id}: {result.scoreline()} | Winner: {result.winner}")
        write_text(self.output_dir / "worldcup_summary.txt", "\n".join(lines) + "\n")


    def record_external_result(self, result: MatchResult) -> None:
        """Insert a result produced by the interactive GUI into the tournament.

        This keeps the tournament layer as the source of truth while allowing the
        selected user's matches to be played with the RPGsoccer non-simulated UI.
        """
        if not result.match_id:
            raise ValueError("Manual tournament results require a match_id.")
        if result.match_id in self.match_results:
            raise ValueError(f"Match {result.match_id} has already been played.")

        if result.match_id[0] in GROUPS:
            group = result.match_id[0]
            group_dir = self._group_dir(group)
            base = f"{slugify(result.home)}_{slugify(result.away)}"
            game_file = group_dir / f"{base}_game.txt"
            result_file = group_dir / f"{base}_result.txt"
            write_text(game_file, "\n".join(result.log_lines) + "\n")
            update_stats(self._ensure_group_stats(group), result)
            self.match_results[result.match_id] = result
            write_text(result_file, result_file_text(result))
            self._write_group_table(group, final=self._all_group_matches_are_done(group))
            self.log_summary(result.scoreline())
            return

        round_dir_name = self.round_dir_for_stage(result.stage, result.match_id)
        round_dir = self.output_dir / round_dir_name
        base = f"{result.match_id}_{slugify(result.home)}_{slugify(result.away)}"
        write_text(round_dir / f"{base}_game.txt", "\n".join(result.log_lines) + "\n")
        self.match_results[result.match_id] = result
        write_text(round_dir / f"{base}_result.txt", result_file_text(result))
        self.log_summary(result.scoreline())
        if result.match_id == "M104":
            self.write_summary()

    def round_dir_for_stage(self, stage: str, match_id: str) -> str:
        number = int(match_id[1:]) if match_id.startswith("M") and match_id[1:].isdigit() else 0
        if 73 <= number <= 88:
            return "round32"
        if 89 <= number <= 96:
            return "round16"
        if 97 <= number <= 100:
            return "quarterfinals"
        if number in {101, 102}:
            return "semifinals"
        if number == 103:
            return "third_place"
        if number == 104:
            return "final"
        return slugify(stage or "matches")

    def final_status_map(self) -> Dict[str, str]:
        """Return each team's final tournament status after enough matches exist."""
        status = {team: "Group stage" for teams in GROUPS.values() for team in teams}
        for number in range(73, 89):
            result = self.match_results.get(f"M{number}")
            if result:
                if result.winner:
                    status[result.winner] = "R16"
                if result.loser:
                    status[result.loser] = "R32"
        for number in range(89, 97):
            result = self.match_results.get(f"M{number}")
            if result:
                if result.winner:
                    status[result.winner] = "QF"
                if result.loser:
                    status[result.loser] = "R16"
        for number in range(97, 101):
            result = self.match_results.get(f"M{number}")
            if result:
                if result.winner:
                    status[result.winner] = "SF"
                if result.loser:
                    status[result.loser] = "QF"
        for number in range(101, 103):
            result = self.match_results.get(f"M{number}")
            if result:
                if result.winner:
                    status[result.winner] = "Final"
                if result.loser:
                    status[result.loser] = "Fourth"
        third = self.match_results.get("M103")
        if third:
            if third.winner:
                status[third.winner] = "Third"
            if third.loser:
                status[third.loser] = "Fourth"
        final = self.match_results.get("M104")
        if final:
            if final.winner:
                status[final.winner] = "Winner"
            if final.loser:
                status[final.loser] = "Runner-up"
        return status

    def next_step(self) -> StepResult:
        if self.is_complete:
            return StepResult(kind="finished", message=f"Tournament already completed. Champion: {self.champion}", completed=True)

        group_step = self._next_group_step()
        if group_step:
            return group_step

        if not self._all_groups_are_ranked():
            for group in GROUPS:
                if self._all_group_matches_are_done(group) and group not in self.group_rankings:
                    self._write_group_table(group, final=True)
                    return StepResult(kind="classification", stage=f"Group {group}", message=f"Group {group} classification completed.")

        if not self.thirds_ranking:
            self.write_thirds_classification()
            return StepResult(kind="thirds", stage="Third-place classification", message="Third-place classification completed.")

        knockout_step = self._next_knockout_step()
        if knockout_step:
            if knockout_step.match_id == "M104":
                self.write_summary()
                champion = self.champion
                self.log_summary(f"\nCampeón de la simulación: {champion}")
                knockout_step.completed = True
            return knockout_step

        self.write_summary()
        return StepResult(kind="finished", message=f"Tournament completed. Champion: {self.champion}", completed=True)

    def play_group_stage(self) -> None:
        while True:
            step = self._next_group_step()
            if step is None:
                break

    def play_knockout_matches(self, round_dir_name: str, stage_name: str, matches: Iterable[tuple[str, str, str]]) -> None:
        while True:
            step = self._next_from_matches(round_dir_name, stage_name, matches)
            if step is None:
                break

    def play_knockout_stage(self) -> None:
        while not self.is_complete:
            step = self._next_knockout_step()
            if step is None:
                break

    def run(self) -> str:
        while not self.is_complete:
            self.next_step()
        champion = self.champion
        if champion is None:
            raise RuntimeError("No champion produced.")
        return champion
