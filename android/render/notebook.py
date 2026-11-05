"""Render the NOTEBOOK overlay (J): the pilot's own notes."""

import time

from core import state, notebook
from render import ui

W = 72


def _rows(width):
    """[(note index, first line?, text)] with long notes wrapped."""
    out = []
    for i, n in enumerate(notebook.notes()):
        for j, line in enumerate(ui.wrap(n["text"], width) or [""]):
            out.append((i, j == 0, line))
    return out


def draw(console, width, height=ui.MAP_H):
    H = min(46, ui.MAP_H - 2)
    notes = notebook.notes()
    x, y = ui.window(console, W, H, "Pilot's notebook",
                     right_title=f"{len(notes)} notes · galaxy {state.galaxy_seed}")
    ix, iw = x + 3, W - 6
    text_w = iw - 9
    list_h = H - 9

    if notes:
        state.note_index = max(0, min(state.note_index, len(notes) - 1))
    rows = _rows(text_w)
    # keep the selected note in view (newest notes at the bottom)
    sel_rows = [k for k, r in enumerate(rows) if r[0] == state.note_index]
    end = len(rows)
    if sel_rows and sel_rows[0] < end - list_h:
        end = min(len(rows), sel_rows[-1] + 1 + list_h // 3)
    start = max(0, end - list_h)
    if not notes:
        ui.paragraph(console, ix, y + 3, iw,
                     "Nothing written yet. Press ENTER to write a note - prices, "
                     "good trade routes, what a station buys... When docked at a "
                     "market, R writes down all of its prices for you.", fg=ui.DIM)
    for row, (i, first, line) in enumerate(rows[start:end]):
        sel = i == state.note_index and state.note_input is None
        if sel:
            console.draw_rect(ix - 1, y + 2 + row, iw + 2, 1, ord(" "), bg=ui.SEL_BG)
        bg = ui.SEL_BG if sel else None
        if first:
            console.print(ix, y + 2 + row, f"Day {notes[i]['day']:<3}", fg=ui.ACCENT, bg=bg)
        console.print(ix + 9, y + 2 + row, line, fg=ui.SEL_FG if sel else ui.TEXT, bg=bg)
    ui.scrollbar(console, x + W - 2, y + 2, list_h, start, list_h, len(rows), fg=ui.BORDER_HI)

    # --- writing line ----------------------------------------------------------
    ui.hline(console, x, y + H - 6, W, fg=ui.BORDER_HI)
    if state.note_input is not None:
        cursor = "█" if int(time.time() * 2) % 2 == 0 else " "
        text = state.note_input
        shown = text[-(iw - 4):]
        console.print(ix, y + H - 5, "> ", fg=ui.KEY)
        console.print(ix + 2, y + H - 5, shown + cursor, fg=ui.TEXT)
        ui.right(console, ix + iw - 1, y + H - 4, f"{len(text)}/{notebook.MAX_LEN}", fg=ui.FAINT)
        ui.hint_row_centered(console, x + W // 2, y + H - 2,
                             [("type", "Write"), ("ENTER", "Save"), ("ESC", "Cancel")])
        return
    record = notebook.price_record()
    if record:
        ui.text(console, ix, y + H - 5, ui.clip(f"R: note prices at {state.current_location.name}", iw),
                fg=ui.GOOD)
    else:
        ui.text(console, ix, y + H - 5, "Dock at a market and press R to note its prices.",
                fg=ui.FAINT)
    hints = [("ENTER", "New note"), ("↑↓", "Select"), ("DEL", "Delete")]
    if record:
        hints.insert(1, ("R", "Note prices"))
    ui.hint_row_centered(console, x + W // 2, y + H - 3, hints)
    ui.hint_row_centered(console, x + W // 2, y + H - 2, [("J", "Close"), ("ESC", "Close")])
