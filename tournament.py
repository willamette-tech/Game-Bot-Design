"""Reproducible multi-match tournament runner for Tron bots."""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from arena import LoadedBot, load_bots, run_match, write_replay


POINTS = {1: 3, 2: 2, 3: 1, 4: 0}

# (survival weight, coverage weight).  "survival" reproduces placement-only scoring.
SCORING_PRESETS = {
    "survival": (1.0, 0.0),
    "balanced": (0.5, 0.5),
    "coverage": (0.0, 1.0),
}


def score_match(placements: list[dict[str, object]], survival_weight: float, coverage_weight: float) -> dict[str, float]:
    """Split one match's points between staying alive and claiming ground.

    The survival half is the usual placement table.  The coverage half shares the
    same total pool out in proportion to the cells each bot painted, so the two
    halves are worth the same to a bot and the weights alone decide the incentive.
    """

    pool = float(sum(POINTS.get(place, 0) for place in range(1, len(placements) + 1)))
    total_cells = sum(int(item["trail_length"]) for item in placements) or 1
    return {
        str(item["bot_id"]): (
            survival_weight * POINTS.get(int(item["place"]), 0)
            + coverage_weight * pool * int(item["trail_length"]) / total_cells
        )
        for item in placements
    }


def _format_points(value: float) -> str:
    return f"{value:.0f}" if abs(value - round(value)) < 1e-9 else f"{value:.2f}"


def make_schedule(bots: list[LoadedBot], rounds: int, seed: int) -> list[list[LoadedBot]]:
    """Make groups of 2-4, with every bot appearing once in each round."""

    if len(bots) < 2:
        raise ValueError("a tournament needs at least two bots")
    if rounds < 1:
        raise ValueError("rounds must be positive")
    rng = random.Random(seed)
    schedule: list[list[LoadedBot]] = []
    for _ in range(rounds):
        shuffled = bots[:]
        rng.shuffle(shuffled)
        offset = 0
        while offset < len(shuffled):
            remaining = len(shuffled) - offset
            size = 3 if remaining == 5 else min(4, remaining)
            if size == 1:  # Only possible for an unusual future grouping change.
                schedule[-1].append(shuffled[offset])
                break
            schedule.append(shuffled[offset : offset + size])
            offset += size
    return schedule


