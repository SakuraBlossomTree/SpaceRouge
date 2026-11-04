"""Render the EXCHANGE overlay: the galactic stock market and trade routes.

Tabs: Overview, Companies, Routes, Commodities. Data comes from
core.economy (state.economy).
"""

from core import state
from core.world import COMMODITIES
from render import ui

W, H = 78, 58
TABS = ["Overview", "Companies", "Routes", "Commodities"]

NEWS_FG = {"good": ui.GOOD, "bad": ui.BAD, "info": ui.ACCENT}


def _change(hist, days):
    if len(hist) <= days or not hist[-1 - days]:
        return 0.0
    return hist[-1] / hist[-1 - days] - 1


def _pct_cell(console, rx, y, v, bg=None):
    ui.right(console, rx, y, ui.pct(v), fg=ui.pct_color(v), bg=bg)


def tab_count(tab):
    ec = state.economy
    if ec is None:
        return 0
    return [len(ec.corporations), len(ec.companies), len(ec.top_routes(18)), len(COMMODITIES)][tab]


# ---------------------------------------------------------------------------

def _overview(console, ec, x, y, ix, iw, bottom):
    comp = ec.composite
    ui.text(console, ix, y, "GALACTIC COMPOSITE", fg=ui.TITLE)
    ui.text(console, ix + 20, y, f"{comp[-1]:,.1f}", fg=ui.KEY)
    cx = ix + 32
    for label, days in (("1d", 1), ("7d", 7), ("30d", 30)):
        v = _change(comp, days)
        ui.text(console, cx, y, label, fg=ui.DIM)
        ui.text(console, cx + len(label) + 1, y, ui.pct(v), fg=ui.pct_color(v))
        cx += len(label) + 10
    ui.chart(console, ix, y + 2, iw, 11, comp, min_span=0.06)
    ui.text(console, ix, y + 13, f"last {min(len(comp), iw - 8)} days", fg=ui.FAINT)

    # corporations
    ty = y + 15
    ui.hline(console, x, ty - 1, W, fg=ui.BORDER_HI)
    heads = [(ix, "CORPORATION"), (ix + 30, "INDEX"), (ix + 39, "1D"), (ix + 47, "7D"),
             (ix + 52, "30 DAYS")]
    for hx, label in heads:
        ui.text(console, hx, ty, label, fg=ui.DIM)
    sel = min(state.exchange_index, len(ec.corporations) - 1)
    for i, corp in enumerate(ec.corporations):
        ry = ty + 1 + i * 2
        bg = ui.SEL_BG if i == sel else None
        if bg:
            console.draw_rect(ix - 1, ry, iw + 2, 2, ord(" "), bg=bg)
        ui.text(console, ix, ry, corp.ticker, fg=ui.KEY, bg=bg)
        ui.text(console, ix + 5, ry, ui.clip(corp.name, 24), fg=ui.TEXT, bg=bg)
        ui.text(console, ix + 5, ry + 1,
                ui.clip(" · ".join(c.ticker for c in corp.companies), 24), fg=ui.DIM, bg=bg)
        ui.right(console, ix + 35, ry, f"{corp.index:.1f}", fg=ui.TEXT, bg=bg)
        _pct_cell(console, ix + 42, ry, _change(corp.history, 1), bg)
        _pct_cell(console, ix + 50, ry, _change(corp.history, 7), bg)
        ui.spark(console, ix + 52, ry, iw - 52, corp.history[-30:], bg=bg)

    # news
    ny = ty + 2 + len(ec.corporations) * 2
    ui.hline(console, x, ny - 1, W, fg=ui.BORDER_HI)
    ui.text(console, ix, ny, "DAY   NEWSWIRE", fg=ui.DIM)
    rows = bottom - ny - 1
    for i, (day, text, kind) in enumerate(reversed(ec.news[-rows:])):
        ui.right(console, ix + 3, ny + 1 + i, str(day), fg=ui.FAINT)
        ui.text(console, ix + 6, ny + 1 + i, ui.clip(text, iw - 6), fg=NEWS_FG.get(kind, ui.TEXT))


