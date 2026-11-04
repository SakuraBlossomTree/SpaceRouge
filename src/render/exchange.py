"""Render the EXCHANGE overlay: nearby market prices and trade information.

The Exchange deliberately has no company, stock or galaxy-wide price data.
A long-range market scanner is required to compare systems; it is a ship
upgrade, not fitted at the start. Without it only the market you are docked
at is visible. With it, markets within core.economy.SCAN_DEPTH jumps are
shown, with each good marked cheap or dear against the regional average.
Flying somewhere new is how you discover new prices.

Tabs: Overview, Markets, Goods, Routes. The last three need the scanner.

TODO: the U key on the Exchange is a temporary debug toggle for the
scanner; replace it with a real purchase/installation path.
"""

from core import state
from core.economy import PRICE_BAND, SCAN_DEPTH, price_band
from core.world import COMMODITIES
from render import ui

W, H = 78, 58
TABS = ["Overview", "Markets", "Goods", "Routes"]
NEWS_FG = {"good": ui.GOOD, "bad": ui.BAD, "info": ui.ACCENT}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _start_system():
    return state.current_system.name if state.current_system else None


def _underlying_state():
    return state.overlay_return or state.game_state


def _docked_location():
    """The planet/station the player is docked at, or None while flying."""
    if _underlying_state() not in ("LOCATION", "MARKET"):
        return None
    return state.current_location


def _docked_market(ec):
    """The market the player is docked at, or None while flying."""
    location = _docked_location()
    if location is None:
        return None
    return ec.market_for(location)


def _selected(index, count):
    if count <= 0:
        return 0
    return max(0, min(index, count - 1))


def _price_text(lo, hi):
    return f"{lo} cr" if lo == hi else f"{lo}-{hi} cr"


def _jumps(n):
    return "0j" if not n else f"{n}j"


def _price_tag(lo, hi, reference):
    """Price-range label and colour against a regional average."""
    if not reference:
        return "-", ui.DIM
    cheap = lo <= reference * (1 - PRICE_BAND)
    dear = hi >= reference * (1 + PRICE_BAND)
    if cheap and dear:
        return "▼▲ mixed", ui.ACCENT
    if cheap:
        return f"▼ {(reference - lo) / reference * 100:.0f}% cheap", ui.GOOD
    if dear:
        return f"▲ {(hi - reference) / reference * 100:.0f}% dear", ui.WARN
    return "fair", ui.DIM


def _best_quotes(markets, good):
    quotes = [(ms.market[good], ms, sname, jumps)
              for jumps, sname, ms in markets if good in ms.market]
    quotes.sort(key=lambda quote: (quote[0], quote[2], quote[1].name))
    return quotes


def tab_count(tab):
    """Rows the UP/DOWN cursor can move through on the current tab."""
    ec = state.economy
    if ec is None or not state.market_scanner:
        return 0
    if tab == 1:
        return len(ec.systems_within(_start_system()))
    if tab == 2:
        return len(COMMODITIES)
    return 0