def _print_leaderboard(
    bots: list[LoadedBot],
    scores: dict[str, float],
    finishes: dict[str, Counter[int]],
    cells: dict[str, int],
    shares: dict[str, list[float]],
) -> None:
    ordered = sorted(bots, key=lambda bot: (-scores[bot.bot_id], -cells[bot.bot_id], bot.name.casefold()))
    print("\nLEADERBOARD")
    print(f"{'Rank':<6}{'Bot':<26}{'Points':>8}{'Cells':>8}{'Area%':>8}  Finishes")
    previous_points: Optional[float] = None
    rank = 0
    for index, bot in enumerate(ordered):
        if scores[bot.bot_id] != previous_points:
            rank = index + 1
            previous_points = scores[bot.bot_id]
        finish_text = ", ".join(f"{place}:{count}" for place, count in sorted(finishes[bot.bot_id].items())) or "-"
        bot_shares = shares[bot.bot_id]
        share_text = f"{100 * sum(bot_shares) / len(bot_shares):.0f}" if bot_shares else "-"
        points = _format_points(scores[bot.bot_id])
        print(f"{rank:<6}{bot.name[:25]:<26}{points:>8}{cells[bot.bot_id]:>8}{share_text:>8}  {finish_text}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run a reproducible Tron bot tournament.")
    parser.add_argument("--bots", type=Path, default=Path("bots"))
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--logs", type=Path, default=Path("logs"))
    parser.add_argument("--width", type=int, default=40)
    parser.add_argument("--height", type=int, default=30)
    parser.add_argument("--tick-cap", type=int, default=2000)
    parser.add_argument("--timeout-ms", type=int, default=100)
    parser.add_argument(
        "--scoring",
        choices=sorted(SCORING_PRESETS),
        default="survival",
        help="what the points reward: survival (placement only, the default), coverage (cells claimed), or balanced",
    )
    parser.add_argument("--survival-weight", type=float, help="override the preset's survival weight")
    parser.add_argument("--coverage-weight", type=float, help="override the preset's coverage weight")
    playback = parser.add_mutually_exclusive_group()
    playback.add_argument("--headless", action="store_true", help="never open the viewer (this is also the default without --replay)")
    playback.add_argument("--replay", type=int, nargs="+", metavar="MATCH", help="open these 1-based match numbers after all matches finish")
    args = parser.parse_args(argv)

    survival_weight, coverage_weight = SCORING_PRESETS[args.scoring]
    if args.survival_weight is not None:
        survival_weight = args.survival_weight
    if args.coverage_weight is not None:
        coverage_weight = args.coverage_weight
    scoring_name = args.scoring
    if (survival_weight, coverage_weight) != SCORING_PRESETS[args.scoring]:
        scoring_name = "custom"
    if survival_weight < 0 or coverage_weight < 0 or survival_weight + coverage_weight <= 0:
        parser.error("scoring weights must not be negative and cannot both be zero")

    bots = load_bots(args.bots)
    if len(bots) < 2:
        parser.error(f"need at least two valid bots in {args.bots}")
    try:
        schedule = make_schedule(bots, args.rounds, args.seed)
    except ValueError as exc:
        parser.error(str(exc))

    args.logs.mkdir(parents=True, exist_ok=True)
    scores: dict[str, float] = defaultdict(float)
    finishes: dict[str, Counter[int]] = defaultdict(Counter)
    errors: dict[str, Counter[str]] = defaultdict(Counter)
    cells: dict[str, int] = defaultdict(int)
    shares: dict[str, list[float]] = defaultdict(list)
    logs: list[Path] = []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    print(f"Loaded {len(bots)} bots; running {len(schedule)} matches.")
    print(f"Scoring: {scoring_name} (survival x{survival_weight:g}, coverage x{coverage_weight:g})")
    for index, group in enumerate(schedule, start=1):
        match_seed = args.seed + index - 1
        names = " vs ".join(bot.name for bot in group)
        print(f"\nMatch {index:03d}: {names} (seed {match_seed})")
        replay = run_match(
            group,
            width=args.width,
            height=args.height,
            seed=match_seed,
            tick_cap=args.tick_cap,
            timeout_ms=args.timeout_ms,
        )
        log_path = args.logs / f"{stamp}_match_{index:03d}_seed_{match_seed}.json"
        write_replay(replay, log_path)
        logs.append(log_path)
        placements = replay["results"]["placements"]  # type: ignore[index]
        awarded = score_match(placements, survival_weight, coverage_weight)
        claimed = sum(int(item["trail_length"]) for item in placements) or 1
        for placement in placements:
            bot_id = str(placement["bot_id"])
            place = int(placement["place"])
            trail = int(placement["trail_length"])
            scores[bot_id] += awarded[bot_id]
            finishes[bot_id][place] += 1
            cells[bot_id] += trail
            shares[bot_id].append(trail / claimed)
            print(f"  {place}. {placement['name']} (+{_format_points(awarded[bot_id])}, {trail} cells = {100 * trail / claimed:.0f}%)")
        for frame in replay["frames"]:  # type: ignore[assignment]
            for event in frame["errors"]:
                errors[str(event["bot_id"])][str(event["type"])] += 1

    _print_leaderboard(bots, scores, finishes, cells, shares)
    print("\nBOT ERROR / TIMEOUT SUMMARY")
    reported = False
    for bot in sorted(bots, key=lambda item: (-sum(errors[item.bot_id].values()), item.name.casefold())):
        counts = errors[bot.bot_id]
        if counts:
            reported = True
            print(f"  {bot.name}: " + ", ".join(f"{kind}={count}" for kind, count in counts.most_common()))
    if not reported:
        print("  No bot errors.")
    print(f"\nLogs written to {args.logs}")

    if args.replay:
        viewer = Path(__file__).with_name("viewer.py")
        for match_number in args.replay:
            if 1 <= match_number <= len(logs):
                subprocess.run([sys.executable, str(viewer), str(logs[match_number - 1])], check=False)
            else:
                print(f"Cannot replay match {match_number}: valid range is 1-{len(logs)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
