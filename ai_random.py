"""Random decisions for the non-interactive RPGsoccer match engine."""

from __future__ import annotations

import random
from typing import Sequence

from rpgsoccer_core import acciones_validas, accion_defensiva, jugadores_por_posicion


FORMATIONS = [
    [4, 3, 3],
    [4, 4, 2],
    [3, 5, 2],
    [5, 4, 1],
    [3, 4, 3],
    [5, 3, 2],
]


def choose_formation(rng: random.Random) -> list[int]:
    return list(rng.choice(FORMATIONS))


def choose_action(position: str, rng: random.Random) -> str:
    return rng.choice(acciones_validas(position))


def choose_defender(attacker_position: str, defender_positions: Sequence[str], rng: random.Random) -> tuple[int, str]:
    required_position, defensive_action = accion_defensiva(attacker_position)
    candidates = jugadores_por_posicion(defender_positions, required_position)
    if not candidates:
        candidates = list(range(1, len(defender_positions) + 1))
    return rng.choice(candidates), defensive_action


def choose_receiver(positions: Sequence[str], position: str, rng: random.Random) -> int:
    candidates = jugadores_por_posicion(positions, position)
    if not candidates:
        candidates = list(range(1, len(positions) + 1))
    return rng.choice(candidates)


def coin_winner(first: str, second: str, rng: random.Random) -> str:
    return first if rng.randint(0, 1) == 0 else second


def penalty_outcome(rng: random.Random) -> str:
    return rng.choice(["goal", "saved", "miss"])
