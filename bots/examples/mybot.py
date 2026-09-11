from arena import Direction, State

NAME = "My Very Cool Bot" #You should change this!

def move(state: State) -> Direction:
    if state.is_free(state.x + 1, state.y):
        return "right"
    return "up"