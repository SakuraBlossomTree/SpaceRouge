"""Render the STORY screen: typewriter text inside a terminal-style frame."""

import random
import textwrap
import time

from core import state
from render import ui

TEXT_WIDTH = 66
TYPE_SPEED = 0.05  # seconds per revealed character

BOX_W = TEXT_WIDTH + 8
BOX_H = 30

_dust = None


def update(story_text):
    """Advance the typewriter reveal. Call once per frame."""
    if state.story_char_index < len(story_text):
        if time.time() - state.last_story_time > TYPE_SPEED:
            state.story_char_index += 1
            state.last_story_time = time.time()


def draw(console, height, story_text, width=ui.SCREEN_W):
    global _dust
    console.draw_rect(0, 0, width, height, ord(" "), bg=ui.BG)
    if _dust is None:
        rng = random.Random(3)
        _dust = [(rng.randrange(width), rng.randrange(height), rng.randint(25, 60))
                 for _ in range(160)]
    for x, y, b in _dust:
        console.print(x, y, "·", fg=(b, b, int(b * 1.3)), bg=ui.BG)

    bx = (width - BOX_W) // 2
    by = (height - BOX_H) // 2
    total = len(state.story_texts) or 1
    chapter = min(state.story_index + 1, total)
    ui.frame(console, bx, by, BOX_W, BOX_H, "Incoming transmission",
             right_title=f"{chapter}/{total}", bg=(8, 12, 22))

    visible = story_text[: state.story_char_index]
    lines = []
    for para in visible.split("\n"):
        lines.extend(textwrap.wrap(para, TEXT_WIDTH) if para else [""])

    tx, ty = bx + 4, by + 3
    max_lines = BOX_H - 7
    max_top = max(0, len(lines) - max_lines)
    if state.story_follow:
        state.story_scroll = max_top
    state.story_scroll = max(0, min(state.story_scroll, max_top))
    if state.story_scroll >= max_top:
        state.story_follow = True
    top = state.story_scroll
    shown = lines[top:top + max_lines]
    for i, line in enumerate(shown):
        console.print(tx, ty + i, line, fg=(170, 230, 190), bg=(8, 12, 22))

    # Scrollbar on the right edge of the text area.
    ui.scrollbar(console, bx + BOX_W - 4, ty, max_lines, top, max_lines,
                 len(lines), fg=(90, 150, 170), bg=(8, 12, 22))

    still_typing = state.story_char_index < len(story_text)
    if still_typing and state.story_follow and int(time.time() * 2) % 2:
        cx = tx + (len(shown[-1]) if shown else 0)
        cy = ty + max(0, len(shown) - 1)
        console.print(cx, cy, "█", fg=(170, 230, 190), bg=(8, 12, 22))

    # progress bar of the reveal
    ui.bar(console, bx + 4, by + BOX_H - 3, BOX_W - 8,
           state.story_char_index, max(1, len(story_text)), ui.BORDER_HI,
           bg=(8, 12, 22))
    hints = [("SPACE", "Skip")] if still_typing else [("ENTER", "Continue")]
    if len(lines) > max_lines:
        hints.append(("↑/↓", "Scroll"))
    ui.hint_row_centered(console, width // 2, by + BOX_H - 1, hints)
