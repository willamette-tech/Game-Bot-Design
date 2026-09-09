# Tron Light Cycle Bot Arena

A meeting-night tournament system with three deliberately separate programs:

- `arena.py` runs one match headlessly and writes a JSON replay.
- `viewer.py` only plays a replay; it never runs bots or collision rules.
- `tournament.py` schedules matches, scores placements, and prints commentary-friendly statistics.

## Organizer setup

Install Python 3.10 or newer, then install the sole runtime dependency:

```sh
python -m pip install -r requirements.txt
```

Put entrant `.py` files anywhere under `bots/`. Broken imports and files without a callable
`move(state)` are reported and skipped. The four teaching bots in `bots/examples/` are loaded
too, so move that directory elsewhere if they should not compete.

Run a single match and open its replay:

```sh
python arena.py --bots bots/ --seed 42 --out logs/match.json
python viewer.py logs/match.json
```

Run a reproducible tournament (every bot plays once per round):

```sh
python tournament.py --bots bots/ --rounds 3 --seed 42 --headless
```

Tournament mode is headless by default. To open selected matches only after the complete
tournament has finished, pass their 1-based numbers, for example `--replay 1 4 7`.
Useful common flags are `--width`, `--height`, `--tick-cap`, `--timeout-ms`, and `--logs`.

Viewer controls: Space pauses, Left/Right step while paused, R restarts, Up/Down changes
speed, and Escape quits. Playback holds on the final frame.

## Operations notes

Each bot call runs in a daemon thread with a 100 ms default timeout. An exception, timeout,
or invalid direction is logged and printed; that bot continues straight for the tick. Python
cannot safely kill a stuck thread. A bot with a genuinely infinite loop therefore leaks one
daemon thread per turn: remove that bot and restart the arena process after the tournament.

Replay JSON includes metadata, bot colors and starts, full bot snapshots, incremental trail
updates, per-tick errors, and final placements. Runs with the same seed have identical gameplay;
the real UTC `metadata.timestamp` naturally differs. The included reproducibility test fixes it.

Run the standard-library test suite headlessly:

```sh
python -m unittest discover -s tests -v
```
