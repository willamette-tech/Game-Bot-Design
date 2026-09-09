"""Copy this file into bots/ and give it a new filename.

Your bot is one function.  The arena calls ``move(state)`` once per tick and you
return where to go next: ``"up"``, ``"down"``, ``"left"``, or ``"right"``.

Everything you are allowed to look at is on ``state``:

    state.width, state.height : int
        Board size in cells.  Columns are 0 to width - 1, rows are 0 to height - 1.
    state.x, state.y : int
        Your head right now.  x is the column, y is the row, (0, 0) is the top-left.
    state.direction : Direction
        The direction you moved last: "up", "down", "left", or "right".
    state.tick : int
        Which tick this is.  Your first decision is tick 1.
    state.opponents : list[Opponent]
        The other bots.  Each one has .x, .y, .direction, and .alive.
    state.grid : list[list[str | None]]
        The whole board as grid[y][x] (row first): None for an empty cell, or the
        id of the bot whose trail is there.
    state.is_free(x, y) : bool
        True only for a cell that is on the board and empty.  Use this instead of
        indexing the grid yourself, because it does the bounds check for you.

``print(state)`` shows all of it except the grid, which is handy while debugging.
The state is a fresh copy made for your call alone, so changing it changes nothing.

Going up means y - 1 and going down means y + 1, because row 0 is the top row.
"""

from arena import Direction, State

NAME = "My Bot"


def move(state: State) -> Direction:
    """Choose and return a direction."""

    return state.direction
