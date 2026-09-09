"""Example 1: keep going until the cell ahead is blocked."""

from arena import Direction, State

NAME = "Straight Shooter"

DIRECTIONS: dict[Direction, tuple[int, int]] = {
    "up": (0, -1),
    "right": (1, 0),
    "down": (0, 1),
    "left": (-1, 0),
}
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
