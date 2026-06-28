"""Download miniature flags for the World Cup GUI.

Run once from the project folder:
    python download_flags.py
"""

from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

from team_assets import TEAM_FLAG_CODES, asset_root, flag_url


def download_file(url: str, target: Path) -> None:
    request = Request(url, headers={"User-Agent": "RPGsoccerWorldCupSimulator/1.0"})
    with urlopen(request, timeout=20) as response:
        target.write_bytes(response.read())


def main() -> None:
    flags_dir = asset_root() / "flags"
    flags_dir.mkdir(parents=True, exist_ok=True)
    for team in TEAM_FLAG_CODES:
        target = flags_dir / f"{TEAM_FLAG_CODES[team]}_80.png"
        if target.exists() and target.stat().st_size > 0:
            print(f"OK {team}: {target.name}")
            continue
        url = flag_url(team, size=80)
        print(f"Downloading {team}: {url}")
        try:
            download_file(url, target)
        except Exception as exc:
            print(f"Could not download {team}: {exc}")
    print(f"Flags folder: {flags_dir}")


if __name__ == "__main__":
    main()
