"""Example 2: prefer open moves that run beside a wall or trail."""

from bot_api import DIRECTIONS, Direction, State

NAME = "Wall Hugger"

OPPOSITE: dict[Direction, Direction] = {"up": "down", "down": "up", "left": "right", "right": "left"}


def move(state: State) -> Direction:
    # (walls touched, reverse penalty, direction) so the best move sorts highest.
    choices: list[tuple[int, int, Direction]] = []
    for direction, (dx, dy) in DIRECTIONS.items():
        nx, ny = state.x + dx, state.y + dy
        if not state.is_free(nx, ny):
            continue

        # Count blocked neighbors around the destination.  A higher count means
        # the move stays closer to existing trails or the outside wall.
        touching = 0
        for nearby_dx, nearby_dy in DIRECTIONS.values():
            if not state.is_free(nx + nearby_dx, ny + nearby_dy):
                touching += 1
        # Avoid reversing when equally good, because our old head is a trail.
        reverse_penalty = 1 if direction == OPPOSITE[state.direction] else 0
        choices.append((touching, -reverse_penalty, direction))

    if not choices:
        return state.direction
    return max(choices)[2]
