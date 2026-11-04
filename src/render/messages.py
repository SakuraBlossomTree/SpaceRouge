"""Render the MESSAGES overlay: the full, scrollable comms log."""

from core import state
from render import ui

W, H = 72, 50


def _lines(width):
    out = []
    for i, msg in enumerate(state.messages):
        wrapped = ui.wrap(msg, width - 6) or [""]
        for j, line in enumerate(wrapped):
            num = f"{i + 1:>3} " if j == 0 else "    "
            out.append((num, line, ui.message_color(msg)))
    return out


def _height():
    return min(50, ui.MAP_H - 2)     # fits shorter (mobile) screens


def max_scroll():
    rows = _height() - 6
    return max(0, len(_lines(W - 6)) - rows)


def draw(console, width, height=ui.MAP_H):
    H = _height()
    x, y = ui.window(console, W, H, "Comms Log",
                     right_title=f"{len(state.messages)} messages")
    ix, iw = x + 3, W - 6
    rows = H - 6

    lines = _lines(iw)
    if not lines:
        ui.center(console, x + W // 2, y + H // 2, "No messages here right now.", fg=ui.DIM)
    else:
        state.message_scroll = max(0, min(state.message_scroll, len(lines) - rows))
        end = len(lines) - state.message_scroll
        start = max(0, end - rows)
        for i, (num, line, fg) in enumerate(lines[start:end]):
            ui.text(console, ix, y + 2 + i, num, fg=ui.FAINT)
            ui.text(console, ix + 4, y + 2 + i, line, fg=fg)
        ui.scrollbar(console, x + W - 2, y + 2, rows, start, rows, len(lines),
                     fg=ui.BORDER_HI)
        if state.message_scroll:
            ui.right(console, x + W - 4, y + H - 3,
                     f"↓ {state.message_scroll} newer lines", fg=ui.KEY)

    ui.hint_row_centered(console, x + W // 2, y + H - 2,
                         [("↑↓", "Scroll"), ("L", "Close"), ("ESC", "Close")])
