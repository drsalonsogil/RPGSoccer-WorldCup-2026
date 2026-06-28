"""Persistent seed and score history for RPGsoccer World Cup."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import pickle
import random
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
SAVED_GAMES_DIR = PROJECT_DIR / "saved_games"
USED_SEEDS_FILE = SAVED_GAMES_DIR / "used_seeds.json"
HISTORY_FILE = SAVED_GAMES_DIR / "historical_classifications.json"


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def seeds_from_saved_games() -> set[int]:
    seeds: set[int] = set()
    SAVED_GAMES_DIR.mkdir(parents=True, exist_ok=True)
    for path in SAVED_GAMES_DIR.glob("*.rpgsave"):
        try:
            with path.open("rb") as handle:
                obj = pickle.load(handle)
            seed = getattr(obj, "seed", None)
            if seed is not None:
                seeds.add(int(seed))
        except Exception:
            continue
    return seeds


def used_seeds() -> set[int]:
    stored = _read_json(USED_SEEDS_FILE, [])
    seeds = {int(item) for item in stored if str(item).isdigit()}
    seeds.update(seeds_from_saved_games())
    return seeds


def register_seed(seed: int) -> None:
    seeds = sorted(used_seeds() | {int(seed)})
    _write_json(USED_SEEDS_FILE, seeds)


def generate_unique_seed() -> int:
    seeds = used_seeds()
    rng = random.SystemRandom()
    for _ in range(10000):
        seed = rng.randrange(1, 999_999_999)
        if seed not in seeds:
            register_seed(seed)
            return seed
    raise RuntimeError("Could not generate an unused random seed.")


def read_history() -> dict[str, list[dict[str, Any]]]:
    data = _read_json(HISTORY_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in ["single_game", "tournament", "guess_the_winner"]:
        data.setdefault(key, [])
    return data


def add_history(kind: str, record: dict[str, Any]) -> None:
    data = read_history()
    record = dict(record)
    record.setdefault("date_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    data.setdefault(kind, []).append(record)
    _write_json(HISTORY_FILE, data)


def top_history(kind: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = read_history().get(kind, [])
    if kind == "guess_the_winner":
        return sorted(rows, key=lambda row: int(row.get("points", 0)), reverse=True)[:limit]
    if kind == "tournament":
        rank_order = {"Winner": 1, "Runner-up": 2, "Third": 3, "Fourth": 4, "QF": 5, "R16": 6, "R32": 7, "Group stage": 8, "Unknown": 9}
        return sorted(rows, key=lambda row: (rank_order.get(str(row.get("final_position", "Unknown")), 99), str(row.get("date_time", ""))))[:limit]
    return list(reversed(rows))[:limit]
