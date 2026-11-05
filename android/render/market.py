"""Render the MARKET screen: a commodity table with buy / sell."""

from collections import Counter

from core import state
from core.entities import ITEMS
from core.world import BASE_PRICES, COMMODITIES, sell_price
from render import ui

W = 66


def market_goods():
    """Commodities this market trades, in the standard order."""
    market = state.current_location.market or {}
    return [c for c in COMMODITIES if c in market]


def draw(console, width, height=ui.MAP_H):
    loc = state.current_location
    if loc is None:
        return
    goods = market_goods()
    held = Counter(item.name for item in state.inventory.items if not item.mission_key)

    rows = max(1, len(goods))
    H = 17 + rows
    x, y = ui.window(console, W, H, f"{loc.name} · Trading Post",
                     right_title=state.current_system.archetype)
    from render.location import station_tabs
    station_tabs(console, x, y - 2, W)
    ix, iw = x + 3, W - 6
    from core import economy
    days = economy.days_to_update()
    ui.right(console, ix + iw - 1, y + 1, f"Prices update in {days} day{'s' if days != 1 else ''}",
             fg=ui.DIM)

    # header
    cols = {"name": ix + 1, "price": ix + 22, "trend": ix + 31,
            "held": ix + 44, "size": ix + 52}
    hy = y + 2
    for key, label in (("name", "COMMODITY"), ("price", "PRICE"),
                       ("trend", "VS GALAXY"), ("held", "HELD"),
                       ("size", "SIZE")):
        ui.text(console, cols[key], hy, label, fg=ui.DIM)
    console.print(ix, hy + 1, "─" * iw, fg=ui.BORDER)

    if not goods:
        ui.text(console, ix + 1, hy + 2, "Nothing for sale here.", fg=ui.DIM)
    state.market_index = min(state.market_index, max(0, len(goods) - 1))

    for i, name in enumerate(goods):
        ry = hy + 2 + i
        sel = i == state.market_index
        bg = ui.SEL_BG if sel else None
        if sel:
            console.draw_rect(ix, ry, iw, 1, ord(" "), bg=ui.SEL_BG)
            console.print(ix, ry, "►", fg=ui.KEY, bg=bg)
        price = loc.market[name]
        ec = state.economy
        base = ec.avg_price(name) if ec else BASE_PRICES.get(name, price)
        diff = (price - base) / base if base else 0
        ms = ec.market_for(loc) if ec else None
        prev = ms.prev.get(name, price) if ms else price
        if diff <= -0.15:
            trend, tfg = f"▼ {abs(diff) * 100:3.0f}% low", ui.GOOD
        elif diff >= 0.15:
            trend, tfg = f"▲ {diff * 100:3.0f}% high", ui.WARN
        else:
            trend, tfg = "  average", ui.DIM
        n = held.get(name, 0)
        ui.text(console, cols["name"], ry, name, fg=ui.SEL_FG if sel else ui.TEXT, bg=bg)
        ui.right(console, cols["price"] + 5, ry, f"{price} cr", fg=ui.KEY, bg=bg)
        if price != prev:
            console.print(cols["price"] + 6, ry, "↑" if price > prev else "↓",
                          fg=ui.WARN if price > prev else ui.GOOD, bg=bg)
        ui.text(console, cols["trend"], ry, trend, fg=tfg, bg=bg)
        ui.right(console, cols["held"] + 3, ry, str(n) if n else "-",
                 fg=ui.TEXT if n else ui.FAINT, bg=bg)
        ui.right(console, cols["size"] + 3, ry, str(ITEMS[name].size), fg=ui.DIM, bg=bg)

    # --- details for the selected good -----------------------------------
    dy = hy + 3 + rows
    console.print(ix, dy, "─" * iw, fg=ui.BORDER)
    if goods:
        name = goods[state.market_index]
        price = loc.market[name]
        size = ITEMS[name].size
        free = state.inventory.free_space()
        can_afford = state.credits // price if price else 0
        can_fit = free // size if size else 0
        can_buy = min(can_afford, can_fit)
        n = held.get(name, 0)

        ui.text(console, ix, dy + 1, name.upper(), fg=ui.TITLE)
        ui.kv(console, ix, dy + 2, 28, "Buy 1 for", f"{price} cr",
              value_fg=ui.GOOD if can_buy else ui.BAD)
        ui.kv(console, ix, dy + 3, 28, "Sell 1 for", f"{sell_price(price)} cr",
              value_fg=ui.GOOD if n else ui.FAINT)
        limit = "cargo full" if can_fit == 0 else ("no credits" if can_afford == 0 else "")
        ui.kv(console, ix, dy + 4, 28, "You can buy", f"{can_buy}" + (f" ({limit})" if limit else ""),
              value_fg=ui.TEXT if can_buy else ui.BAD)

        rx, rw = ix + 33, iw - 33
        ui.kv(console, rx, dy + 1, rw, "Credits", f"{ui.fmt_int(state.credits)} cr",
              value_fg=ui.KEY)
        used, cap = state.inventory.used_space(), state.inventory.space
        ui.kv(console, rx, dy + 2, rw, "Cargo", f"{used}/{cap}")
        ui.bar(console, rx, dy + 3, rw, used, cap,
               ui.ACCENT if used < cap else ui.WARN)
        ui.kv(console, rx, dy + 4, rw, "In hold", f"{n} {name}",
              value_fg=ui.TEXT if n else ui.FAINT)

        # --- profit information ----------------------------------------
        ec = state.economy
        avg = ec.avg_price(name) if ec else BASE_PRICES.get(name, price)
        here_sell = sell_price(price)
        basis = state.cost_basis.get(name)
        cost = basis[1] / basis[0] if basis and basis[0] > 0 and n else None
        ui.kv(console, ix, dy + 6, 28, "Galaxy average", f"{avg:.0f} cr", value_fg=ui.DIM)
        ui.kv(console, rx, dy + 6, rw, "You paid (avg)",
              f"{cost:.0f} cr" if cost is not None else "-",
              value_fg=ui.TEXT if cost is not None else ui.FAINT)
        if cost is not None:
            per = here_sell - cost
            pfg = ui.GOOD if per >= 0 else ui.BAD
            ui.kv(console, ix, dy + 7, 28, "Profit / unit here", f"{per:+.0f} cr", value_fg=pfg)
            ui.kv(console, rx, dy + 7, rw, "Total if sold", f"{per * n:+.0f} cr", value_fg=pfg)
        else:
            ui.kv(console, ix, dy + 7, 28, "Profit / unit here", "-", value_fg=ui.FAINT)

        from core import pricelog
        seen = [e for e in pricelog.for_good(name) if e["place"] != loc.name]
        if seen:
            lo, hi = seen[0], seen[-1]
            gain = sell_price(hi["price"]) - price
            tail = f"{gain:+d}/unit if bought here"
            ui.right(console, ix + iw - 1, dy + 8, tail, fg=ui.GOOD if gain > 0 else ui.BAD)
            ui.text(console, ix, dy + 8, ui.clip(
                f"Sell best: {hi['price']} cr at {hi['place']} ({hi['system']})",
                iw - len(tail) - 2), fg=ui.TEXT)
            ui.text(console, ix, dy + 9, ui.clip(
                f"Buy cheapest: {lo['price']} cr at {lo['place']} ({lo['system']})", iw), fg=ui.TEXT)
        else:
            ui.text(console, ix, dy + 8, "No other markets seen yet - visit more to compare.",
                    fg=ui.FAINT)

    ui.hint_row_centered(console, x + W // 2, y + H - 1,
                         [("↑↓", "Select"), ("→/B", "Buy"), ("←/S", "Sell"),
                          ("TAB", "Next"), ("ESC", "Station")])
