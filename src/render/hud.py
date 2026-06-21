# render/hud.py

from core import state

def draw(console, width, height):

    if state.game_state in ("GALAXY", "SYSTEM"):
        console.print(
            width - 15,
            height - 1,
            f"Credits: {state.credits}"
        )