def _scanner_locked(console, ix, iw, y, bottom, heading, detail):
    """Explain what the missing long-range scanner would unlock."""
    lines = ui.wrap(detail, iw)
    height = 7 + len(lines) + (2 if state.DEBUG else 0)
    top = y + max(0, (bottom - y - height) // 2)
    ui.text(console, ix, top, "LONG-RANGE MARKET SCANNER REQUIRED", fg=ui.WARN)
    ui.text(console, ix, top + 2, heading, fg=ui.TITLE)
    for i, line in enumerate(lines):
        ui.text(console, ix, top + 4 + i, line, fg=ui.TEXT)
    note_y = top + 4 + len(lines) + 1
    ui.text(console, ix, note_y,
            "The Exchange currently shows local prices only.", fg=ui.DIM)
    if state.DEBUG:
        ui.text(console, ix, note_y + 2,
                "DEBUG: press U to install the scanner.", fg=ui.ACCENT)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

def _overview(console, ec, x, y, ix, iw, bottom):
    start = _start_system()
    upgraded = state.market_scanner
    nearby = ec.systems_within(start) if start else {}
    market_count = sum(len(ec.markets_in.get(name, ())) for name in nearby)
    system_markets = len(ec.markets_in.get(start, ())) if start else 0
    docked = _docked_market(ec)
    docked_loc = _docked_location()

    ui.text(console, ix, y, "SYSTEM", fg=ui.DIM)
    ui.text(console, ix + 8, y, start or "unknown", fg=ui.TITLE)
    if start and state.current_system is not None:
        archetype = getattr(state.current_system, "archetype", "")
        if archetype:
            ui.text(console, ix + 10 + len(start), y, f"· {archetype}", fg=ui.DIM)
    ui.right(console, ix + iw - 1, y,
             f"SCAN RANGE {SCAN_DEPTH} JUMPS" if upgraded else "LOCAL FEED",
             fg=ui.ACCENT if upgraded else ui.WARN)

    if docked:
        where = f"Docked at {docked_loc.name if docked_loc else docked.name}"
    elif docked_loc:
        where = f"Docked at {docked_loc.name} · no market here"
    elif start and upgraded:
        where = ("In space · system-wide prices" if system_markets
                 else "In space · no local market")
    elif start:
        where = "In space · dock at a market to see prices"
    else:
        where = "In space"
    ui.text(console, ix, y + 1, where, fg=ui.DIM)
    if upgraded:
        ui.right(console, ix + iw - 1, y + 1,
                 f"{len(nearby)} systems · {market_count} markets", fg=ui.FAINT)

    # --- local prices ------------------------------------------------------
    ty = y + 3
    ui.text(console, ix, ty,
            "LOCAL PRICES" if (docked or not upgraded) else "PRICES IN THIS SYSTEM",
            fg=ui.TITLE)
    if upgraded:
        ui.right(console, ix + 43, ty, "AVG", fg=ui.DIM)
        ui.text(console, ix + iw - 24, ty, "VS REGION", fg=ui.DIM)
    else:
        ui.right(console, ix + 22, ty, "PRICE", fg=ui.DIM)

    region = ec.regional_prices(start) if start and upgraded else {}
    if docked:
        local = {good: [(price, docked)] for good, price in docked.market.items()}
    elif upgraded and start:
        local = ec.system_prices(start)
    else:
        local = {}

    if not local:
        if docked_loc:
            note = f"{docked_loc.name} has no market."
        elif start and upgraded:
            note = "No markets in this system."
        elif start:
            note = "Dock at a market to see its prices."
        else:
            note = "Enter a system to see market prices."
        ui.text(console, ix, ty + 2, note, fg=ui.DIM)
    ry = ty + 2
    for good in COMMODITIES:
        quotes = local.get(good)
        if not quotes:
            continue
        prices = [price for price, _ in quotes]
        lo, hi = min(prices), max(prices)
        ui.text(console, ix, ry, good, fg=ui.TEXT)
        ui.right(console, ix + 22, ry, _price_text(lo, hi), fg=ui.KEY)
        if upgraded:
            reference = region.get(good)
            tag, tag_fg = _price_tag(lo, hi, reference)
            ui.right(console, ix + 43, ry,
                     f"{reference:.1f}" if reference else "-", fg=ui.DIM)
            ui.text(console, ix + iw - 24, ry, tag, fg=tag_fg)
        ry += 1

    # --- best nearby trades / scanner upgrade -------------------------------
    dy = ty + 12
    ui.hline(console, x, dy - 1, W, fg=ui.BORDER_HI)
    if upgraded:
        ui.text(console, ix, dy, "BEST NEARBY TRADES", fg=ui.TITLE)
        ui.right(console, ix + iw - 1, dy, f"within {SCAN_DEPTH} jumps", fg=ui.FAINT)
        ui.text(console, ix, dy + 1, "GOOD", fg=ui.DIM)
        ui.text(console, ix + 14, dy + 1, "BUY", fg=ui.DIM)
        ui.text(console, ix + 35, dy + 1, "SELL", fg=ui.DIM)
        ui.right(console, ix + iw - 1, dy + 1, "GAIN", fg=ui.DIM)

        deals = ec.nearby_trades(start)[:6] if start else []
        if not deals:
            ui.text(console, ix, dy + 3, "No profitable trades in scan range.",
                    fg=ui.DIM)
            ny = dy + 5
        else:
            for i, deal in enumerate(deals):
                line_y = dy + 2 + i
                buy = f"{deal.buy_price} cr {ui.clip(deal.buy_system, 8)} ({_jumps(deal.buy_jumps)})"
                sell = f"{deal.sell_price} cr {ui.clip(deal.sell_system, 8)} ({_jumps(deal.sell_jumps)})"
                gain = f"+{deal.profit} cr {deal.profit / (deal.hops + 1):.1f}/j"
                ui.text(console, ix, line_y, deal.good, fg=ui.TEXT)
                ui.text(console, ix + 14, line_y, buy, fg=ui.GOOD)
                ui.text(console, ix + 35, line_y, sell, fg=ui.WARN)
                ui.right(console, ix + iw - 1, line_y, gain, fg=ui.KEY)
            ny = dy + 2 + len(deals) + 2
    else:
        ui.text(console, ix, dy, "LONG-RANGE MARKET SCANNER", fg=ui.TITLE)
        ui.right(console, ix + iw - 1, dy, "NOT INSTALLED", fg=ui.WARN)
        detail = ("Compare every market within {SCAN_DEPTH} jumps, see which goods are "
                  "cheap or dear, and find the best nearby trade.")
        lines = ui.wrap(detail, iw)
        for i, line in enumerate(lines):
            ui.text(console, ix, dy + 2 + i, line, fg=ui.TEXT)
        ui.text(console, ix, dy + 2 + len(lines) + 1,
                "Dock at a market to see its local prices.", fg=ui.DIM)
        if state.DEBUG:
            ui.text(console, ix, dy + 2 + len(lines) + 2,
                    "DEBUG: press U to install the scanner.", fg=ui.ACCENT)
        ny = dy + 2 + len(lines) + 4

    # --- explanation (anchored to the bottom of the panel) -----------------
    hy = max(ny + 6, bottom - 5)

    # --- market wire -------------------------------------------------------
    ui.hline(console, x, ny - 1, W, fg=ui.BORDER_HI)
    ui.text(console, ix, ny, "MARKET WIRE", fg=ui.TITLE)
    news = list(reversed(ec.trade_news[-5:]))
    if not news:
        ui.text(console, ix, ny + 2, "No market news.", fg=ui.DIM)
    wire_y = ny + 1
    body_w = iw - 7
    for day, text, kind in news:
        if wire_y >= hy - 1:
            break
        age = max(0, state.day - day)
        ui.right(console, ix + 5, wire_y, f"{age}d" if age else "now",
                 fg=ui.FAINT)
        parts = ui.wrap(text, body_w)
        if len(parts) > 2:                       # keep the wire compact
            parts = parts[:2]
            parts[1] = ui.clip(parts[1] + " ...", body_w)
        for part in parts:
            if wire_y >= hy - 1:
                break
            ui.text(console, ix + 7, wire_y, part,
                    fg=NEWS_FG.get(kind, ui.TEXT))
            wire_y += 1
        wire_y += 1                              # blank line between items

    # --- explanation -------------------------------------------------------
    ui.hline(console, x, hy - 1, W, fg=ui.BORDER_HI)
    ui.text(console, ix, hy, "HOW TO READ THIS", fg=ui.TITLE)
    if upgraded:
        ui.text(console, ix, hy + 1,
                ui.clip(f"▼ cheap = at least {PRICE_BAND * 100:.0f}% below the "
                        f"{SCAN_DEPTH}-jump regional average.", iw), fg=ui.DIM)
        ui.text(console, ix, hy + 2,
                ui.clip(f"▲ dear = at least {PRICE_BAND * 100:.0f}% above it. "
                        "Buy low here, sell high there.", iw), fg=ui.DIM)
        ui.text(console, ix, bottom - 1,
                ui.clip(f"Only markets within {SCAN_DEPTH} jumps are shown. Fly on "
                        "to reveal new prices.", iw), fg=ui.FAINT)
    else:
        ui.text(console, ix, hy + 1,
                ui.clip("Local prices are from the market you are docked at.",
                        iw), fg=ui.DIM)
        ui.text(console, ix, hy + 2,
                ui.clip("A long-range scanner compares prices across nearby "
                        "systems.", iw), fg=ui.DIM)
        ui.text(console, ix, bottom - 1,
                ui.clip("No scanner fitted. Only this system's market is "
                        "visible.", iw), fg=ui.FAINT)


def _markets(console, ec, x, y, ix, iw, bottom):
    if not state.market_scanner:
        _scanner_locked(
            console, ix, iw, y, bottom, "NEARBY MARKETS",
            "Scan every market within {SCAN_DEPTH} jumps, compare their prices at a "
            "glance, and see which goods are cheap or dear in each system.")
        return
    start = _start_system()
    systems = sorted((ec.systems_within(start) if start else {}).items(),
                     key=lambda item: (item[1], item[0]))
    if not systems:
        ui.text(console, ix, y, "No nearby market data. Enter a system first.",
                fg=ui.DIM)
        return

    sel = _selected(state.exchange_index, len(systems))
    region = ec.regional_prices(start)

    # --- system list -------------------------------------------------------
    lw = 27
    ui.text(console, ix, y, "NEARBY SYSTEMS", fg=ui.DIM)
    ui.right(console, ix + lw - 7, y, "MKTS", fg=ui.DIM)
    ui.right(console, ix + lw - 1, y, "JUMPS", fg=ui.DIM)
    for i, (name, jumps) in enumerate(systems):
        line_y = y + 2 + i
        if line_y >= bottom:
            break
        on = i == sel
        bg = ui.SEL_BG if on else None
        if on:
            console.draw_rect(ix - 1, line_y, lw + 1, 1, ord(" "), bg=bg)
        fg = ui.PLAYER if jumps == 0 else (ui.SEL_FG if on else ui.TEXT)
        ui.text(console, ix, line_y, "►" if on else " ", fg=ui.KEY, bg=bg)
        ui.text(console, ix + 2, line_y, ui.clip(name, lw - 13), fg=fg, bg=bg)
        ui.right(console, ix + lw - 7, line_y,
                 f"{len(ec.markets_in.get(name, ()))}m", fg=ui.FAINT, bg=bg)
        ui.right(console, ix + lw - 1, line_y, _jumps(jumps), fg=ui.DIM, bg=bg)

    for line_y in range(y - 1, bottom):
        console.print(ix + lw, line_y, "│", fg=ui.BORDER)

    # --- selected system ---------------------------------------------------
    dx = ix + lw + 2
    dw = ix + iw - dx
    sname, jumps = systems[sel]
    markets = ec.markets_in.get(sname, ())
    ui.text(console, dx, y, sname.upper(), fg=ui.TITLE)
    ui.right(console, ix + iw - 1, y,
             "HERE" if jumps == 0 else f"{jumps} JUMP" + ("S" if jumps != 1 else ""),
             fg=ui.ACCENT if jumps == 0 else ui.DIM)
    market_names = ", ".join(ms.name for ms in markets) or "no markets"
    ui.text(console, dx, y + 1,
            ui.clip(f"{len(markets)} market(s): {market_names}", dw), fg=ui.DIM)

    ui.text(console, dx, y + 3, "GOOD", fg=ui.DIM)
    ui.right(console, dx + 23, y + 3, "PRICE", fg=ui.DIM)
    ui.text(console, dx + 27, y + 3, "VS REGION", fg=ui.DIM)

    rows = ec.system_prices(sname)
    row_y = y + 5
    if not rows:
        ui.text(console, dx, row_y, "No market in this system (military).", fg=ui.DIM)
    for good in COMMODITIES:
        quotes = rows.get(good)
        if not quotes or row_y >= bottom:
            continue
        prices = [price for price, _ in quotes]
        lo, hi = min(prices), max(prices)
        tag, tag_fg = _price_tag(lo, hi, region.get(good))
        ui.text(console, dx, row_y, good, fg=ui.TEXT)
        ui.right(console, dx + 23, row_y, _price_text(lo, hi), fg=ui.KEY)
        ui.text(console, dx + 27, row_y, tag, fg=tag_fg)
        row_y += 1

    # --- what each individual market is good for ---------------------------
    sy = row_y + 1
    if markets and sy < bottom - 5:
        console.print(dx, sy - 1, "─" * dw, fg=ui.BORDER)
        ui.text(console, dx, sy, "MARKET BREAKDOWN", fg=ui.TITLE)
        by = sy + 2
        for ms in markets[:5]:
            if by + 2 >= bottom - 2:
                break
            cheap = [good for good in COMMODITIES
                     if good in ms.market and price_band(ms.market[good],
                                                         region.get(good)) < 0]
            dear = [good for good in COMMODITIES
                    if good in ms.market and price_band(ms.market[good],
                                                        region.get(good)) > 0]
            ui.text(console, dx, by, ui.clip(ms.name, dw), fg=ui.ACCENT)
            ui.text(console, dx + 2, by + 1,
                    ui.clip("▼ cheap  " + (", ".join(cheap[:3]) or "-"), dw - 2),
                    fg=ui.GOOD if cheap else ui.FAINT)
            ui.text(console, dx + 2, by + 2,
                    ui.clip("▲ dear   " + (", ".join(dear[:3]) or "-"), dw - 2),
                    fg=ui.WARN if dear else ui.FAINT)
            by += 3
        if len(markets) > 5:
            ui.text(console, dx, by, f"+{len(markets) - 5} more market(s)",
                    fg=ui.FAINT)

    ui.text(console, dx, bottom - 1,
            ui.clip("Ranges cover every market in this system.", dw), fg=ui.FAINT)


def _goods(console, ec, x, y, ix, iw, bottom):
    if not state.market_scanner:
        _scanner_locked(
            console, ix, iw, y, bottom, "GOODS COMPARISON",
            "Compare every trade good across nearby markets: local ranges, "
            "the regional average, and the best place to buy or sell.")
        return
    start = _start_system()
    if not start:
        ui.text(console, ix, y, "No market data. Enter a system first.", fg=ui.DIM)
        return

    sel = _selected(state.exchange_index, len(COMMODITIES))
    region = ec.regional_prices(start)
    local = ec.system_prices(start)
    markets = ec.nearby_markets(start)

    # --- all goods at a glance --------------------------------------------
    ui.text(console, ix, y, "GOOD", fg=ui.DIM)
    ui.right(console, ix + 21, y, "SYSTEM", fg=ui.DIM)
    ui.right(console, ix + 28, y, "REGION", fg=ui.DIM)
    ui.right(console, ix + 34, y, "GAP", fg=ui.DIM)
    ui.text(console, ix + 36, y, "BEST BUY", fg=ui.DIM)
    ui.text(console, ix + 55, y, "BEST SELL", fg=ui.DIM)

    for i, good in enumerate(COMMODITIES):
        line_y = y + 2 + i
        on = i == sel
        bg = ui.SEL_BG if on else None
        if on:
            console.draw_rect(ix - 1, line_y, iw + 2, 1, ord(" "), bg=bg)

        quotes = local.get(good, [])
        if quotes:
            prices = [price for price, _ in quotes]
            here = _price_text(min(prices), max(prices))
        else:
            here = "-"

        all_quotes = _best_quotes(markets, good)
        if all_quotes:
            buy = all_quotes[0]
            buy_text = f"{buy[0]} cr {ui.clip(buy[2], 10)}"
        else:
            buy_text = "-"
        if len(all_quotes) > 1:
            sell = all_quotes[-1]
            sell_text = f"{sell[0]} cr {ui.clip(sell[2], 9)}"
            spread = max(0, sell[0] - buy[0])
        else:
            sell_text = "-"
            spread = 0

        ui.text(console, ix, line_y, good, fg=ui.SEL_FG if on else ui.TEXT, bg=bg)
        ui.right(console, ix + 21, line_y, here, fg=ui.KEY, bg=bg)
        ui.right(console, ix + 28, line_y, f"{region.get(good, 0):.1f}",
                 fg=ui.DIM, bg=bg)
        ui.right(console, ix + 34, line_y, f"+{spread}" if spread else "-",
                 fg=ui.GOOD if spread else ui.FAINT, bg=bg)
        ui.text(console, ix + 36, line_y, ui.clip(buy_text, 18),
                fg=ui.GOOD if all_quotes else ui.FAINT, bg=bg)
        ui.text(console, ix + 55, line_y, ui.clip(sell_text, 17),
                fg=ui.WARN if len(all_quotes) > 1 else ui.FAINT, bg=bg)

    # --- selected good: every nearby market -------------------------------
    dy = y + 12
    ui.hline(console, x, dy - 1, W, fg=ui.BORDER_HI)
    good = COMMODITIES[sel]
    average = region.get(good)
    ui.text(console, ix, dy, f"{good.upper()} · NEARBY MARKETS", fg=ui.TITLE)
    if average:
        ui.right(console, ix + iw - 1, dy, f"REGION AVG {average:.1f} cr",
                 fg=ui.DIM)

    ui.text(console, ix, dy + 2, "SYSTEM", fg=ui.DIM)
    ui.text(console, ix + 20, dy + 2, "MARKET", fg=ui.DIM)
    ui.right(console, ix + 52, dy + 2, "JUMPS", fg=ui.DIM)
    ui.right(console, ix + 59, dy + 2, "PRICE", fg=ui.DIM)
    ui.text(console, ix + 61, dy + 2, "VS REGION", fg=ui.DIM)

    quotes = _best_quotes(markets, good)
    if not quotes:
        ui.text(console, ix, dy + 4, "No nearby market trades this good.", fg=ui.DIM)
        return

    for i, (price, ms, sname, jumps) in enumerate(quotes):
        line_y = dy + 3 + i
        if line_y >= bottom - 3:
            break
        here = sname == start
        fg = ui.PLAYER if here else ui.TEXT
        ui.text(console, ix, line_y, ui.clip(sname, 18), fg=fg)
        ui.text(console, ix + 20, line_y, ui.clip(ms.name, 28), fg=fg)
        ui.right(console, ix + 52, line_y, _jumps(jumps), fg=ui.DIM)
        ui.right(console, ix + 59, line_y, f"{price} cr", fg=ui.KEY)
        band = price_band(price, average)
        tag = ("▼ cheap" if band < 0 else "▲ dear" if band > 0 else "fair")
        tag_fg = ui.GOOD if band < 0 else ui.WARN if band > 0 else ui.DIM
        ui.text(console, ix + 61, line_y, tag, fg=tag_fg)

    best = quotes[0]
    worst = quotes[-1]
    if best[1] is worst[1]:
        line1 = f"Only {best[1].name} ({best[2]}) trades {good} nearby at {best[0]} cr."
        line2 = "Fly within the scan range to compare more markets."
    else:
        line1 = f"Buy {best[1].name} ({best[2]}) at {best[0]} cr."
        line2 = (f"Sell {worst[1].name} ({worst[2]}) at {worst[0]} cr, "
                 f"+{worst[0] - best[0]}/unit.")
    ui.text(console, ix, bottom - 2, ui.clip(line1, iw), fg=ui.TEXT)
    ui.text(console, ix, bottom - 1, ui.clip(line2, iw), fg=ui.TEXT)


def _route_table(console, ec, ix, iw, y, title, routes, bottom):
    """Draw one route table and return the next free y."""
    pirate = ec._pirate_edges()
    ui.text(console, ix, y, title, fg=ui.TITLE)
    ui.text(console, ix, y + 1, "ROUTE", fg=ui.DIM)
    ui.text(console, ix + 35, y + 1, "MAIN CARGO", fg=ui.DIM)
    ui.text(console, ix + 50, y + 1, "VOLUME", fg=ui.DIM)
    ui.right(console, ix + 71, y + 1, "SHIPS", fg=ui.DIM)

    if not routes:
        ui.text(console, ix, y + 2, "No traffic.", fg=ui.DIM)
        return y + 4

    top = max(volume for volume, _, _ in routes) or 1
    here = state.current_system.name if state.current_system else None
    for i, (volume, edge, good) in enumerate(routes):
        line_y = y + 2 + i
        if line_y >= bottom:
            break
        name = f"{edge[0]} ↔ {edge[1]}"
        ui.text(console, ix, line_y, ui.clip(name, 33),
                fg=ui.PLAYER if here in edge else ui.TEXT)
        if frozenset(edge) in pirate:
            ui.text(console, ix + 33, line_y, "‼", fg=ui.BAD)
        ui.text(console, ix + 35, line_y, ui.clip(good, 14), fg=ui.ACCENT)
        ui.bar(console, ix + 50, line_y, 10, volume, top, ui.KEY)
        ui.right(console, ix + 66, line_y, f"{volume:,.0f}", fg=ui.DIM)
        ui.right(console, ix + 71, line_y, str(ec.ships_on(edge)), fg=ui.TEXT)
    return y + 2 + len(routes) + 1


def _routes(console, ec, x, y, ix, iw, bottom):
    if not state.market_scanner:
        _scanner_locked(
            console, ix, iw, y, bottom, "TRADE ROUTES",
            "Track the lanes freighters are using, what they carry, and "
            "where pirates are raiding.")
        return
    start = _start_system()
    near = set(ec.systems_within(start)) if start else set()
    local, remote = [], []
    for volume, edge, good in ec.top_routes(120):
        (local if edge[0] in near or edge[1] in near else remote).append(
            (volume, edge, good))

    shown = _route_table(console, ec, ix, iw, y,
                         "NEARBY TRADE LANES (last 7 days)", local[:12], bottom)
    if not local:
        ui.text(console, ix, y + 2, "No traffic touching your scan range yet.",
                fg=ui.DIM)
        shown = y + 4

    remaining = bottom - shown - 4
    if remote and remaining >= 4:
        ui.hline(console, x, shown, W, fg=ui.BORDER_HI)
        _route_table(console, ec, ix, iw, shown + 1, "BUSIEST ELSEWHERE",
                     remote[:min(12, remaining - 1)], bottom)

    ui.text(console, ix, bottom - 1,
            ui.clip("Volume = units carried over the last 7 days; "
                    "‼ marks pirate raids.", iw), fg=ui.FAINT)


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------

def draw(console, width, height=ui.MAP_H):
    H = min(58, ui.MAP_H - 2)        # fits shorter (mobile) screens
    ec = state.economy
    x, y = ui.window(console, W, H, "Galactic Exchange",
                     right_title=f"day {state.day}")
    ix, iw = x + 3, W - 6
    if ec is None:
        ui.center(console, x + W // 2, y + H // 2, "The exchange is offline.",
                  fg=ui.DIM)
        return

    tab = state.exchange_tab % len(TABS)
    tx = ix
    for i, name in enumerate(TABS):
        label = f" {i + 1} {name} "
        on = i == tab
        ui.text(console, tx, y + 2, label, fg=(0, 0, 0) if on else ui.DIM,
                bg=ui.ACCENT if on else None)
        tx += len(label) + 1
    ui.hline(console, x, y + 3, W, fg=ui.BORDER_HI)

    body = (_overview, _markets, _goods, _routes)[tab]
    body(console, ec, x, y + 5, ix, iw, y + H - 3)

    hints = [("←→", "Tab"), ("E", "Close")]
    if tab in (1, 2) and state.market_scanner:
        hints.insert(1, ("↑↓", "Select"))
    if state.DEBUG:
        hints.extend([("U", "Scanner"), ("F", "+1 day")])
    ui.hint_row_centered(console, x + W // 2, y + H - 2, hints)