def _companies(console, ec, x, y, ix, iw, bottom):
    comps = ec.companies
    sel = min(state.exchange_index, len(comps) - 1)
    lw = 30
    ui.text(console, ix, y, "TICKER  PRICE      7D", fg=ui.DIM)
    for i, c in enumerate(comps):
        ry = y + 1 + i
        if ry >= bottom:
            break
        on = i == sel
        bg = ui.SEL_BG if on else None
        if on:
            console.draw_rect(ix - 1, ry, lw, 1, ord(" "), bg=bg)
        ui.text(console, ix, ry, c.ticker, fg=ui.KEY, bg=bg)
        ui.right(console, ix + 14, ry, f"{c.price:,.2f}", fg=ui.SEL_FG if on else ui.TEXT, bg=bg)
        _pct_cell(console, ix + 22, ry, c.change(7), bg)
        ui.text(console, ix + 24, ry, c.corp.ticker, fg=ui.FAINT, bg=bg)

    dx = ix + lw + 1
    for i in range(y - 1, bottom):
        console.print(dx - 1, i, "│", fg=ui.BORDER)
    c = comps[sel]
    rw = ix + iw - dx
    ui.text(console, dx + 1, y, ui.clip(c.name.upper(), rw - 8), fg=ui.TITLE)
    ui.right(console, dx + rw - 1, y, c.ticker, fg=ui.KEY)
    ui.text(console, dx + 1, y + 1, ui.clip(f"{c.sector} · {c.corp.name}", rw - 2), fg=ui.DIM)

    ui.text(console, dx + 1, y + 3, f"{c.price:,.2f} cr", fg=ui.KEY)
    cx = dx + 14
    for label, days in (("1d", 1), ("7d", 7), ("30d", 30)):
        v = c.change(days)
        ui.text(console, cx, y + 3, label, fg=ui.DIM)
        ui.text(console, cx + len(label) + 1, y + 3, ui.pct(v), fg=ui.pct_color(v))
        cx += len(label) + 9
    ui.chart(console, dx + 1, y + 5, rw - 1, 13, c.history)
    recent = c.history[-30:]
    ui.kv(console, dx + 1, y + 19, rw - 2, "30-day range", f"{min(recent):,.2f} - {max(recent):,.2f}")

    ui.text(console, dx + 1, y + 21, "REVENUE (daily)", fg=ui.DIM)
    ui.spark(console, dx + 1, y + 22, rw - 2, c.rev_hist[-40:], fg=ui.ACCENT)
    goods = ", ".join(c.goods) if c.goods else "freight on any route"
    ui.kv(console, dx + 1, y + 25, rw - 2, "Trades", ui.clip(goods, rw - 10))
    ui.kv(console, dx + 1, y + 26, rw - 2, "Home systems", ui.clip(", ".join(c.homes[:3]) or "-", rw - 16))

    ui.text(console, dx + 1, y + 28, f"FLEET · {len(c.fleet)} ships", fg=ui.DIM)
    fy = y + 29
    for t in c.fleet:
        if fy >= bottom:
            break
        if t.cargo:
            good, qty = t.cargo[0], t.cargo[1]
            dest = t.cargo[3].system
            status = f"{qty} {good} → {dest}"
            fg = ui.TEXT
        elif t.path:
            status, fg = f"repositioning → {t.path[-1]}", ui.DIM
        else:
            status, fg = f"docked at {t.system}", ui.DIM
        ui.text(console, dx + 1, fy, ui.clip(t.name, 16), fg=ui.ACCENT)
        ui.text(console, dx + 18, fy, ui.clip(status, rw - 19), fg=fg)
        fy += 1


def _routes(console, ec, x, y, ix, iw, bottom):
    routes = ec.top_routes(18)
    pirate = ec._pirate_edges()
    ui.text(console, ix, y, "BUSIEST TRADE ROUTES (last 7 days)", fg=ui.DIM)
    heads = [(ix, "ROUTE"), (ix + 36, "MAIN CARGO"), (ix + 51, "VOLUME"), (ix + 69, "SHIPS")]
    for hx, label in heads:
        ui.text(console, hx, y + 2, label, fg=ui.DIM)
    if not routes:
        ui.text(console, ix, y + 4, "No traffic yet.", fg=ui.DIM)
        return
    top = routes[0][0]
    sel = min(state.exchange_index, len(routes) - 1)
    here = state.current_system.name if state.current_system else None
    for i, (vol, edge, good) in enumerate(routes):
        ry = y + 3 + i
        on = i == sel
        bg = ui.SEL_BG if on else None
        if on:
            console.draw_rect(ix - 1, ry, iw + 2, 1, ord(" "), bg=bg)
        name = f"{edge[0]} ↔ {edge[1]}"
        fg = ui.PLAYER if here in edge else (ui.SEL_FG if on else ui.TEXT)
        ui.text(console, ix, ry, ui.clip(name, 33), fg=fg, bg=bg)
        if frozenset(edge) in pirate:
            ui.text(console, ix + 33, ry, "‼", fg=ui.BAD, bg=bg)
        ui.text(console, ix + 36, ry, ui.clip(good, 14), fg=ui.ACCENT, bg=bg)
        ui.bar(console, ix + 51, ry, 10, vol, top, ui.KEY, bg=bg)
        ui.right(console, ix + 66, ry, f"{vol:,.0f}", fg=ui.DIM, bg=bg)
        ui.right(console, ix + 73, ry, str(ec.ships_on(edge)), fg=ui.TEXT, bg=bg)

    sy = y + 4 + len(routes)
    ui.hline(console, x, sy, W, fg=ui.BORDER_HI)
    loaded = sum(1 for t in ec.traders if t.cargo)
    moving = sum(1 for t in ec.traders if t.path)
    total7 = sum(sum(w) for w in ec.traffic.values())
    ui.text(console, ix, sy + 1, "FLEETS", fg=ui.DIM)
    ui.kv(console, ix, sy + 2, 34, "NPC traders", len(ec.traders))
    ui.kv(console, ix, sy + 3, 34, "Carrying cargo", loaded)
    ui.kv(console, ix, sy + 4, 34, "In transit", moving)
    ui.kv(console, ix + 40, sy + 2, iw - 40, "Cargo moved (7d)", f"{total7:,.0f} u")
    ui.kv(console, ix + 40, sy + 3, iw - 40, "Pirate-hit routes", len(pirate),
          value_fg=ui.BAD if pirate else ui.DIM)
    ui.text(console, ix, sy + 6, "Busy routes mean big price swings at both ends.", fg=ui.FAINT)
    ui.text(console, ix, sy + 7, "‼ = pirates on the route; traders avoid it.", fg=ui.FAINT)
    if here:
        ui.text(console, ix, sy + 8, "Routes touching your system are highlighted.", fg=ui.FAINT)


