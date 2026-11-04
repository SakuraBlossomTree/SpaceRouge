"""Render the HYPERSPACE screen: warp streaks + progress, then arrival flash."""

import math
import random
import time

from core import state
from render import ui

_particles = None


def _init(count=170):
    rng = random.Random(11)
    return [(rng.uniform(0, math.tau), rng.uniform(0.3, 1.0), rng.uniform(0, 1))
            for _ in range(count)]


def _glyph(angle):
    # pick a streak character matching the direction from the centre
    a = (math.degrees(angle) + 360) % 180
    if a < 22.5 or a >= 157.5:
        return "─"
    if a < 67.5:
        return "\\"
    if a < 112.5:
        return "│"
    return "/"


def draw(console, width, height):
    global _particles
    if _particles is None:
        _particles = _init()
    t = time.time()
    cx, cy = width / 2, height / 2
    console.draw_rect(0, 0, width, height, ord(" "), bg=(2, 3, 10))

    if not state.hyperspace_complete:
        progress = min(1.0, state.hyperspace_stage / 10)
        speed = 0.35 + progress * 1.6
        max_r = math.hypot(cx, cy * 2)
        for ang, spd, off in _particles:
            r = ((t * spd * speed + off) % 1.0) ** 1.6 * max_r
            tail = 1 + int(progress * 5 * (r / max_r) * 3)
            for k in range(tail):
                rr = r - k * 1.2
                if rr < 2:
                    break
                x = int(cx + math.cos(ang) * rr)
                y = int(cy + math.sin(ang) * rr * 0.5)
                if 0 <= x < width and 0 <= y < height:
                    fade = (1 - k / (tail + 1)) * min(1.0, r / (max_r * 0.4))
                    col = ui.lerp_color((40, 60, 140), (200, 235, 255), fade)
                    console.print(x, y, _glyph(ang) if k else "·", fg=col, bg=(2, 3, 10))

        bw = 40
        bx = (width - bw) // 2
        console.draw_rect(bx - 2, int(cy) - 3, bw + 4, 7, ord(" "), bg=(2, 3, 10))
        ui.center(console, width // 2, int(cy) - 2, "H Y P E R S P A C E", fg=ui.TITLE)
        ui.center(console, width // 2, int(cy),
                  f"{state.pending_origin or '?'}  ►  {state.pending_destination or '?'}",
                  fg=ui.TEXT)
        ui.bar(console, bx, int(cy) + 2, bw, state.hyperspace_stage, 10, ui.ACCENT)
    else:
        el = time.time() - state.hyperspace_complete_timer
        flash = max(0.0, 1.0 - el * 2.5)
        bg = ui.lerp_color((2, 3, 10), (200, 230, 255), flash)
        console.draw_rect(0, 0, width, height, ord(" "), bg=bg)
        ui.center(console, width // 2, int(cy) - 1, "JUMP COMPLETE", fg=ui.GOOD, bg=bg)
        ui.center(console, width // 2, int(cy) + 1,
                  f"Arriving at {state.pending_destination}", fg=ui.TEXT, bg=bg)
