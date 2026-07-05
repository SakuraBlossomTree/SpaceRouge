"""Render the GALAXY screen (twinkling stars, player marker)."""

import time
import math

from core import state, look
from effects.effects import twinkle_color
from core.world import STAR_TYPES

def draw(console, width, height, stars):

    look_object = None

    center_x = width // 2
    center_y = height // 2

    angle = time.time()  * 0.05

    t = time.time()

    # Draw jump point connections in debug mode
    if state.DEBUG:
        star_map = {star.name: star for star in stars}
        drawn_pairs = set()

        for star in stars:
            for jp in star.system.jump_points:
                pair = tuple(sorted([star.name, jp.destination]))
                if pair in drawn_pairs:
                    continue
                drawn_pairs.add(pair)

                dest = star_map.get(jp.destination)
                if not dest:
                    continue

                # Draw a simple line between the two stars
                x0, y0 = star.x, star.y
                x1, y1 = dest.x, dest.y

                dx = abs(x1 - x0)
                dy = abs(y1 - y0)
                sx = 1 if x0 < x1 else -1
                sy = 1 if y0 < y1 else -1
                err = dx - dy

                x, y = x0, y0
                while True:
                    if (x, y) != (x0, y0) and (x, y) != (x1, y1):
                        console.print(x, y, ".", fg=(80, 80, 80))
                    if x == x1 and y == y1:
                        break
                    e2 = err * 2
                    if e2 > -dy:
                        err -= dy
                        x += sx
                    if e2 < dx:
                        err += dx
                        y += sy

    for i, star in enumerate(stars):

        # Skip drawing stars over the hud in the galaxy screen (Temparary fix)
        
        if star.x > width - 20 and star.y > height - 8:
            continue

        base_color = STAR_TYPES[star.type]["color"]
        color = twinkle_color(base_color, t, speed=5.0, phase=i * 1.3)
        console.print(star.x, star.y, "*", fg=color)

        """the commented code is for the movement of the stars, since we have implemented the advancement of day, we can later add star movement if we want in the game"""

        # dx = star.x - center_x
        # dy = star.y - center_y

        # draw_x = int(center_x + dx * math.cos(angle) - dy * math.sin(angle))

        # draw_y = int(center_y + dx * math.sin(angle) + dy * math.cos(angle))

        # console.print(draw_x, draw_y, "*", fg=color)

        if state.player_x == star.x and state.player_y == star.y:
            state.current_star = star
        look_object = look.check(star, look_object)

    if state.current_star:
        console.print(state.current_star.x, state.current_star.y, "@", fg=(255, 255, 255))

        console.print(1, height - 1, f"System: {state.current_star.name}")

    if state.look_mode:
        look.draw_result(console, height, look_object)