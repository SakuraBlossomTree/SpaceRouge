"""Draw the tutorial card in the bottom-left of the map viewport."""

import math
import time

from core import state, tutorial
from render import ui

W = 46


def draw(console, corner="bottom-left"):
    if not state.tutorial_active or state.game_state in tutorial.HIDDEN_STATES:
        return
    if state.game_state in ("INVENTORY", "MESSAGES", "MISSION_LOG", "HELP", "EXCHANGE"):
        return
    step = tutorial.current()
    if step is None:
        return
    title, body, kind, _ = step

    lines = ui.wrap(body, W - 4)
    h = len(lines) + 6
    if corner == "top-right":         # classic UI keeps its text at the bottom
        x, y = console.width - W - 2, 5
    elif corner == "top-center":      # mobile: clear of the side controls
        x, y = (console.width - W) // 2, 1
    else:
        x = 1
        y = console.height - h - 2    # leave the bottom row for the galaxy zoom bar

    # border flashes for a moment when a new step appears
    age = time.time() - state.tutorial_step_time
    flash = max(0.0, 1.0 - age / 1.2)
    pulse = 0.5 + 0.5 * math.sin(age * 8)
    border = ui.lerp_color(ui.BORDER_HI, ui.KEY, flash * pulse)

    console.draw_rect(x + 1, y + 1, W, h, ord(" "), bg=(0, 0, 0))
    n, total = state.tutorial_step + 1, len(tutorial.STEPS)
    ui.frame(console, x, y, W, h, "Tutorial", right_title=f"{n}/{total}",
             fg=border, bg=(12, 18, 34), title_fg=ui.KEY)

    ui.text(console, x + 2, y + 1, ui.clip(title.upper(), W - 4), fg=ui.TITLE)
    for i, line in enumerate(lines):
        ui.text(console, x + 2, y + 2 + i, line, fg=ui.TEXT)

    # progress pips
    pips = "".join("■" if i < state.tutorial_step else ("►" if i == state.tutorial_step else "·")
                   for i in range(total))
    ui.text(console, x + 2, y + h - 3, " ".join(pips)[: W - 4], fg=ui.ACCENT)

    hints = [("SPACE", "Continue")] if kind == "info" else []
    hints += [("T", "Hide"), ("H", "Handbook")]
    ui.hint_row(console, x + 2, y + h - 2, hints, bg=(12, 18, 34))
