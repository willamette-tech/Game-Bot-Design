from arena import DIRECTIONS, Direction, State, random

NAME = "Binklebot" #You should change this!

grid = [(1,0), (1,1), (0,1), (-1,1), (-1,0), (-1,-1), (0,-1), (1,-1)]

ORDER: list[Direction] = ["up", "right", "down", "left"]

def move(state: State) -> Direction:
    free = []
    for dx, dy in grid:
        if state.is_free(state.x+dx, state.y+dy):
            free.append((dx,dy))

    random_index = random.choice(free)
    if random_index == (0,1):
        return "up"
    elif random_index == (1,0):
        return "right"
    elif random_index == (0,-1):
        return "down"
    elif random_index == (-1,0):
        return "left"

    
