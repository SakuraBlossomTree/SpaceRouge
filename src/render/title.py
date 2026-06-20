"""Render the TITLE screen."""

import time
import random
from effects.effects import twinkle_color

_title_stars = None

TITLE_X = 10
TITLE_Y = 10

def _init_title_stars(width, height, avoid_boxes, count=40):

    stars = []
    attempts = 0
    max_attempts = count * 30

    while len(stars) < count and attempts < max_attempts:
        attempts += 1

        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
    
        if any(_in_box(x, y, box) for box in avoid_boxes):
                continue

        stars.append({
             "x": x,
             "y": y,
             "phase": random.uniform(0, 6.28),
             "color": (random.randint(0, 255),random.randint(0, 255),random.randint(0, 255)),
        })

    return stars

def _text_bounds(text, x, y):
    lines = text.split("\n")
    height = len(lines)
    width = max(len(line) for line in lines) if lines else 0
    return x,y, x + width, y + height

def _in_box(x, y, box):
    bx0, by0, bx1, by1 = box
    return bx0 <= x < bx1 and by0 <= y < by1

def draw(console, width, height, title_text):

    global _title_stars

    prompt = "Press Enter to start a New Game"
    prompt_x = width // 2 - len(prompt) // 2
    prompt_y = 24

    title_box = _text_bounds(title_text, TITLE_X, TITLE_Y)
    prompt_box = _text_bounds(prompt, prompt_x, prompt_y)

    if _title_stars is None:
        _title_stars = _init_title_stars(width, height, avoid_boxes=[title_box, prompt_box])

    t = time.time()
    for star in _title_stars:
        color = twinkle_color(star["color"], t, speed=2.0, phase=star["phase"])
        console.print(star["x"], star["y"], "*", fg=color)

    console.print(TITLE_X, TITLE_Y, title_text)
    console.print(prompt_x, prompt_y, prompt)