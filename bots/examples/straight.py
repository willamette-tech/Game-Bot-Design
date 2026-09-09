"""Example 1: keep going until the cell ahead is blocked."""

from bot_api import DIRECTIONS, Direction, State

NAME = "Straight Shooter"

# DIRECTIONS maps each direction to the (dx, dy) it moves you; see bot_api.py.
ORDER: list[Direction] = ["up", "right", "down", "left"]


def move(state: State) -> Direction:
    # First try to continue in the current direction.
    dx, dy = DIRECTIONS[state.direction]
    if state.is_free(state.x + dx, state.y + dy):
        return state.direction

    # If blocked, take the first open direction.  This is deliberately naive:
    # it can turn into a tiny pocket and trap itself a moment later.
    for direction in ORDER:
        dx, dy = DIRECTIONS[direction]
        if state.is_free(state.x + dx, state.y + dy):
            return direction
    return state.direction  # No escape; the arena will resolve the crash.