def _commodities(console, ec, x, y, ix, iw, bottom):
    sel = min(state.exchange_index, len(COMMODITIES) - 1)
    heads = [(ix, "GOOD"), (ix + 15, "AVG"), (ix + 22, "7D"),
             (ix + 29, "CHEAPEST ▼ / DEAREST ▲  (system)")]
    for hx, label in heads:
        ui.text(console, hx, y, label, fg=ui.DIM)
    for i, c in enumerate(COMMODITIES):
        ry = y + 1 + i * 2
        on = i == sel
        bg = ui.SEL_BG if on else None
        if on:
            console.draw_rect(ix - 1, ry, iw + 2, 2, ord(" "), bg=bg)
        hist = ec.avg_history[c]
        ui.text(console, ix, ry, c, fg=ui.SEL_FG if on else ui.TEXT, bg=bg)
        ui.right(console, ix + 18, ry, f"{hist[-1]:.1f}", fg=ui.KEY, bg=bg)
        _pct_cell(console, ix + 27, ry, _change(hist, 7), bg)
        lo, hi = ec.price_extremes(c)
        if lo:
            # "Nova Outpost (Kappa Minor)": the planet/station, then its system
            name_w = iw - 38
            for row, (price, ms), arrow, fg in ((0, lo, "▼", ui.GOOD), (1, hi, "▲", ui.WARN)):
                ui.text(console, ix + 29, ry + row, f"{arrow} {price:>3} cr", fg=fg, bg=bg)
                where = f"{ms.name} ({ms.system})"
                ui.text(console, ix + 38, ry + row, ui.clip(where, name_w),
                        fg=ui.TEXT if on else ui.DIM, bg=bg)

    c = COMMODITIES[sel]
    cy = y + 2 + len(COMMODITIES) * 2
    ui.hline(console, x, cy, W, fg=ui.BORDER_HI)
    ui.text(console, ix, cy + 1, f"{c.upper()} · GALAXY AVERAGE PRICE", fg=ui.TITLE)
    ch = max(3, min(10, bottom - cy - 8))
    ui.chart(console, ix, cy + 3, iw, ch, ec.avg_history[c], min_span=0.25)
    cy += ch - 10
    lo, hi = ec.price_extremes(c)
    if lo:
        ui.text(console, ix, cy + 14,
                ui.clip(f"Buy at {lo[1].name} ({lo[1].system}) for {lo[0]}, "
                        f"sell at {hi[1].name} ({hi[1].system}) for {hi[0]}.", iw), fg=ui.TEXT)
    ms = ec.market_for(state.current_location) if state.game_state != "SYSTEM" else None
    if ms and c in ms.market:
        ui.text(console, ix, cy + 15, f"Here at {ms.name}: {ms.market[c]} cr", fg=ui.ACCENT)


def draw(console, width, height=ui.MAP_H):
    H = min(58, ui.MAP_H - 2)        # fits shorter (mobile) screens
    ec = state.economy
    x, y = ui.window(console, W, H, "Galactic Exchange",
                     right_title=f"day {state.day}")
    ix, iw = x + 3, W - 6
    if ec is None:
        ui.center(console, x + W // 2, y + H // 2, "The exchange is offline.", fg=ui.DIM)
        return

    tab = state.exchange_tab % len(TABS)
    tx = ix
    for i, t in enumerate(TABS):
        label = f" {i + 1} {t} "
        on = i == tab
        ui.text(console, tx, y + 2, label, fg=(0, 0, 0) if on else ui.DIM,
                bg=ui.ACCENT if on else None)
        tx += len(label) + 1
    ui.hline(console, x, y + 3, W, fg=ui.BORDER_HI)

    body = (_overview, _companies, _routes, _commodities)[tab]
    body(console, ec, x, y + 5, ix, iw, y + H - 3)

    hints = [("←→", "Tab"), ("↑↓", "Select"), ("E", "Close")]
    if state.DEBUG:
        hints.append(("F", "+1 day"))
    ui.hint_row_centered(console, x + W // 2, y + H - 2, hints)
