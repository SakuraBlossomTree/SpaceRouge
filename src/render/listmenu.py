"""Render the object / ship list menu (core/listmenu.py)."""

from core import state, listmenu
from render import ui

W = 64


def draw(console):
    title, sub, info, items = listmenu.current()
    ix_w = W - 4
    H = 3 + len(info) + 2 + len(items) * 2 + 1 + 4 + 2
    ui.dim_console(console, 0.35)
    x, y = ui.window(console, W, H, title, right_title="S")
    ix = x + 2
    cy = y + 1
    if sub:
        ui.text(console, ix, cy, sub, fg=ui.DIM)
    cy += 2
    for label, value in info:
        ui.kv(console, ix, cy, ix_w, label, value)
        cy += 1
    cy += 1
    ui.text(console, ix, cy, "WHAT DO YOU WANT TO DO?", fg=ui.TITLE)
    cy += 1
    sel = state.list_menu_index % max(1, len(items))
    for i, it in enumerate(items):
        selected = i == sel
        ui.menu_row(console, ix - 1, cy, ix_w + 1, it["label"], selected=selected,
                    key=str(i + 1), enabled=it["enabled"], suffix=it["note"])
        tag = f"[{it['key']}]"
        console.print(x + W - 2 - len(tag), cy + 1, tag,
                      fg=ui.KEY if it["enabled"] else ui.FAINT)
        cy += 2
    cy += 1
    ui.hline(console, x, cy - 1, W)
    if items:
        ui.paragraph(console, ix, cy, ix_w, items[sel]["detail"], fg=ui.TEXT, max_lines=3)
    ui.hint_row_centered(console, x + W // 2, y + H - 1,
                         [("↑↓", "Select"), ("1-9", "Pick"), ("ENTER", "Do it"), ("ESC", "Close")])
