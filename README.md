# Light-Cycle Arena Tournament
In today's club meeting we will be having an algorithm-writing tournament. Each of you *(or in teams)* will work to write your own algorithm to survive the longest in the Light-Cycle arena. Game specifications will be below. 

## The Game
This game is based off of the **Tron Light-Cycle** early arcade game. In this game, a number of players move their cycle around the arena, leaving a trail behind them. Any other player who runs into this trail will be killed and eliminated. 
<br>
![Game Overview](https://github.com/willamette-tech/Game-Bot-Design/blob/main/images/overview.png?raw=true)
<br>
The only difference in this case is that instead of manually controlling your cycle, **you will be writing an algorithm that controls it.**
While you can test your algorithm against a set of example ones, at the end of the meeting, we will have a competition between everyone's self-written algorithms.

## Getting Started
Lets first make sure you are able to run the game locally. 

First, clone this repository
```sh
git clone https://github.com/willamette-tech/Game-Bot-Design.git
```

Next, open a terminal in this folder and initialize the Python project
```sh
python -m pip install -r requirements.txt
```

Finally, run
```sh
python viewer.py
```
to open the game-runner application.
<br>
You should see a meny that looks like this:
![Menu Screen](https://github.com/willamette-tech/Game-Bot-Design/blob/main/images/menu.png?raw=true)

<br>
Take a moment to run a couple of the example bots against each other. 

## Writing your own Bot
First create a new file inside the `/bots` directory. Something like `mybot.py` will do.
<br>
Paste the following starter code into this file:
```python
from arena import Direction, State

NAME = "My Very Cool Bot" #You should change this!

def move(state: State) -> Direction:
    if state.is_free(state.x + 1, state.y):
        return "right"
    return "up"
```

Your light cycle moves one grid cell every tick and leaves a permanent trail. Every tick, the arena calls your `move()` function, which in turn must return one of `"up"`, `"down"`, `"left"`, or `"right"`. You crash if you leave the board, hit any trail *(including yours)*, or choose the same new cell as another bot on the same tick. Everyone moves simultaneously and the last bot alive wins; tied crashes share a place.
<br>
The `State` object also contains other useful 

## Testing your Bot
Once again, run
```sh
python viewer.py
```
and select your bot with a couple others to test it against. 