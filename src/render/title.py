"""Render the TITLE screen."""

import time
import random
from effects.effects import twinkle_color

_title_stars = None

def _init_title_stars(width, height, count=40):
    return [
        {
            "x": random.randint(0, width - 1),
            "y": random.randint(0, height - 1),
            "phase": random.uniform(0, 6.28),
            "color": (random.randint(0, 255),random.randint(0, 255),random.randint(0, 255))
        }
        for _ in range(count)
    ]

def draw(console, width, height, title_text):

    global _title_stars
    if _title_stars is None:
        _title_stars = _init_title_stars(width, height)

    t = time.time()
    for star in _title_stars:
        color = twinkle_color(star["color"], t, speed=2.0, phase=star["phase"])
        console.print(star["x"], star["y"], "*", fg=color)

    console.print(10, 10, title_text)

    prompt = "Press Enter to start a New Game"
    console.print(
        width // 2 - len(prompt) // 2,
        24,
        prompt,
    )