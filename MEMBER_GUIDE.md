# Write a Tron Bot

You only need to hand in **one Python file**. You do not need to install or run anything.
Start by copying `bot_template.py`, rename it, and give the file to the organizer.

To see it in action, put the file in the arena's `bots/` folder (or ask the organizer to),
open the arena, and press **Refresh**. Select your bot and one to three example opponents,
choose **Run Match**, and the replay will start automatically. Change your code, refresh,
and run again. Each practice replay is saved, so you can compare strategies.

## Optional: test on your own computer

If you have a copy of the project, you can use the same practice menu locally:

1. Install Python 3.10 or newer.
2. In the project folder, run `python -m pip install -r requirements.txt`.
3. Put your bot file in `bots/`.
4. Run `python viewer.py`, select your bot and some opponents, then choose **Run Match**.

After changing your code, press **Refresh** in the menu and run another match. You do not
need to run the arena separately—the menu launches the headless match and opens its replay.
If you only want a non-visual check, the organizer can run a headless match with `arena.py`.

## The game

Your light cycle moves one grid cell every tick and leaves a permanent trail. Return one of
`"up"`, `"down"`, `"left"`, or `"right"`. You crash if you leave the board, hit any trail
(including yours), or choose the same new cell as another bot on the same tick. Everyone moves
simultaneously. Last bot alive wins; tied crashes share a place.

Tournament points can also reward area: ask the organizer whether the night is scored on
survival (placement only), coverage (cells your trail claimed), or a balance of the two. Under
coverage scoring a bot that paints a lot of ground still scores well even if it dies early.

## Your function

```python
from arena import Direction, State

NAME = "Ada's Amazing Bot"       # optional

def move(state: State) -> Direction:
    if state.is_free(state.x + 1, state.y):
        return "right"
    return "up"
```

`Direction` is just the four strings `"up"`, `"down"`, `"left"`, and `"right"`, and `State` is
described below. The import and the hints are optional—the arena never checks them—but with
them your editor will autocomplete `state.` and warn you about a typo like `"rihgt"`.

## What is in `state`

The arena calls `move(state)` every tick and hands you a fresh `State`:

| Attribute | Type | What it is |
| --- | --- | --- |
| `state.width`, `state.height` | `int` | Board size. Columns are `0` to `width - 1`, rows `0` to `height - 1`. |
| `state.x`, `state.y` | `int` | Your head. `x` is the column, `y` is the row, `(0, 0)` is the top-left. |
| `state.direction` | `Direction` | The direction you moved last; return it again to keep going straight. |
| `state.tick` | `int` | Which tick this is. Your first decision is tick 1. |
| `state.opponents` | `list[Opponent]` | The other bots, dead ones included. Each has `.x`, `.y`, `.direction`, `.alive`. |
| `state.grid` | `list[list[str \| None]]` | The board as `grid[y][x]`—row first. `None` is an empty cell, otherwise a bot id. |
| `state.is_free(x, y)` | `bool` | True only for a cell that is on the board **and** empty. |

Prefer `state.is_free(x, y)` over reading `state.grid` yourself: it does the bounds check, so
it cannot blow up on a cell just off the edge. Remember that up is `y - 1` and down is `y + 1`,
because row 0 is the top row. `print(state)` shows everything except the grid, which is the
quickest way to see what your bot is looking at.

Your `state` is a private copy made for that one call, so scribbling on it—say, marking cells
in `state.grid` while you search—cannot corrupt the match or another bot.

The easiest useful strategy is: keep going when the next cell is free, otherwise try the
other directions. Stronger ideas include looking several moves ahead, staying away from small
pockets, or flood-filling open space. Study `bots/examples/` in numbered difficulty order.

Your move has 100 milliseconds. If your code crashes, takes too long, or returns something
else, your cycle goes straight for that tick. The match continues, so test spelling and avoid
infinite loops. Standard-library imports are welcome; do not use packages besides pygame (and
there is no reason for a bot to use pygame). Most importantly: make it yours and have fun.
