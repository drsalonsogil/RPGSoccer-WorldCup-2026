"""Run a complete RPGsoccer World Cup 2026 simulation."""

from __future__ import annotations

import argparse
from pathlib import Path

from tournament import WorldCupSimulator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate the FIFA World Cup 2026 with RPGsoccer.")
    parser.add_argument("--output-dir", default="worldcup_2026_simulation", help="Folder where all match logs and tables are written.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible simulations.")
    parser.add_argument("--minutes", type=float, default=10.0, help="Length of every match in simulated RPGsoccer minutes.")
    parser.add_argument("--quiet", action="store_true", help="Do not print the play-by-play log to the terminal.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    simulator = WorldCupSimulator(
        output_dir=Path(args.output_dir),
        seed=args.seed,
        minutes=args.minutes,
        print_to_console=not args.quiet,
    )
    champion = simulator.run()
    print(f"Simulation finished. Champion: {champion}")
    print(f"Output folder: {Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()
