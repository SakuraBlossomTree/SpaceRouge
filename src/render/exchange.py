"""Render the EXCHANGE overlay: the player's market intelligence network.

This is an information screen only.  Buying and selling happen at station
markets; the Exchange shows what the Long-Range System Scanner has recorded.

The economy always has real prices for every market.  The Exchange never
reads them for a system outside the scanner radius: LIVE systems are read
from the economy, STALE systems are read from the player's saved records,
and UNKNOWN systems show no prices at all.

Tabs: Overview, Commodities, Systems, Opportunities, Routes.
"""

from core import market_intel as intel
from core import scanner, shipyard, state
from core.economy import PRICE_BAND
from core.world import COMMODITIES
from render import ui

W, H = 78, 58
TABS = ["Overview", "Commodities", "Systems", "Opportunities", "Routes"]
NEWS_FG = {"good": ui.GOOD, "bad": ui.BAD, "info": ui.ACCENT}
STATUS_FG = {intel.LIVE: ui.GOOD, intel.STALE: ui.WARN, intel.UNKNOWN: ui.FAINT}


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


def _selected(index, count):
    if count <= 0:
        return 0
    return max(0, min(index, count - 1))


def _offset(index, count, height):
    """First visible row for a scrolling list."""
    if count <= height:
        return 0
    return max(0, min(index - height // 2, count - height))


def _jumps(n):
    return "0j" if not n else f"{n}j"


def _day(day):
    return f"day {day}" if day is not None else "never"


def _status_text(status, day=None, short=False):
    if status == intel.UNKNOWN:
        return "UNKNOWN"
    if day is None:
        return status
    return f"{status} d{day}" if short else f"{status} · day {day}"


def _quote_status(quote, key="buy"):
    price = quote[key] if quote else None
    return f"{price} cr" if price is not None else "-"


def _market_label(market):
    return market["name"]


def _system_prices(markets):
    """good -> {'buy_lo', 'buy_hi', 'sell_hi'} across one system's markets."""
    rows = {}
    for good in COMMODITIES:
        buys = [m["buy"][good] for m in markets if good in m["buy"]]
        sells = [m["sell"][good] for m in markets if good in m["sell"]]
        if not buys:
            continue
        rows[good] = {
            "buy_lo": min(buys),
            "buy_hi": max(buys),
            "sell_hi": max(sells) if sells else None,
        }
    return rows


def _price_range(lo, hi):
    return f"{lo}" if lo == hi else f"{lo}-{hi}"


def _scan_range():
    return scanner.range_text()


def _tag_bg(status):
    return None


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

def _overview(console, ec, x, y, ix, iw, bottom):
    start = _start_system()
    summary = intel.overview()
    docked = _docked_location()

    ui.text(console, ix, y, "SYSTEM", fg=ui.DIM)
    ui.text(console, ix + 8, y, start or "unknown", fg=ui.TITLE)
    if start and state.current_system is not None:
        archetype = getattr(state.current_system, "archetype", "")
        if archetype:
            ui.text(console, ix + 10 + len(start), y, f"· {archetype}", fg=ui.DIM)
    ui.right(console, ix + iw - 1, y,
             f"SCANNER {_scan_range().upper()} · {scanner.level_name().upper()}",
             fg=ui.ACCENT)

    if docked:
        where = f"Docked at {docked.name}"
    elif start:
        where = "Remote market intelligence · scanner centred on this system"
    else:
        where = "Enter a system to receive scanner data"
    ui.text(console, ix, y + 1, where, fg=ui.DIM)

    # --- network summary ---------------------------------------------------
    ui.hline(console, x, y + 3, W, fg=ui.BORDER_HI)
    ui.text(console, ix, y + 4, "MARKET INTELLIGENCE NETWORK", fg=ui.TITLE)
    left_x, right_x = ix, ix + 37
    col_w = 32
    ui.kv(console, left_x, y + 5, col_w, "Systems detected",
          f"{summary['detected']} within {_scan_range()}", value_fg=ui.KEY)
    ui.kv(console, left_x, y + 6, col_w, "Recorded systems",
          str(summary["known_systems"]))
    ui.kv(console, left_x, y + 7, col_w, "Market records",
          str(summary["market_records"]))
    ui.kv(console, left_x, y + 8, col_w, "Commodities tracked",
          f"{summary['commodities']} / {len(COMMODITIES)}")
    ui.kv(console, right_x, y + 5, col_w, "LIVE now",
          str(summary["live_systems"]), value_fg=ui.GOOD)
    ui.kv(console, right_x, y + 6, col_w, "STALE records",
          str(summary["stale_systems"]), value_fg=ui.WARN)
    ui.kv(console, right_x, y + 7, col_w, "UNKNOWN",
          str(summary["unknown_systems"]), value_fg=ui.FAINT)
    ui.kv(console, right_x, y + 8, col_w, "Last sweep",
          _day(summary["last_sweep"]), value_fg=ui.DIM)

    # --- current system market --------------------------------------------
    ui.hline(console, x, y + 10, W, fg=ui.BORDER_HI)
    current_status = intel.status(start) if start else intel.UNKNOWN
    ui.text(console, ix, y + 11, "CURRENT SYSTEM MARKET", fg=ui.TITLE)
    ui.right(console, ix + iw - 1, y + 11,
             _status_text(current_status,
                          intel.last_update(start) if start else None),
             fg=STATUS_FG[current_status])

    ui.text(console, ix, y + 12, "COMMODITY", fg=ui.DIM)
    ui.right(console, ix + 36, y + 12, "BUY", fg=ui.DIM)
    ui.right(console, ix + 46, y + 12, "SELL", fg=ui.DIM)
    ui.right(console, ix + iw - 1, y + 12, "MARKETS", fg=ui.DIM)

    markets = intel.system_markets(start) if start else []
    prices = _system_prices(markets)
    row_y = y + 13
    if not prices:
        note = "No markets in this system." if start else "No current system."
        ui.text(console, ix, row_y, note, fg=ui.DIM)
        row_y += 2
    else:
        for good in COMMODITIES:
            if good not in prices:
                continue
            row = prices[good]
            count = sum(1 for m in markets if good in m["buy"])
            ui.text(console, ix, row_y, good, fg=ui.TEXT)
            ui.right(console, ix + 36, row_y,
                     _price_range(row["buy_lo"], row["buy_hi"]), fg=ui.KEY)
            ui.right(console, ix + 46, row_y,
                     str(row["sell_hi"]) if row["sell_hi"] is not None else "-",
                     fg=ui.GOOD)
            ui.right(console, ix + iw - 1, row_y, str(count), fg=ui.FAINT)
            row_y += 1

    # --- scanner upgrade ---------------------------------------------------
    sy = max(row_y + 1, y + 24)
    if sy <= bottom - 7:
        ui.hline(console, x, sy, W, fg=ui.BORDER_HI)
        ui.text(console, ix, sy + 1, "LONG-RANGE SYSTEM SCANNER", fg=ui.TITLE)
        ui.right(console, ix + iw - 1, sy + 1,
                 f"{scanner.level_name()} · {_scan_range()}", fg=ui.ACCENT)
        offer = shipyard.next_offer("scanrange")
        if offer is None:
            ui.text(console, ix, sy + 2,
                    "Fully upgraded: the Exchange can follow markets four jumps out.",
                    fg=ui.DIM)
        else:
            price, desc = offer
            ui.text(console, ix, sy + 2,
                    ui.clip(f"Next: {desc} · {ui.fmt_int(price)} cr at a shipyard.", iw),
                    fg=ui.TEXT)
        ui.text(console, ix, sy + 3,
                "Upgrades extend previews on the galaxy chart too; they never grant jump access.",
                fg=ui.FAINT)

    # --- market wire -------------------------------------------------------
    wire_y = max(sy + 5, bottom - 11)
    if wire_y < bottom - 4:
        ui.hline(console, x, wire_y, W, fg=ui.BORDER_HI)
        ui.text(console, ix, wire_y + 1, "MARKET WIRE", fg=ui.TITLE)
        news = list(reversed(ec.trade_news[-3:]))
        wy = wire_y + 2
        if not news:
            ui.text(console, ix, wy, "No market news.", fg=ui.DIM)
        for day, text, kind in news:
            if wy >= bottom - 5:
                break
            age = max(0, state.day - day)
            ui.right(console, ix + 5, wy, f"{age}d" if age else "now", fg=ui.FAINT)
            ui.text(console, ix + 7, wy, ui.clip(text, iw - 7),
                    fg=NEWS_FG.get(kind, ui.TEXT))
            wy += 1

    # --- status key --------------------------------------------------------
    ui.hline(console, x, bottom - 3, W, fg=ui.BORDER_HI)
    ui.text(console, ix, bottom - 2,
            ui.clip("LIVE = current scanner feed   ·   STALE = last known data   ·   "
                    "UNKNOWN = no record", iw), fg=ui.DIM)
    ui.text(console, ix, bottom - 1,
            ui.clip("The economy keeps moving outside scanner range. Stale prices are "
                    "never presented as current.", iw), fg=ui.FAINT)


# ---------------------------------------------------------------------------
# Commodities
# ---------------------------------------------------------------------------

def _commodities(console, ec, x, y, ix, iw, bottom):
    start = _start_system()
    table = intel.commodity_table()
    sel = _selected(state.exchange_index, len(table))

    ui.text(console, ix, y, "COMMODITY", fg=ui.DIM)
    ui.text(console, ix + 13, y, "CHEAPEST BUY", fg=ui.DIM)
    ui.text(console, ix + 39, y, "BEST SELL", fg=ui.DIM)
    ui.right(console, ix + iw - 1, y, "SPREAD", fg=ui.DIM)

    for i, row in enumerate(table):
        line_y = y + 2 + i
        on = i == sel
        bg = ui.SEL_BG if on else None
        if on:
            console.draw_rect(ix - 1, line_y, iw + 2, 1, ord(" "), bg=bg)

        cheap = row["cheapest"]
        sell = row["best_sell"]
        if cheap:
            cheap_text = f"[{'L' if cheap['status'] == intel.LIVE else 'S'}] {cheap['buy']} cr {cheap['system']}"
            cheap_fg = STATUS_FG[cheap["status"]]
        else:
            cheap_text, cheap_fg = "-", ui.FAINT
        if sell:
            sell_text = f"[{'L' if sell['status'] == intel.LIVE else 'S'}] {sell['sell']} cr {sell['system']}"
            sell_fg = STATUS_FG[sell["status"]]
        else:
            sell_text, sell_fg = "-", ui.FAINT

        ui.text(console, ix, line_y, row["good"],
                fg=ui.SEL_FG if on else ui.TEXT, bg=bg)
        ui.text(console, ix + 13, line_y, ui.clip(cheap_text, 24),
                fg=cheap_fg, bg=bg)
        ui.text(console, ix + 39, line_y, ui.clip(sell_text, 24),
                fg=sell_fg, bg=bg)
        ui.right(console, ix + iw - 1, line_y,
                 f"+{row['spread']}" if row["spread"] else "-",
                 fg=ui.GOOD if row["spread"] else ui.FAINT, bg=bg)

    # --- selected commodity ------------------------------------------------
    dy = y + 11
    ui.hline(console, x, dy, W, fg=ui.BORDER_HI)
    row = table[sel]
    good = row["good"]
    ui.text(console, ix, dy + 1, f"{good.upper()} · KNOWN MARKET QUOTES",
            fg=ui.TITLE)
    cheap = row["cheapest"]
    dearest = row["dearest"]
    sell = row["best_sell"]
    quotes = intel.commodity_quotes(good)
    average = intel.known_average(good)
    parts = []
    if cheap:
        parts.append(f"cheapest {cheap['buy']} cr {cheap['system']}")
    if dearest:
        parts.append(f"dearest {dearest['buy']} cr {dearest['system']}")
    if sell:
        parts.append(f"best sell {sell['sell']} cr {sell['system']}")
    if average is not None:
        parts.append(f"avg {average:.0f} cr")
    if parts:
        ui.right(console, ix + iw - 1, dy + 1,
                 ui.clip(" · ".join(parts), iw - 28), fg=ui.DIM)

    ui.text(console, ix, dy + 3, "SYSTEM", fg=ui.DIM)
    ui.text(console, ix + 18, dy + 3, "MARKET", fg=ui.DIM)
    ui.right(console, ix + 47, dy + 3, "BUY", fg=ui.DIM)
    ui.right(console, ix + 55, dy + 3, "SELL", fg=ui.DIM)
    ui.text(console, ix + 58, dy + 3, "STATUS", fg=ui.DIM)
    ui.right(console, ix + iw - 1, dy + 3, "UPDATED", fg=ui.DIM)

    if not quotes:
        ui.text(console, ix, dy + 5,
                "No known market trades this commodity yet.", fg=ui.DIM)
    shown = 0
    for quote in quotes:
        line_y = dy + 4 + shown
        if line_y >= bottom - 2:
            break
        here = quote["system"] == start
        fg = ui.PLAYER if here else ui.TEXT
        ui.text(console, ix, line_y, ui.clip(quote["system"], 17), fg=fg)
        ui.text(console, ix + 18, line_y, ui.clip(quote["market"], 27), fg=fg)
        marker = ""
        if quote["buy"] is not None and average is not None:
            if quote["buy"] < average * (1 - PRICE_BAND):
                marker = "▼ "
            elif quote["buy"] > average * (1 + PRICE_BAND):
                marker = "▲ "
        ui.right(console, ix + 47, line_y,
                 marker + _quote_status(quote, "buy"), fg=ui.KEY)
        ui.right(console, ix + 55, line_y, _quote_status(quote, "sell"), fg=ui.GOOD)
        ui.text(console, ix + 58, line_y, quote["status"],
                fg=STATUS_FG[quote["status"]])
        ui.right(console, ix + iw - 1, line_y,
                 _day(quote["updated_day"]), fg=ui.FAINT)
        shown += 1
    if shown < len(quotes):
        ui.text(console, ix, bottom - 2,
                f"+{len(quotes) - shown} more known quote(s).", fg=ui.FAINT)

    if row["spread"]:
        buy = row["cheapest"]
        sell = row["best_sell"]
        ui.text(console, ix, bottom - 1,
                ui.clip(f"Potential spread: buy {buy['market']} ({buy['system']}) at "
                        f"{buy['buy']} cr, sell at {sell['market']} ({sell['system']}) "
                        f"for {sell['sell']} cr. Verify cargo, fuel and route.", iw),
                fg=ui.TEXT)
    else:
        ui.text(console, ix, bottom - 1,
                "No positive spread between known markets. Scan more systems to compare.",
                fg=ui.DIM)


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------

def _systems(console, ec, x, y, ix, iw, bottom):
    rows = intel.directory()
    if not rows:
        ui.text(console, ix, y, "No systems found.", fg=ui.DIM)
        return
    sel = _selected(state.exchange_index, len(rows))
    lw = 34
    list_top = y + 2
    list_height = max(1, bottom - list_top - 1)
    offset = _offset(sel, len(rows), list_height)

    ui.text(console, ix, y, "SYSTEM MARKET DIRECTORY", fg=ui.DIM)
    ui.right(console, ix + lw - 8, y, "STATUS", fg=ui.DIM)
    ui.right(console, ix + lw - 1, y, "UPD", fg=ui.DIM)

    for pos in range(list_height):
        i = offset + pos
        if i >= len(rows):
            break
        row = rows[i]
        line_y = list_top + pos
        on = i == sel
        bg = ui.SEL_BG if on else None
        if on:
            console.draw_rect(ix - 1, line_y, lw + 1, 1, ord(" "), bg=bg)
        status = row["status"]
        fg = ui.PLAYER if row["is_current"] else (ui.SEL_FG if on else ui.TEXT)
        ui.text(console, ix, line_y, "►" if on else " ", fg=ui.KEY, bg=bg)
        ui.text(console, ix + 2, line_y, ui.clip(row["system"], 17), fg=fg, bg=bg)
        ui.text(console, ix + 21, line_y, status, fg=STATUS_FG[status], bg=bg)
        ui.right(console, ix + lw - 1, line_y,
                 _day(row["updated_day"]) if status != intel.UNKNOWN else "-",
                 fg=ui.FAINT, bg=bg)

    for line_y in range(y - 1, bottom):
        console.print(ix + lw, line_y, "│", fg=ui.BORDER)

    # --- selected system ---------------------------------------------------
    row = rows[sel]
    sname = row["system"]
    status = row["status"]
    dx = ix + lw + 2
    dw = ix + iw - dx
    days = row["updated_day"]
    ui.text(console, dx, y, sname.upper(), fg=ui.TITLE)
    ui.right(console, ix + iw - 1, y, _status_text(status, days),
             fg=STATUS_FG[status])
    hops = row["jumps"]
    distance = "current system" if rows[sel]["is_current"] else (
        f"{hops} jump{'s' if hops != 1 else ''} from you"
        if hops is not None else "no known route")
    ui.text(console, dx, y + 1, ui.clip(distance, dw), fg=ui.DIM)

    if status == intel.LIVE:
        detail = f"Scanner feed active · refreshed {_day(days)}"
        detail_fg = ui.GOOD
    elif status == intel.STALE:
        detail = f"Last known data · recorded {_day(days)}"
        detail_fg = ui.WARN
    else:
        detail = "No market information recorded for this system."
        detail_fg = ui.FAINT
    ui.text(console, dx, y + 3, ui.clip(detail, dw), fg=detail_fg)

    markets = intel.system_markets(sname, status)
    if status == intel.UNKNOWN:
        ui.hline(console, x + lw + 1, y + 5, W - lw - 2, fg=ui.BORDER)
        ui.center(console, dx + dw // 2, y + 8, "NO DATA AVAILABLE", fg=ui.BAD)
        ui.text(console, dx, y + 10,
                ui.clip("Fly within scanner range to detect this market.", dw),
                fg=ui.DIM)
        ui.text(console, dx, y + 11,
                ui.clip("The star itself remains visible on the galaxy chart.", dw),
                fg=ui.FAINT)
        return

    ui.text(console, dx, y + 5,
            ui.clip("Markets: " + (", ".join(m["name"] for m in markets)
                                   or "none"), dw), fg=ui.ACCENT)
    ui.text(console, dx, y + 7, "COMMODITY", fg=ui.DIM)
    ui.right(console, dx + 18, y + 7, "BUY", fg=ui.DIM)
    ui.right(console, dx + 27, y + 7, "SELL", fg=ui.DIM)
    ui.text(console, dx + 30, y + 7, "STATUS", fg=ui.DIM)

    prices = _system_prices(markets)
    ry = y + 8
    if not prices:
        ui.text(console, dx, ry, "No markets in this system.", fg=ui.DIM)
    for good in COMMODITIES:
        if good not in prices or ry >= bottom - 3:
            continue
        prices_row = prices[good]
        ui.text(console, dx, ry, good, fg=ui.TEXT)
        ui.right(console, dx + 18, ry,
                 _price_range(prices_row["buy_lo"], prices_row["buy_hi"]),
                 fg=ui.KEY)
        ui.right(console, dx + 27, ry,
                 str(prices_row["sell_hi"])
                 if prices_row["sell_hi"] is not None else "-", fg=ui.GOOD)
        ui.text(console, dx + 30, ry, status, fg=STATUS_FG[status])
        ry += 1

    ui.text(console, dx, bottom - 1,
            ui.clip(f"LIVE refreshes every day in range; STALE keeps the "
                    f"{_day(days)} snapshot.", dw), fg=ui.FAINT)


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

def _opportunities(console, ec, x, y, ix, iw, bottom):
    rows = intel.opportunities()
    ui.text(console, ix, y, "COMMODITY", fg=ui.DIM)
    ui.text(console, ix + 13, y, "BUY AT", fg=ui.DIM)
    ui.text(console, ix + 38, y, "SELL AT", fg=ui.DIM)
    ui.text(console, ix + 61, y, "DATA", fg=ui.DIM)
    ui.right(console, ix + iw - 1, y, "GAIN", fg=ui.DIM)

    if not rows:
        ui.text(console, ix, y + 2,
                "No positive spreads with sufficient intelligence yet.", fg=ui.DIM)
        ui.text(console, ix, y + 3,
                "Scan more markets within the Long-Range System Scanner's range.",
                fg=ui.FAINT)
        return

    limit = min(len(rows), max(1, bottom - y - 8))
    for i, row in enumerate(rows[:limit]):
        line_y = y + 2 + i
        buy, sell = row["buy"], row["sell"]
        buy_text = f"{buy['buy']} cr {buy['system']}"
        sell_text = f"{sell['sell']} cr {sell['system']}"
        ui.text(console, ix, line_y, row["good"], fg=ui.TEXT)
        ui.text(console, ix + 13, line_y, ui.clip(buy_text, 24),
                fg=STATUS_FG[buy["status"]])
        ui.text(console, ix + 38, line_y, ui.clip(sell_text, 24),
                fg=STATUS_FG[sell["status"]])
        ui.text(console, ix + 61, line_y, row["status"],
                fg=STATUS_FG[row["status"]])
        ui.right(console, ix + iw - 1, line_y, f"+{row['spread']}",
                 fg=ui.KEY if row["status"] == intel.LIVE else ui.WARN)

    top = rows[0]
    ui.hline(console, x, bottom - 6, W, fg=ui.BORDER_HI)
    ui.text(console, ix, bottom - 5, "BEST KNOWN SPREAD", fg=ui.TITLE)
    ui.text(console, ix, bottom - 4,
            ui.clip(f"{top['good']}: {top['buy']['buy']} cr at "
                    f"{top['buy']['market']} ({top['buy']['system']}) → "
                    f"{top['sell']['sell']} cr at {top['sell']['market']} "
                    f"({top['sell']['system']}), +{top['spread']}/unit.", iw),
            fg=ui.TEXT)
    ui.text(console, ix, bottom - 3,
            ui.clip("Potential opportunity only. Cargo space, fuel, travel time and "
                    "later market movement can erase the margin.", iw), fg=ui.DIM)
    ui.text(console, ix, bottom - 2,
            ui.clip("LIVE = both legs current · STALE = at least one leg uses last "
                    "known data.", iw), fg=ui.FAINT)
    ui.text(console, ix, bottom - 1,
            ui.clip("Sell figures are what the station pays after its normal spread.",
                    iw), fg=ui.FAINT)


# ---------------------------------------------------------------------------
# Routes (older Exchange feature, retained)
# ---------------------------------------------------------------------------

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
    near = set(intel.coverage())
    local, remote = [], []
    for volume, edge, good in ec.top_routes(120):
        (local if edge[0] in near or edge[1] in near else remote).append(
            (volume, edge, good))

    shown = _route_table(console, ec, ix, iw, y,
                         "NEARBY TRADE LANES (last 7 days)", local[:12], bottom)
    if not local:
        ui.text(console, ix, y + 2, "No traffic touching your scanner range yet.",
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

def tab_count(tab):
    """Rows the UP/DOWN cursor can move through on the current tab."""
    if state.economy is None:
        return 0
    if tab == 1:
        return len(COMMODITIES)
    if tab == 2:
        return len(intel.directory())
    return 0


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

    # Opening the Exchange already refreshes the scanner in core.events.
    # Here we only sweep once per day (or if the current record is missing),
    # so drawing at 60 FPS does no repeated economy snapshots.
    current = _start_system()
    if current is None or intel.last_update(current) != state.day:
        intel.refresh()

    tab = state.exchange_tab % len(TABS)
    tx = ix
    for i, name in enumerate(TABS):
        label = f" {i + 1} {name} "
        on = i == tab
        ui.text(console, tx, y + 2, label, fg=(0, 0, 0) if on else ui.DIM,
                bg=ui.ACCENT if on else None)
        tx += len(label) + 1
    ui.hline(console, x, y + 3, W, fg=ui.BORDER_HI)

    body = (_overview, _commodities, _systems, _opportunities, _routes)[tab]
    body(console, ec, x, y + 5, ix, iw, y + H - 3)

    hints = [("←→", "Tab"), ("E", "Close")]
    if tab in (1, 2):
        hints.insert(1, ("↑↓", "Select"))
    if state.DEBUG:
        hints.append(("F", "+1 day"))
    ui.hint_row_centered(console, x + W // 2, y + H - 2, hints)
