"""Render the quick menu (SPACE): a list of every screen and place."""

from core import state, quickmenu
from render import ui

W = 50


def draw(console):
    sections = quickmenu.build()
    rows = sum(len(items) + 2 for _, items in sections)
    H = rows + 4
    ui.dim_console(console, 0.35)
    x, y = ui.window(console, W, H, "Go to", right_title="SPACE")
    ix, iw = x + 2, W - 4
    cy = y + 2
    i = 0
    sel = state.quick_index
    for title, items in sections:
        ui.text(console, ix, cy, title.upper(), fg=ui.TITLE)
        cy += 1
        for it in items:
            selected = i == sel
            suffix = it["note"]
            if it["here"]:
                suffix = "you are here"
            key = f"[{it['key']}]" if it["key"] else ""
            label = it["label"]
            ui.menu_row(console, ix - 1, cy, iw - 5, label, selected=selected,
                        enabled=it["enabled"] and not (it["here"] and not selected),
                        suffix=suffix,
                        suffix_fg=ui.ACCENT if it["here"] else None)
            if key:
                console.print(x + W - 2 - len(key), cy, key,
                              fg=ui.KEY if it["enabled"] else ui.FAINT,
                              bg=ui.SEL_BG if selected else None)
            cy += 1
            i += 1
        cy += 1
    ui.hint_row_centered(console, x + W // 2, y + H - 1,
                         [("↑↓", "Select"), ("ENTER", "Go"), ("SPACE/ESC", "Close")])
