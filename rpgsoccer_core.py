"""Core RPGsoccer objects used by the automatic World Cup simulator."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Dict, List, Sequence, Tuple


ACTION_TIME = {
    "pase": 0.25,
    "pase largo": 0.50,
    "centro": 0.50,
    "regate": 0.25,
    "chute": 0.25,
    "chute lejano": 0.50,
}


@dataclass
class Futbolista:
    equipo: int
    dorsal: int
    posicion: str
    skills: Dict[str, float]

    def accion(self, skill: str, dado: Sequence[int]) -> float:
        power = 50.0 * (sum(dado) / 12.0) - 25.0
        return self.skills.get(skill, 0.0) + power


class Portero(Futbolista):
    def __init__(self, equipo: int, dorsal: int, parada: float, pase: float, pase_largo: float, reflejos: float):
        super().__init__(
            equipo=equipo,
            dorsal=dorsal,
            posicion="portero",
            skills={
                "parada": parada,
                "pase": pase,
                "pase largo": pase_largo,
                "reflejos": reflejos,
            },
        )


class Defensa(Futbolista):
    def __init__(self, equipo: int, dorsal: int, entrada: float, pase: float, pase_largo: float, cabeza: float):
        super().__init__(
            equipo=equipo,
            dorsal=dorsal,
            posicion="defensa",
            skills={
                "entrada": entrada,
                "pase": pase,
                "pase largo": pase_largo,
                "cabeza": cabeza,
            },
        )


class Medio(Futbolista):
    def __init__(self, equipo: int, dorsal: int, entrada: float, pase: float, chute_lejano: float, centro: float):
        super().__init__(
            equipo=equipo,
            dorsal=dorsal,
            posicion="medio",
            skills={
                "entrada": entrada,
                "pase": pase,
                "chute lejano": chute_lejano,
                "centro": centro,
            },
        )


class Delantero(Futbolista):
    def __init__(self, equipo: int, dorsal: int, presion: float, chute: float, regate: float, cabeza: float):
        super().__init__(
            equipo=equipo,
            dorsal=dorsal,
            posicion="delantero",
            skills={
                "presion": presion,
                "chute": chute,
                "regate": regate,
                "cabeza": cabeza,
            },
        )


@dataclass
class Balon:
    equipo: int
    atacante: int
    defensor: int
    gol: bool = False

    def cambio_pos(self) -> None:
        self.atacante, self.defensor = self.defensor, self.atacante
        self.equipo = 1 - self.equipo

    def cambio_at(self, newat: int) -> None:
        self.atacante = newat

    def cambio_def(self, newdef: int) -> None:
        self.defensor = newdef

    def entra(self) -> None:
        self.gol = True

    def restart(self) -> None:
        self.gol = False


@dataclass
class Crono:
    minuto: float = 0.0

    def reloj(self) -> str:
        minutos = int(self.minuto)
        segundos = int(round((self.minuto - minutos) * 60.0))
        if segundos == 60:
            minutos += 1
            segundos = 0
        return f"{minutos:02d}:{segundos:02d}"

    def lapso(self, action: str) -> None:
        self.minuto += ACTION_TIME.get(action, 0.25)


@dataclass
class Marcador:
    local: int = 0
    visitante: int = 0

    @property
    def quiniela(self) -> str:
        if self.local > self.visitante:
            return "1"
        if self.local < self.visitante:
            return "2"
        return "X"

    def gol(self, equipo: int) -> None:
        if equipo == 0:
            self.local += 1
        else:
            self.visitante += 1


class Dados:
    def __init__(self, lados: int = 6, rng: random.Random | None = None):
        self.lados = lados
        self.rng = rng or random.Random()

    def lanzar(self) -> Tuple[List[int], int]:
        dado = [self.rng.randint(1, self.lados), self.rng.randint(1, self.lados)]
        combo = 0
        if dado[0] == dado[1] and dado[0] <= 3:
            combo = -1
        elif dado[0] == dado[1] and dado[0] > 3:
            combo = 1
        return dado, combo


def gaussian_skill(rng: random.Random, mean: float, sigma: float = 4.0) -> float:
    return mean + rng.gauss(0.0, sigma)


def positions_from_formation(formacion: Sequence[int]) -> List[str]:
    if len(formacion) != 3 or sum(formacion) != 10:
        raise ValueError("La formación debe tener tres números y sumar 10, por ejemplo [4, 3, 3].")
    posiciones = ["portero"]
    posiciones.extend(["defensa"] * int(formacion[0]))
    posiciones.extend(["medio"] * int(formacion[1]))
    posiciones.extend(["delantero"] * int(formacion[2]))
    return posiciones


def generar(equipo: int, formacion: Sequence[int], rng: random.Random | None = None) -> List[Futbolista]:
    rng = rng or random.Random()
    futbolistas: List[Futbolista] = []
    numero = 1
    futbolistas.append(
        Portero(
            equipo,
            numero,
            gaussian_skill(rng, 75.0),
            gaussian_skill(rng, 70.0),
            gaussian_skill(rng, 65.0),
            gaussian_skill(rng, 55.0),
        )
    )
    for _ in range(int(formacion[0])):
        numero += 1
        futbolistas.append(
            Defensa(
                equipo,
                numero,
                gaussian_skill(rng, 75.0),
                gaussian_skill(rng, 65.0),
                gaussian_skill(rng, 55.0),
                gaussian_skill(rng, 60.0),
            )
        )
    for _ in range(int(formacion[1])):
        numero += 1
        futbolistas.append(
            Medio(
                equipo,
                numero,
                gaussian_skill(rng, 60.0),
                gaussian_skill(rng, 75.0),
                gaussian_skill(rng, 55.0),
                gaussian_skill(rng, 65.0),
            )
        )
    for _ in range(int(formacion[2])):
        numero += 1
        futbolistas.append(
            Delantero(
                equipo,
                numero,
                gaussian_skill(rng, 55.0),
                gaussian_skill(rng, 75.0),
                gaussian_skill(rng, 65.0),
                gaussian_skill(rng, 60.0),
            )
        )
    return futbolistas


def acciones_validas(posicion: str) -> List[str]:
    if posicion == "portero":
        return ["pase", "pase largo"]
    if posicion == "defensa":
        return ["pase", "pase largo"]
    if posicion == "medio":
        return ["pase", "chute lejano", "centro"]
    if posicion == "delantero":
        return ["chute", "regate"]
    raise ValueError(f"Posición desconocida: {posicion}")


def accion_defensiva(posicion_atacante: str) -> Tuple[str, str]:
    if posicion_atacante in {"portero", "defensa"}:
        return "delantero", "presion"
    if posicion_atacante == "medio":
        return "medio", "entrada"
    if posicion_atacante == "delantero":
        return "defensa", "entrada"
    raise ValueError(f"Posición atacante desconocida: {posicion_atacante}")


def jugadores_por_posicion(posiciones: Sequence[str], posicion: str) -> List[int]:
    return [i + 1 for i, pos in enumerate(posiciones) if pos == posicion]


def criterio(azar: int, potencia: float, jug: str, intento: str) -> str:
    ocurre = "robo"
    if jug == "portero" and intento == "pase":
        if azar == -2:
            ocurre = "golrival"
        elif azar == -1:
            ocurre = "1vs1rival"
        elif azar == 0:
            ocurre = "pasedef" if potencia >= 0 else "robo"
        elif azar > 0:
            ocurre = "pasemed"
    elif jug == "portero" and intento == "pase largo":
        if azar == -2:
            ocurre = "golrival"
        elif azar == -1:
            ocurre = "1vs1rival"
        elif azar == 0:
            ocurre = "pasemed" if potencia >= 0 else "robo"
        elif azar == 1:
            ocurre = "pasedel"
        elif azar == 2:
            ocurre = "1vs1"
    elif jug == "defensa":
        if azar == -2:
            ocurre = "1vs1rival"
        elif azar == -1:
            ocurre = "delrival"
        elif azar == 0:
            if potencia >= 0 and intento == "pase":
                ocurre = "pasemed"
            elif potencia >= 0 and intento == "pase largo":
                ocurre = "pasedel"
            else:
                ocurre = "robo"
        elif azar == 1 and intento == "pase":
            ocurre = "pasedel"
        elif azar == 1 and intento == "pase largo":
            ocurre = "1vs1"
        elif azar == 2:
            ocurre = "1vs1"
    elif jug == "medio" and intento == "pase":
        if azar < 0:
            ocurre = "delrival"
        elif azar == 0:
            ocurre = "pasedel" if potencia >= 0 else "robo"
        elif azar > 0:
            ocurre = "1vs1"
    elif jug == "medio" and intento == "chute lejano":
        if azar < 0:
            ocurre = "delrival"
        elif azar == 0:
            ocurre = "chute lejano 2" if potencia >= 0 else "robo"
        elif azar > 0:
            ocurre = "chute 2"
    elif jug == "medio" and intento == "centro":
        if azar < 0:
            ocurre = "delrival"
        elif azar == 0:
            ocurre = "cabvsdef" if potencia >= 0 else "robo"
        elif azar > 0:
            ocurre = "cabvspor"
    elif jug == "delantero" and intento == "regate":
        if azar < 0:
            ocurre = "medrival"
        elif azar == 0:
            ocurre = "1vs1" if potencia >= 0 else "robo"
        elif azar > 0:
            ocurre = "gol"
    elif jug == "delantero" and intento == "chute":
        if azar < 0:
            ocurre = "medrival"
        elif azar == 0:
            ocurre = "chute 2" if potencia >= 0 else "robo"
        elif azar > 0:
            ocurre = "gol"
    return ocurre


def team_name(equipo: int, home: str, away: str) -> str:
    return home if equipo == 0 else away
