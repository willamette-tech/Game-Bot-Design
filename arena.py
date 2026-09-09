"""Headless Tron light-cycle arena and replay writer.

This module deliberately has no pygame dependency.  Bots receive fresh State objects,
and their moves are collected before any movement is resolved.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Callable, Iterable, Literal, Optional


# The only four values a bot may return, and the only ones it will ever be given.
Direction = Literal["up", "down", "left", "right"]

# grid[y][x] is None for an empty cell, or the id of the bot whose trail owns it.
Grid = list[list[Optional[str]]]

DIRECTIONS: dict[Direction, tuple[int, int]] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

COLORS: list[tuple[int, int, int]] = [
    (0, 220, 255),     # cyan
    (255, 170, 0),     # orange
    (255, 80, 220),    # magenta
    (255, 245, 70),    # yellow
    (245, 245, 245),   # white
    (175, 130, 255),   # lavender
    (70, 255, 180),    # mint
    (255, 120, 90),    # coral
]


@dataclass(frozen=True)
class LoadedBot:
    """A successfully loaded bot."""

    bot_id: str
    name: str
    move: Callable[[object], object]
    source: str = "<memory>"
    color: tuple[int, int, int] = (255, 255, 255)


@dataclass
class _RuntimeBot:
    definition: LoadedBot
    x: int
    y: int
    direction: Direction
    alive: bool = True
    trail_length: int = 1
    death_tick: Optional[int] = None


@dataclass
class Opponent:
    """One rival bot, as your bot sees it at the start of a tick."""

    x: int
    """Column of that bot's head; 0 is the left edge."""

    y: int
    """Row of that bot's head; 0 is the top edge."""

    direction: Direction
    """The direction it moved last."""

    alive: bool
    """False once it has crashed.  A dead bot never moves again, but its trail stays."""


@dataclass
class State:
    """Everything your bot knows on one tick, passed to ``move(state)``.

    Reading is all a bot ever needs to do here.  Every object is a fresh copy made
    for this one call, so writing to it changes nothing in the real match.
    """

    width: int
    """Board width in cells.  Valid columns are ``0`` to ``width - 1``."""

    height: int
    """Board height in cells.  Valid rows are ``0`` to ``height - 1``."""

    x: int
    """Column your head is on right now."""

    y: int
    """Row your head is on right now."""

    direction: Direction
    """The direction you moved last; returning it again keeps going straight."""

    tick: int
    """Which tick this is.  Your first decision is tick 1."""

    opponents: list[Opponent]
    """The other bots in this match, dead ones included."""

    grid: Grid = field(repr=False)
    """The whole board as ``grid[y][x]`` (row first, then column): ``None`` for an
    empty cell, otherwise the id of the bot whose trail is there.  Left out of
    ``repr`` so printing a state stays readable; prefer :meth:`is_free`."""

    def is_free(self, x: int, y: int) -> bool:
        """Return True only when ``(x, y)`` is on the board and has no trail on it.

        This is the safe way to ask about a cell: it does the bounds check that
        indexing ``grid`` yourself would skip.
        """

        return 0 <= x < self.width and 0 <= y < self.height and self.grid[y][x] is None


