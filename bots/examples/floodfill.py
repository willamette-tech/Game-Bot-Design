"""Example 4: choose the move leading to the largest connected open region."""

from collections import deque

from arena import Direction, State

NAME = "Flood Fill"

DIRECTIONS: dict[Direction, tuple[int, int]] = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}


def region_size(state: State, start: tuple[int, int]) -> int:
    """Breadth-first search: count all empty cells connected to start."""

    queue: deque[tuple[int, int]] = deque([start])
    visited: set[tuple[int, int]] = {start}
    while queue:
        x, y = queue.popleft()
        for dx, dy in DIRECTIONS.values():
            neighbor = (x + dx, y + dy)
            if neighbor not in visited and state.is_free(*neighbor):
                visited.add(neighbor)
                queue.append(neighbor)
    return len(visited)


def move(state: State) -> Direction:
    best_direction: Direction = state.direction
    best_area = -1
    for direction, (dx, dy) in DIRECTIONS.items():
        destination = (state.x + dx, state.y + dy)
        if state.is_free(*destination):
            area = region_size(state, destination)
            if area > best_area:
                best_area = area
                best_direction = direction
    return best_direction
