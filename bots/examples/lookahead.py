"""Example 3: count free cells reachable within two steps of each move."""

from arena import Direction, State

NAME = "Two-Step Lookahead"

DIRECTIONS: dict[Direction, tuple[int, int]] = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}


def move(state: State) -> Direction:
    best_direction: Direction = state.direction
    best_score = -1
    for direction, (dx, dy) in DIRECTIONS.items():
        first: tuple[int, int] = (state.x + dx, state.y + dy)
        if not state.is_free(*first):
            continue

        # A set prevents counting the same second-step cell twice.
        reachable: set[tuple[int, int]] = {first}
        for next_dx, next_dy in DIRECTIONS.values():
            second = (first[0] + next_dx, first[1] + next_dy)
            if second != (state.x, state.y) and state.is_free(*second):
                reachable.add(second)
        score = len(reachable)
        # Strict > makes ties deterministic and easy to reproduce.
        if score > best_score:
            best_score = score
            best_direction = direction
    return best_direction
