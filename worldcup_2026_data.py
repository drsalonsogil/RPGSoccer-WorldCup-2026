"""World Cup 2026 teams, group pairings and knockout bracket slots."""

from __future__ import annotations

from itertools import combinations
from typing import Dict, Iterable, List, Tuple


GROUPS: Dict[str, List[str]] = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Curacao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}


GROUP_MATCH_PAIRINGS = [
    (0, 1),
    (2, 3),
    (0, 2),
    (3, 1),
    (3, 0),
    (1, 2),
]


ROUND32_MATCHES = [
    {"id": "M73", "home": "2A", "away": "2B"},
    {"id": "M74", "home": "1E", "away": "3:1E", "third_candidates": "ABCDF"},
    {"id": "M75", "home": "1F", "away": "2C"},
    {"id": "M76", "home": "1C", "away": "2F"},
    {"id": "M77", "home": "1I", "away": "3:1I", "third_candidates": "CDFGH"},
    {"id": "M78", "home": "2E", "away": "2I"},
    {"id": "M79", "home": "1A", "away": "3:1A", "third_candidates": "CEFHI"},
    {"id": "M80", "home": "1L", "away": "3:1L", "third_candidates": "EHIJK"},
    {"id": "M81", "home": "1D", "away": "3:1D", "third_candidates": "BEFIJ"},
    {"id": "M82", "home": "1G", "away": "3:1G", "third_candidates": "AEHIJ"},
    {"id": "M83", "home": "2K", "away": "2L"},
    {"id": "M84", "home": "1H", "away": "2J"},
    {"id": "M85", "home": "1B", "away": "3:1B", "third_candidates": "EFGIJ"},
    {"id": "M86", "home": "1J", "away": "2H"},
    {"id": "M87", "home": "1K", "away": "3:1K", "third_candidates": "DEIJL"},
    {"id": "M88", "home": "2D", "away": "2G"},
]


THIRD_PLACE_SLOT_ORDER = ["1A", "1B", "1D", "1E", "1G", "1I", "1K", "1L"]

THIRD_PLACE_SLOT_TO_MATCH = {
    "1A": "M79",
    "1B": "M85",
    "1D": "M81",
    "1E": "M74",
    "1G": "M82",
    "1I": "M77",
    "1K": "M87",
    "1L": "M80",
}

THIRD_PLACE_SLOT_CANDIDATES = {
    "1A": set("CEFHI"),
    "1B": set("EFGIJ"),
    "1D": set("BEFIJ"),
    "1E": set("ABCDF"),
    "1G": set("AEHIJ"),
    "1I": set("CDFGH"),
    "1K": set("DEIJL"),
    "1L": set("EHIJK"),
}


ROUND_OF_16 = [
    ("M89", "M74", "M77"),
    ("M90", "M73", "M75"),
    ("M91", "M76", "M78"),
    ("M92", "M79", "M80"),
    ("M93", "M83", "M84"),
    ("M94", "M81", "M82"),
    ("M95", "M86", "M88"),
    ("M96", "M85", "M87"),
]

QUARTER_FINALS = [
    ("M97", "M89", "M90"),
    ("M98", "M93", "M94"),
    ("M99", "M91", "M92"),
    ("M100", "M95", "M96"),
]

SEMI_FINALS = [
    ("M101", "M97", "M98"),
    ("M102", "M99", "M100"),
]

THIRD_PLACE_MATCH = ("M103", "L101", "L102")
FINAL = ("M104", "M101", "M102")


FIFA_THIRD_PLACE_TABLE: Dict[Tuple[str, ...], Dict[str, str]] = {}


def _all_third_place_slots_are_valid(groups: Iterable[str]) -> bool:
    groups_set = set(groups)
    return len(groups_set) == 8 and groups_set.issubset(set("ABCDEFGHIJKL"))


def allocate_third_place_groups(qualified_groups: List[str], ranked_groups: List[str]) -> tuple[Dict[str, str], str]:
    """Assign the eight third-placed qualifiers to the official third-place slots.

    If FIFA_THIRD_PLACE_TABLE contains the exact Annex C row, it is used.
    Otherwise, a deterministic backtracking solver fills the same official slots
    from the official candidate sets, preferring the highest-ranked third-place teams.
    """

    if not _all_third_place_slots_are_valid(qualified_groups):
        raise ValueError("Se necesitan exactamente ocho grupos terceros clasificados.")

    key = tuple(sorted(qualified_groups))
    if key in FIFA_THIRD_PLACE_TABLE:
        return dict(FIFA_THIRD_PLACE_TABLE[key]), "official_annex_c"

    ranked_index = {group: i for i, group in enumerate(ranked_groups)}
    slots = sorted(
        THIRD_PLACE_SLOT_ORDER,
        key=lambda slot: (
            len(THIRD_PLACE_SLOT_CANDIDATES[slot].intersection(qualified_groups)),
            THIRD_PLACE_SLOT_ORDER.index(slot),
        ),
    )

    assignment: Dict[str, str] = {}
    used: set[str] = set()

    def solve(position: int) -> bool:
        if position == len(slots):
            return True
        slot = slots[position]
        candidates = sorted(
            THIRD_PLACE_SLOT_CANDIDATES[slot].intersection(qualified_groups).difference(used),
            key=lambda group: ranked_index.get(group, 999),
        )
        for group in candidates:
            assignment[slot] = group
            used.add(group)
            if solve(position + 1):
                return True
            used.remove(group)
            del assignment[slot]
        return False

    if not solve(0):
        raise RuntimeError("No se pudo construir una asignación válida de terceros.")

    return assignment, "slot_solver"


def third_place_combination_count() -> int:
    return len(list(combinations("ABCDEFGHIJKL", 8)))
