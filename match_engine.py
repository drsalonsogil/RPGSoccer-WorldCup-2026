"""Automatic RPGsoccer match engine with optional penalty shoot-outs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import random
from typing import List, Optional

from ai_random import choose_action, choose_defender, choose_formation, choose_receiver, penalty_outcome
from rpgsoccer_core import Balon, Crono, Dados, Marcador, criterio, generar, positions_from_formation, team_name


@dataclass
class MatchResult:
    home: str
    away: str
    home_goals: int
    away_goals: int
    winner: Optional[str] = None
    loser: Optional[str] = None
    penalties_home: Optional[int] = None
    penalties_away: Optional[int] = None
    stage: str = ""
    match_id: str = ""
    log_lines: List[str] = field(default_factory=list)

    @property
    def draw(self) -> bool:
        return self.home_goals == self.away_goals

    def scoreline(self) -> str:
        base = f"{self.home} {self.home_goals} - {self.away_goals} {self.away}"
        if self.penalties_home is not None and self.penalties_away is not None:
            base += f" | Penaltis: {self.penalties_home} - {self.penalties_away}"
        return base


class MatchLogger:
    def __init__(self, print_to_console: bool = True):
        self.lines: List[str] = []
        self.print_to_console = print_to_console

    def write(self, text: str = "") -> None:
        self.lines.append(text)
        if self.print_to_console:
            print(text)


def _change_possession(ball: Balon, attacking_team: int, attacker: int, defender: int) -> tuple[int, int, int]:
    ball.cambio_pos()
    return 1 - attacking_team, defender, attacker


def _reset_after_goal(ball: Balon, scoring_team: int) -> tuple[int, int, int]:
    next_team = 1 - scoring_team
    ball.equipo = next_team
    ball.gol = False
    ball.atacante = 1
    ball.defensor = 11
    return next_team, 1, 11


def _goal(scoring_team: int, score: Marcador, ball: Balon, logger: MatchLogger, home: str, away: str) -> tuple[int, int, int]:
    score.gol(scoring_team)
    logger.write(f"¡Gooool de {team_name(scoring_team, home, away)}!")
    logger.write(f"Marcador: {home} {score.local} - {score.visitante} {away}")
    return _reset_after_goal(ball, scoring_team)


def _resolve_direct_shot(
    attacking_team: int,
    attacker: int,
    teams: list[list],
    rng: random.Random,
    logger: MatchLogger,
    home: str,
    away: str,
    shot_skill: str = "chute",
    keeper_skill: str = "parada",
) -> bool:
    attacking_name = team_name(attacking_team, home, away)
    defending_team = 1 - attacking_team
    dado_at, combo_at = Dados(rng=rng).lanzar()
    dado_def, combo_def = Dados(rng=rng).lanzar()
    f_at = teams[attacking_team][attacker - 1].accion(shot_skill, dado_at)
    f_def = teams[defending_team][0].accion(keeper_skill, dado_def)
    logger.write(f"Chuta {attacking_name} y ...")
    logger.write(f"Dados ataque {dado_at}; dados portero {dado_def}.")
    if combo_at - combo_def > 0 or f_at - f_def > 0:
        logger.write("¡Gooool!")
        return True
    logger.write("¡El portero la paró!")
    return False


def _apply_consequence(
    fact: str,
    attacking_team: int,
    attacker: int,
    defender: int,
    score: Marcador,
    ball: Balon,
    positions: list[list[str]],
    teams: list[list],
    rng: random.Random,
    logger: MatchLogger,
    home: str,
    away: str,
    current_action: str,
) -> tuple[int, int, int, str]:
    if fact == "golrival":
        logger.write("¡El balón rebota en el rival y se convierte en una ocasión absurda!")
        rival_team = 1 - attacking_team
        rival_attacker = choose_receiver(positions[rival_team], "delantero", rng)
        if _resolve_direct_shot(rival_team, rival_attacker, teams, rng, logger, home, away, "chute", "reflejos"):
            return (*_goal(rival_team, score, ball, logger, home, away), "chute")
        ball.equipo = attacking_team
        ball.atacante = 1
        ball.defensor = 11
        return attacking_team, 1, 11, "chute"

    if fact == "gol":
        shooter = attacker
        if positions[attacking_team][shooter - 1] != "delantero":
            shooter = choose_receiver(positions[attacking_team], "delantero", rng)
        logger.write("La jugada deja una ocasión clarísima.")
        if _resolve_direct_shot(attacking_team, shooter, teams, rng, logger, home, away, "chute", "reflejos"):
            return (*_goal(attacking_team, score, ball, logger, home, away), "chute")
        ball.equipo = 1 - attacking_team
        ball.atacante = 1
        ball.defensor = 11
        return 1 - attacking_team, 1, 11, "chute"

    if fact == "pasedef":
        attacker = choose_receiver(positions[attacking_team], "defensa", rng)
        ball.cambio_at(attacker)
        logger.write(f"El pase llega al defensa #{attacker} de {team_name(attacking_team, home, away)}.")
        return attacking_team, attacker, defender, "pase"

    if fact == "pasemed":
        attacker = choose_receiver(positions[attacking_team], "medio", rng)
        ball.cambio_at(attacker)
        logger.write(f"El pase encuentra al medio #{attacker} de {team_name(attacking_team, home, away)}.")
        return attacking_team, attacker, defender, "pase"

    if fact == "pasedel":
        attacker = choose_receiver(positions[attacking_team], "delantero", rng)
        ball.cambio_at(attacker)
        logger.write(f"Balón al delantero #{attacker} de {team_name(attacking_team, home, away)}.")
        return attacking_team, attacker, defender, "pase largo"

    if fact == "robo":
        logger.write("Se produjo el robo, el balón cambia de equipo.")
        attacking_team, attacker, defender = _change_possession(ball, attacking_team, attacker, defender)
        return attacking_team, attacker, defender, current_action

    if fact == "delrival":
        logger.write("Jugada con mucho riesgo: el balón va al delantero rival.")
        attacking_team = 1 - attacking_team
        attacker = choose_receiver(positions[attacking_team], "delantero", rng)
        defender = choose_receiver(positions[1 - attacking_team], "defensa", rng)
        ball.equipo = attacking_team
        ball.atacante = attacker
        ball.defensor = defender
        return attacking_team, attacker, defender, current_action

    if fact == "medrival":
        logger.write("Se precipita y le regala el balón al medio rival.")
        attacking_team = 1 - attacking_team
        attacker = choose_receiver(positions[attacking_team], "medio", rng)
        defender = choose_receiver(positions[1 - attacking_team], "medio", rng)
        ball.equipo = attacking_team
        ball.atacante = attacker
        ball.defensor = defender
        return attacking_team, attacker, defender, current_action

    if fact in {"1vs1", "1vs1rival"}:
        if fact == "1vs1rival":
            logger.write("¡Peligrosa pérdida de balón! El rival se planta en un uno contra uno.")
            attacking_team = 1 - attacking_team
            attacker = choose_receiver(positions[attacking_team], "delantero", rng)
        else:
            attacker = choose_receiver(positions[attacking_team], "delantero", rng)
        defender = 1
        if _resolve_direct_shot(attacking_team, attacker, teams, rng, logger, home, away, "chute", "reflejos"):
            return (*_goal(attacking_team, score, ball, logger, home, away), "chute")
        ball.equipo = 1 - attacking_team
        ball.atacante = 1
        ball.defensor = 11
        return 1 - attacking_team, 1, 11, "chute"

    if fact == "chute 2":
        logger.write("El balón va hacia el portero. ¿La parará?")
        if _resolve_direct_shot(attacking_team, attacker, teams, rng, logger, home, away, "chute", "parada"):
            return (*_goal(attacking_team, score, ball, logger, home, away), "chute")
        return 1 - attacking_team, 1, 11, "chute"

    if fact == "chute lejano 2":
        logger.write("El tiro lejano supera al medio y va hacia la defensa.")
        defender = choose_receiver(positions[1 - attacking_team], "defensa", rng)
        dado_at, combo_at = Dados(rng=rng).lanzar()
        dado_def, combo_def = Dados(rng=rng).lanzar()
        f_at = teams[attacking_team][attacker - 1].accion("chute lejano", dado_at)
        f_def = teams[1 - attacking_team][defender - 1].accion("entrada", dado_def)
        logger.write(f"Dados tiro lejano {dado_at}; dados defensa {dado_def}.")
        if combo_at - combo_def > 0:
            logger.write("El balón rebota en el defensa, confunde al portero y ... ¡Gooool!")
            return (*_goal(attacking_team, score, ball, logger, home, away), "chute lejano")
        if combo_at - combo_def == 0 and f_at - f_def >= 0:
            if _resolve_direct_shot(attacking_team, attacker, teams, rng, logger, home, away, "chute lejano", "parada"):
                return (*_goal(attacking_team, score, ball, logger, home, away), "chute lejano")
        logger.write("¡Balón interceptado por la defensa!")
        return 1 - attacking_team, 1, 11, "chute lejano"

    if fact in {"cabvsdef", "cabvspor"}:
        if fact == "cabvsdef":
            logger.write("¡Saltan dos jugadores a cabecear la pelota!")
            attacker = choose_receiver(positions[attacking_team], "delantero", rng)
            defender = choose_receiver(positions[1 - attacking_team], "defensa", rng)
            dado_at, combo_at = Dados(rng=rng).lanzar()
            dado_def, combo_def = Dados(rng=rng).lanzar()
            f_at = teams[attacking_team][attacker - 1].accion("cabeza", dado_at)
            f_def = teams[1 - attacking_team][defender - 1].accion("cabeza", dado_def)
            logger.write(f"Dados remate {dado_at}; dados defensa {dado_def}.")
            if combo_at - combo_def < 0 and f_at - f_def <= 0:
                logger.write("¡Interceptación del defensa!")
                return 1 - attacking_team, 1, 11, "centro"
        logger.write("¡El remate de cabeza se dirige a portería!")
        attacker = choose_receiver(positions[attacking_team], "delantero", rng)
        if _resolve_direct_shot(attacking_team, attacker, teams, rng, logger, home, away, "cabeza", "reflejos"):
            return (*_goal(attacking_team, score, ball, logger, home, away), "centro")
        return 1 - attacking_team, 1, 11, "centro"

    logger.write("La jugada se apaga sin consecuencias claras.")
    return attacking_team, attacker, defender, current_action


def simulate_penalty_shootout(home: str, away: str, rng: random.Random, logger: MatchLogger) -> tuple[str, str, int, int]:
    logger.write("Empieza la tanda de penaltis: cinco rondas y, si hace falta, muerte súbita.")
    home_penalties = 0
    away_penalties = 0

    for round_no in range(1, 6):
        logger.write(f"Ronda {round_no} de penaltis.")
        for team, is_home in [(home, True), (away, False)]:
            logger.write(f"Chuta {team} y ...")
            outcome = penalty_outcome(rng)
            if outcome == "goal":
                logger.write("¡Gooool!")
                if is_home:
                    home_penalties += 1
                else:
                    away_penalties += 1
            elif outcome == "saved":
                logger.write("¡El portero la paró!")
            else:
                logger.write("¡Salió a las nubes!")
        logger.write(f"Penaltis tras la ronda {round_no}: {home} {home_penalties} - {away_penalties} {away}")

    sudden_round = 6
    while home_penalties == away_penalties:
        logger.write(f"Muerte súbita, ronda {sudden_round}.")
        before_home = home_penalties
        before_away = away_penalties
        for team, is_home in [(home, True), (away, False)]:
            logger.write(f"Chuta {team} y ...")
            outcome = penalty_outcome(rng)
            if outcome == "goal":
                logger.write("¡Gooool!")
                if is_home:
                    home_penalties += 1
                else:
                    away_penalties += 1
            elif outcome == "saved":
                logger.write("¡El portero la paró!")
            else:
                logger.write("¡Salió a las nubes!")
        if home_penalties == away_penalties and home_penalties == before_home and away_penalties == before_away:
            logger.write("Nadie marca en esta ronda. Seguimos.")
        elif home_penalties == away_penalties:
            logger.write("Ambos marcan. Seguimos.")
        sudden_round += 1

    winner = home if home_penalties > away_penalties else away
    loser = away if winner == home else home
    logger.write(f"Gana {winner} en los penaltis: {home_penalties} - {away_penalties}.")
    return winner, loser, home_penalties, away_penalties


def simulate_match(
    home: str,
    away: str,
    minutes: float = 10.0,
    knockout: bool = False,
    rng: random.Random | None = None,
    print_to_console: bool = True,
    output_path: str | Path | None = None,
    stage: str = "",
    match_id: str = "",
) -> MatchResult:
    rng = rng or random.Random()
    logger = MatchLogger(print_to_console=print_to_console)
    score = Marcador()
    form_home = choose_formation(rng)
    form_away = choose_formation(rng)
    positions = [positions_from_formation(form_home), positions_from_formation(form_away)]
    teams = [generar(0, form_home, rng), generar(1, form_away, rng)]
    attacking_team = rng.randint(0, 1)
    attacker = 1
    defender = 11
    ball = Balon(attacking_team, attacker, defender, False)
    time = Crono(0.0)

    header = f"{stage} {match_id}".strip()
    if header:
        logger.write(header)
    logger.write(f"Partido: {home} vs {away}")
    logger.write(f"Formación {home}: {'-'.join(map(str, form_home))}")
    logger.write(f"Formación {away}: {'-'.join(map(str, form_away))}")
    logger.write(f"Empieza sacando {team_name(attacking_team, home, away)}.")

    while time.minuto <= minutes:
        attacking_positions = positions[attacking_team]
        defending_positions = positions[1 - attacking_team]
        attacking_team_players = teams[attacking_team]
        defending_team_players = teams[1 - attacking_team]
        attacker_position = attacking_positions[attacker - 1]
        action = choose_action(attacker_position, rng)
        defender, defensive_action = choose_defender(attacker_position, defending_positions, rng)
        ball.equipo = attacking_team
        ball.atacante = attacker
        ball.defensor = defender

        logger.write("")
        logger.write(f"Minuto {time.reloj()}.")
        logger.write(
            f"{team_name(attacking_team, home, away)} ataca con su {attacker_position} #{attacker}. "
            f"Acción elegida al azar: {action}."
        )
        logger.write(
            f"Defiende {team_name(1 - attacking_team, home, away)} con el #{defender}. "
            f"Respuesta defensiva: {defensive_action}."
        )

        dice_at, combo_at = Dados(rng=rng).lanzar()
        dice_def, combo_def = Dados(rng=rng).lanzar()
        f_at = attacking_team_players[attacker - 1].accion(action, dice_at)
        f_def = defending_team_players[defender - 1].accion(defensive_action, dice_def)
        fact = criterio(combo_at - combo_def, f_at - f_def, attacker_position, action)
        logger.write(f"Dados ataque {dice_at}; dados defensa {dice_def}.")
        logger.write(f"Diferencia de fuerza: {f_at - f_def:.2f}. Consecuencia: {fact}.")

        attacking_team, attacker, defender, action_for_clock = _apply_consequence(
            fact,
            attacking_team,
            attacker,
            defender,
            score,
            ball,
            positions,
            teams,
            rng,
            logger,
            home,
            away,
            action,
        )
        time.lapso(action_for_clock)

    logger.write("")
    logger.write(f"Final del partido: {home} {score.local} - {score.visitante} {away}")

    winner: Optional[str] = None
    loser: Optional[str] = None
    penalties_home: Optional[int] = None
    penalties_away: Optional[int] = None
    if score.local > score.visitante:
        winner, loser = home, away
    elif score.local < score.visitante:
        winner, loser = away, home
    elif knockout:
        winner, loser, penalties_home, penalties_away = simulate_penalty_shootout(home, away, rng, logger)

    result = MatchResult(
        home=home,
        away=away,
        home_goals=score.local,
        away_goals=score.visitante,
        winner=winner,
        loser=loser,
        penalties_home=penalties_home,
        penalties_away=penalties_away,
        stage=stage,
        match_id=match_id,
        log_lines=list(logger.lines),
    )

    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(logger.lines) + "\n", encoding="utf-8")

    return result
