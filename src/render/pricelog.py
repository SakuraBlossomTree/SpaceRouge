"""Render the PRICELOG overlay (K): what you've paid and been offered."""

from core import state, pricelog
from render import ui

W = 76


def draw(console, width, height=ui.MAP_H):
    H = min(36, ui.MAP_H - 2)
    rows = pricelog.summary()
    seen_count = sum(1 for r in rows if r[1] is not None)
    x, y = ui.window(console, W, H, "Price log",
                     right_title=f"{seen_count}/{len(rows)} goods · galaxy {state.galaxy_seed}")
    ix, iw = x + 3, W - 6

    # column header
    hy = y + 2
    cols = {"good": ix, "lo": ix + 15, "lo_at": ix + 20, "hi": ix + 37,
            "hi_at": ix + 42, "spread": ix + iw - 11, "day": ix + iw - 4}
    ui.text(console, cols["good"], hy, "COMMODITY", fg=ui.DIM)
    ui.text(console, cols["lo"], hy, "LOW", fg=ui.DIM)
    ui.text(console, cols["lo_at"], hy, "AT", fg=ui.DIM)
    ui.text(console, cols["hi"], hy, "HIGH", fg=ui.DIM)
    ui.text(console, cols["hi_at"], hy, "AT", fg=ui.DIM)
    ui.text(console, cols["spread"], hy, "SPREAD", fg=ui.DIM)
    ui.text(console, cols["day"], hy, "SEEN", fg=ui.DIM)
    console.print(ix, hy + 1, "─" * iw, fg=ui.BORDER)

    state.pricelog_index = max(0, min(state.pricelog_index, len(rows) - 1))
    sel = state.pricelog_index

    best_spread = max((r[3] for r in rows if r[1] is not None), default=0)

    for i, (good, lo, hi, spread, _seen, last_day) in enumerate(rows):
        ry = hy + 3 + i
        if i == sel:
            console.draw_rect(ix - 1, ry, iw + 2, 1, ord(" "), bg=ui.SEL_BG)
        bg = ui.SEL_BG if i == sel else None
        fg = ui.SEL_FG if i == sel else ui.TEXT
        ui.text(console, cols["good"], ry, good, fg=fg, bg=bg)
        if lo is None:
            ui.text(console, cols["lo"], ry, "·  unseen", fg=ui.FAINT, bg=bg)
            continue
        ui.text(console, cols["lo"], ry, f"{lo['price']:>3}", fg=ui.GOOD, bg=bg)
        ui.text(console, cols["lo_at"], ry, ui.clip(lo["place"], 16), fg=fg, bg=bg)
        ui.text(console, cols["hi"], ry, f"{hi['price']:>3}", fg=ui.BAD, bg=bg)
        ui.text(console, cols["hi_at"], ry, ui.clip(hi["place"], 16), fg=fg, bg=bg)
        spread_fg = ui.KEY if spread == best_spread and spread > 0 else fg
        ui.text(console, cols["spread"], ry, f"+{spread}" if spread else "—",
                fg=spread_fg, bg=bg)
        ui.text(console, cols["day"], ry, f"d{last_day}", fg=ui.DIM if i != sel else fg, bg=bg)

    # --- details for the selected good ---------------------------------------
    ui.hline(console, x, hy + 3 + len(rows) + 1, W, fg=ui.BORDER_HI)
    good, lo, hi, _spread, _seen, _last = rows[sel]
    dy = hy + 3 + len(rows) + 2
    ui.text(console, ix, dy, good, fg=ui.TITLE)
    if lo is None:
        ui.text(console, ix, dy + 1, "No market seen yet. Dock at a trading post to record its prices.",
                fg=ui.DIM)
    else:
        entries = pricelog.for_good(good)
        max_rows = H - 4 - (hy + 3 + len(rows) + 2 - y)
        for row, e in enumerate(entries[:max_rows]):
            ry = dy + 1 + row
            price_fg = ui.GOOD if e["price"] == lo["price"] else ui.BAD if e["price"] == hi["price"] else ui.TEXT
            console.print(ix, ry, f"{e['price']:>4} cr", fg=price_fg)
            console.print(ix + 10, ry, ui.clip(f"{e['place']} ({e['system']})", iw - 24), fg=ui.TEXT)
            ui.right(console, ix + iw - 1, ry, f"day {e['day']}", fg=ui.DIM)
        if len(entries) > max_rows:
            ui.right(console, ix + iw - 1, dy + max_rows, f"+ {len(entries) - max_rows} more",
                     fg=ui.FAINT)

    ui.hint_row_centered(console, x + W // 2, y + H - 2,
                         [("↑↓", "Select"), ("C", "Clear log"), ("K", "Close"), ("ESC", "Close")])
