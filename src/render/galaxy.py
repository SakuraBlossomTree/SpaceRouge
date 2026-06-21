"""Render the GALAXY screen (twinkling stars, player marker)."""

import time
import math

from core import state
from effects.effects import twinkle_color
from core.world import STAR_TYPES, STAR_FRAMES

def draw(console, width, height, stars):

    center_x = width // 2
    center_y = height // 2

    angle = time.time()  * 0.05

    t = time.time()

    for i, star in enumerate(stars):
        frames = STAR_FRAMES[star.type]
        frame = frames[int(time.time() * 4 + i) % len(frames)]
        base_color = STAR_TYPES[star.type]["color"]
        color = twinkle_color(base_color, t, speed=5.0, phase=i * 1.3)
        console.print(star.x, star.y, frame, fg=color)

        # dx = star.x - center_x
        # dy = star.y - center_y

        # draw_x = int(center_x + dx * math.cos(angle) - dy * math.sin(angle))

        # draw_y = int(center_y + dx * math.sin(angle) + dy * math.cos(angle))

        # console.print(draw_x, draw_y, "*", fg=color)

        if state.player_x == star.x and state.player_y == star.y:
            state.current_star = star

    if state.current_star:
        console.print(state.current_star.x, state.current_star.y, "@", fg=(255, 255, 255))

        console.print(1, height - 1, f"System: {state.current_star.name}")