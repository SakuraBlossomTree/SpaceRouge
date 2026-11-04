"""Render the GALAXY screen (classic UI): twinkling stars, player marker.

Same look as the original screen. The galaxy is now bigger than the screen,
so star positions go through core.galaxy_view (scroll + zoom still work).
"""

import time

from core import state, galaxy_view as view
from effects.effects import twinkle_color
from core.world import STAR_TYPES


def _line(console, x0, y0, x1, y1):
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    if dx + dy > 2000:
        return
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        if (x, y) != (x0, y0) and (x, y) != (x1, y1) and view.on_screen(x, y):
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


def draw(console, width, height, stars):
    if state.galaxy_preview:
        from render.galaxy import draw_preview
        star = next((s for s in stars if s.name == state.galaxy_preview), None)
        if star is not None:
            draw_preview(console, width, height, star, stars, card=True)
            return
    t = time.time()
    proj = {star.name: view.project(star.x, star.y) for star in stars}

    # Draw jump point connections in debug mode
    if state.DEBUG:
        drawn_pairs = set()
        for star in stars:
            for jp in star.system.jump_points:
                pair = tuple(sorted([star.name, jp.destination]))
                if pair in drawn_pairs or jp.destination not in proj:
                    continue
                drawn_pairs.add(pair)
                _line(console, *proj[star.name], *proj[jp.destination])

    # Draw jump connections from current system
    if state.current_system and state.current_star:
        for jp in state.current_system.jump_points:
            if jp.destination in proj:
                _line(console, *proj[state.current_star.name], *proj[jp.destination])

    for i, star in enumerate(stars):
        sx, sy = proj[star.name]
        if not view.on_screen(sx, sy):
            continue
        # Skip drawing stars over the hud in the galaxy screen
        if sx > width - 20 and sy > height - 10:
            continue
        base_color = STAR_TYPES[star.type]["color"]
        color = twinkle_color(base_color, t, speed=5.0, phase=i * 1.3)
        console.print(sx, sy, "*", fg=color)

    if state.current_star:
        sx, sy = proj[state.current_star.name]
        if view.on_screen(sx, sy):
            console.print(sx, sy, "@", fg=(255, 255, 255))
        console.print(1, height - 1, f"System: {state.current_star.name}   "
                                     f"[zoom {view.zoom_name()}]  +/- zoom  arrows scroll")

    # --- look mode ---------------------------------------------------------
    state.look_object = None
    if state.look_mode:
        cx, cy = view.project(state.look_x, state.look_y)
        look_object = view.star_at_cell(stars, cx, cy)
        state.look_object = look_object
        if view.on_screen(cx, cy):
            console.print(cx, cy, "X", fg=(255, 255, 0))
        console.print(1, height - 6, "X - Stop looking")
        if look_object is None:
            console.print(1, height - 3, "Looking at: empty space")
        else:
            console.print(1, height - 4, f"Star: {look_object.name}")
            console.print(1, height - 3, f"[{look_object.system.archetype}]")