def _safe_name(value: object, fallback: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _load_module(path: Path) -> ModuleType:
    module_name = f"tron_bot_{abs(hash(path.resolve()))}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError("could not create an import specification")
    module = importlib.util.module_from_spec(spec)
    # Some decorators (notably dataclasses) look their module up during import.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def load_bot_files(paths: Iterable[str | Path]) -> list[LoadedBot]:
    """Load an explicit collection of bot files, skipping every broken file."""

    loaded: list[LoadedBot] = []
    used_ids: set[str] = set()
    for supplied_path in paths:
        path = Path(supplied_path)
        try:
            module = _load_module(path)
            move = getattr(module, "move", None)
            if not callable(move):
                raise TypeError("no callable move(state) function")
            base_id = path.stem
            bot_id = base_id
            suffix = 2
            while bot_id in used_ids:
                bot_id = f"{base_id}_{suffix}"
                suffix += 1
            used_ids.add(bot_id)
            color = COLORS[len(loaded) % len(COLORS)]
            loaded.append(LoadedBot(bot_id, _safe_name(getattr(module, "NAME", None), path.stem), move, str(path), color))
        except BaseException as exc:
            print(f"[load error] {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return loaded


def load_bots(folder: str | Path, recursive: bool = True) -> list[LoadedBot]:
    """Load bot files below a folder, reporting and skipping broken files."""

    folder = Path(folder)
    pattern = "**/*.py" if recursive else "*.py"
    paths = sorted(
        path for path in folder.glob(pattern)
        if path.name != "__init__.py" and "__pycache__" not in path.parts
    )
    return load_bot_files(paths)


def _default_starts(width: int, height: int, count: int) -> list[tuple[int, int, str]]:
    if count == 2:
        return [(width // 4, height // 2, "right"), (width - 1 - width // 4, height // 2, "left")]
    if count == 3:
        return [
            (width // 2, height // 4, "down"),
            (width // 4, height - 1 - height // 4, "right"),
            (width - 1 - width // 4, height - 1 - height // 4, "left"),
        ]
    return [
        (width // 4, height // 4, "right"),
        (width - 1 - width // 4, height // 4, "left"),
        (width - 1 - width // 4, height - 1 - height // 4, "left"),
        (width // 4, height - 1 - height // 4, "right"),
    ]


def _make_state(bot: _RuntimeBot, bots: list[_RuntimeBot], grid: Grid, tick: int) -> State:
    # Every nested object is new: a bot can only damage its own disposable snapshot.
    grid_copy = [row[:] for row in grid]
    opponents = [Opponent(other.x, other.y, other.direction, other.alive) for other in bots if other is not bot]
    return State(
        width=len(grid[0]),
        height=len(grid),
        x=bot.x,
        y=bot.y,
        direction=bot.direction,
        tick=tick,
        opponents=opponents,
        grid=grid_copy,
    )


def _call_in_thread(bot: _RuntimeBot, state: State, result: dict[str, object]) -> None:
    try:
        result["value"] = bot.definition.move(state)
    except BaseException as exc:
        try:
            detail = str(exc)
        except BaseException:
            detail = "<exception could not be displayed>"
        result["exception"] = f"{type(exc).__name__}: {detail}"


def _as_direction(value: object) -> Optional[Direction]:
    """Return what a bot handed back as a Direction, or None if it was not one."""

    if type(value) is str and value in DIRECTIONS:
        return value
    return None


def _safe_repr(value: object) -> str:
    try:
        return repr(value)
    except BaseException:
        return f"<{type(value).__name__} could not be displayed>"


def _collect_moves(
    bots: list[_RuntimeBot],
    grid: list[list[Optional[str]]],
    tick: int,
    timeout_ms: int,
) -> tuple[dict[str, Direction], list[dict[str, str]]]:
    active = [bot for bot in bots if bot.alive]
    jobs: list[tuple[_RuntimeBot, threading.Thread, dict[str, object]]] = []
    for bot in active:
        result: dict[str, object] = {}
        state = _make_state(bot, bots, grid, tick)
        thread = threading.Thread(target=_call_in_thread, args=(bot, state, result), daemon=True)
        jobs.append((bot, thread, result))
        thread.start()

    deadline = time.monotonic() + timeout_ms / 1000.0
    moves: dict[str, Direction] = {}
    events: list[dict[str, str]] = []
    for bot, thread, result in jobs:
        thread.join(max(0.0, deadline - time.monotonic()))
        reason: Optional[str] = None
        kind: Optional[str] = None
        # Anything the bot gets wrong leaves this untouched, so it carries straight on.
        direction: Direction = bot.direction
        if thread.is_alive():
            kind, reason = "timeout", f"exceeded {timeout_ms} ms"
        elif "exception" in result:
            kind, reason = "exception", str(result["exception"])
        else:
            returned = _as_direction(result.get("value"))
            if returned is None:
                kind, reason = "invalid_return", f"returned {_safe_repr(result.get('value'))}"
            else:
                direction = returned

        moves[bot.definition.bot_id] = direction
        if reason is not None and kind is not None:
            event = {"bot_id": bot.definition.bot_id, "bot_name": bot.definition.name, "type": kind, "reason": reason}
            events.append(event)
            print(f"[tick {tick}] {bot.definition.name}: {kind} ({reason}); continuing straight", file=sys.stderr)
    return moves, events


def _frame(tick: int, bots: list[_RuntimeBot], updates: list[dict[str, object]], errors: list[dict[str, str]]) -> dict[str, object]:
    return {
        "tick": tick,
        "bots": [
            {
                "id": bot.definition.bot_id,
                "x": bot.x,
                "y": bot.y,
                "direction": bot.direction,
                "alive": bot.alive,
                "trail_length": bot.trail_length,
            }
            for bot in bots
        ],
        "trail_updates": updates,
        "errors": errors,
    }


def _rank_results(bots: list[_RuntimeBot], capped: bool) -> list[dict[str, object]]:
    def score(bot: _RuntimeBot) -> tuple[int, int]:
        if bot.alive:
            return (2, bot.trail_length if capped else 0)
        return (1, bot.death_tick or 0)

    ordered = sorted(bots, key=score, reverse=True)
    results: list[dict[str, object]] = []
    previous_score: Optional[tuple[int, int]] = None
    place = 0
    for index, bot in enumerate(ordered):
        current_score = score(bot)
        if current_score != previous_score:
            place = index + 1
            previous_score = current_score
        results.append(
            {
                "bot_id": bot.definition.bot_id,
                "name": bot.definition.name,
                "place": place,
                "alive": bot.alive,
                "death_tick": bot.death_tick,
                "trail_length": bot.trail_length,
            }
        )
    return results


def run_match(
    definitions: Iterable[LoadedBot],
    *,
    width: int = 40,
    height: int = 30,
    seed: int = 0,
    tick_cap: int = 2000,
    timeout_ms: int = 100,
    timestamp: Optional[str] = None,
    initial_states: Optional[dict[str, tuple[int, int, str]]] = None,
) -> dict[str, object]:
    """Run one complete headless match and return its JSON-serializable replay."""

    definitions = list(definitions)
    if not 2 <= len(definitions) <= 4:
        raise ValueError("a match requires two to four bots")
    if width < 3 or height < 3 or tick_cap < 1 or timeout_ms < 1:
        raise ValueError("invalid width, height, tick cap, or timeout")
    ids = [bot.bot_id for bot in definitions]
    if len(set(ids)) != len(ids):
        raise ValueError("bot ids must be unique")

    assigned = definitions[:]
    if initial_states is None:
        random.Random(seed).shuffle(assigned)
        starts = _default_starts(width, height, len(assigned))
        start_by_id = {bot.bot_id: start for bot, start in zip(assigned, starts)}
    else:
        if set(initial_states) != set(ids):
            raise ValueError("initial_states must contain every bot id exactly once")
        start_by_id = dict(initial_states)

    bots: list[_RuntimeBot] = []
    grid: list[list[Optional[str]]] = [[None for _ in range(width)] for _ in range(height)]
    initial_updates: list[dict[str, object]] = []
    for definition in assigned:
        x, y, direction = start_by_id[definition.bot_id]
        if direction not in DIRECTIONS or not (0 <= x < width and 0 <= y < height) or grid[y][x] is not None:
            raise ValueError(f"invalid or overlapping start for {definition.bot_id}")
        runtime = _RuntimeBot(definition, x, y, direction)
        bots.append(runtime)
        grid[y][x] = definition.bot_id
        initial_updates.append({"x": x, "y": y, "bot_id": definition.bot_id})

    frames = [_frame(0, bots, initial_updates, [])]
    tick = 0
    while sum(bot.alive for bot in bots) > 1 and tick < tick_cap:
        tick += 1
        moves, errors = _collect_moves(bots, grid, tick, timeout_ms)
        proposals: dict[str, tuple[int, int]] = {}
        deaths: set[str] = set()
        destinations: dict[tuple[int, int], list[str]] = {}

        for bot in bots:
            if not bot.alive:
                continue
            direction = moves[bot.definition.bot_id]
            bot.direction = direction
            dx, dy = DIRECTIONS[direction]
            destination = (bot.x + dx, bot.y + dy)
            proposals[bot.definition.bot_id] = destination
            destinations.setdefault(destination, []).append(bot.definition.bot_id)
            x, y = destination
            if not (0 <= x < width and 0 <= y < height) or grid[y][x] is not None:
                deaths.add(bot.definition.bot_id)

        for contenders in destinations.values():
            if len(contenders) > 1:
                deaths.update(contenders)

        updates: list[dict[str, object]] = []
        for bot in bots:
            if not bot.alive:
                continue
            bot_id = bot.definition.bot_id
            if bot_id in deaths:
                bot.alive = False
                bot.death_tick = tick
                continue
            x, y = proposals[bot_id]
            bot.x, bot.y = x, y
            bot.trail_length += 1
            grid[y][x] = bot_id
            updates.append({"x": x, "y": y, "bot_id": bot_id})
        frames.append(_frame(tick, bots, updates, errors))

    capped = tick >= tick_cap and sum(bot.alive for bot in bots) > 1
    results = _rank_results(bots, capped)
    return {
        "metadata": {
            "format_version": 1,
            "width": width,
            "height": height,
            "seed": seed,
            "tick_cap": tick_cap,
            "move_timeout_ms": timeout_ms,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "bots": [
                {
                    "id": bot.definition.bot_id,
                    "name": bot.definition.name,
                    "color": list(bot.definition.color),
                    "source": bot.definition.source,
                    "start": {"x": start_by_id[bot.definition.bot_id][0], "y": start_by_id[bot.definition.bot_id][1], "direction": start_by_id[bot.definition.bot_id][2]},
                }
                for bot in bots
            ],
        },
        "frames": frames,
        "results": {
            "reason": "tick_cap" if capped else "last_bot_standing",
            "ticks": tick,
            "placements": results,
        },
    }


def write_replay(replay: dict[str, object], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(replay, indent=2) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run one headless Tron bot match.")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--bots", type=Path, default=Path("bots"), help="folder searched recursively for bot files")
    sources.add_argument("--bot-files", type=Path, nargs="+", help="exact bot files for this match")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("logs/match.json"))
    parser.add_argument("--width", type=int, default=40)
    parser.add_argument("--height", type=int, default=30)
    parser.add_argument("--tick-cap", type=int, default=2000)
    parser.add_argument("--timeout-ms", type=int, default=100)
    parser.add_argument("--list-bots", action="store_true", help="print valid bot metadata as JSON, then exit")
    args = parser.parse_args(argv)

    bots = load_bot_files(args.bot_files) if args.bot_files else load_bots(args.bots)
    if args.list_bots:
        print(json.dumps([
            {"id": bot.bot_id, "name": bot.name, "source": bot.source, "color": list(bot.color)}
            for bot in bots
        ]))
        return 0
    if len(bots) < 2:
        location = "the selected files" if args.bot_files else str(args.bots)
        parser.error(f"need at least two valid bots in {location}")
    if len(bots) > 4:
        bots = random.Random(args.seed).sample(bots, 4)
        print("More than four bots found; selected: " + ", ".join(bot.name for bot in bots))
    replay = run_match(bots, width=args.width, height=args.height, seed=args.seed, tick_cap=args.tick_cap, timeout_ms=args.timeout_ms)
    write_replay(replay, args.out)
    print(f"Wrote {args.out}")
    for result in replay["results"]["placements"]:  # type: ignore[index]
        print(f"  {result['place']}. {result['name']} ({result['trail_length']} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
