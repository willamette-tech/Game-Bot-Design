from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

# The only four values a bot may return, and the only ones it will ever be given.
Direction = Literal["up", "down", "left", "right"]

# How far each direction moves you, as (change in x, change in y).  Iterating this
# walks them clockwise from "up", which is the order the example bots break ties in.
DIRECTIONS: dict[Direction, tuple[int, int]] = {
    "up": (0, -1),      # one row up the screen
    "right": (1, 0),    # one column right
    "down": (0, 1),     # one row down the screen
    "left": (-1, 0),    # one column left
}

# grid[y][x] is None for an empty cell, or the id of the bot whose trail owns it.
Grid = list[list[Optional[str]]]


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
    for this one call, so writing to it—marking cells in ``grid`` while you search,
    say—changes nothing in the real match and cannot disturb another bot.

    ``print(state)`` shows every field except the grid, which is the quickest way to
    see what your bot is looking at.
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
