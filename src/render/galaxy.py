"""Render the GALAXY screen (twinkling stars, player marker)."""

import time

from core import state
from effects.effects import twinkle_color


def draw(console, width, height, stars):
    console.print(width - 15, height - 1, f"Credits: {state.credits}")

    t = time.time()

    for i, star in enumerate(stars):
        color = twinkle_color((255, 234, 0), t, speed=5.0, phase=i * 1.3)
        console.print(star.x, star.y, "*", fg=color)

        if state.player_x == star.x and state.player_y == star.y:
            state.current_star = star

    if state.current_star:
        console.print(state.current_star.x, state.current_star.y, "@", fg=(255, 255, 255))

        console.print(1, height - 1, f"System: {state.current_star.name}")