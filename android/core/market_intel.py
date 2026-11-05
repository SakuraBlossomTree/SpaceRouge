"""Player-held market intelligence for the Galactic Exchange.

This module is deliberately separate from core.economy.  The economy always
knows every market's real, current price; the player only knows what their
Long-Range System Scanner has recorded.  A system is:

    LIVE    - inside the scanner radius; the record is refreshed from the
              actual market and the Exchange may show current prices.
    STALE   - outside the radius but previously recorded; only the saved
              prices are shown, never the actual current ones.
    UNKNOWN - never recorded; no prices are shown at all.

The record is stored in state.market_intel and serialised separately from
the live Economy.
"""

from core import galaxy_view, state
from core.world import COMMODITIES, sell_price

LIVE = "LIVE"
STALE = "STALE"
UNKNOWN = "UNKNOWN"

_FORMAT_VERSION = 1


def _records():
    records = getattr(state, "market_intel", None)
    if not isinstance(records, dict):
        records = {}
        state.market_intel = records
    return records


def _origin():
    return getattr(getattr(state, "current_system", None), "name", None) \
        or getattr(getattr(state, "current_star", None), "name", None)


def _economy():
    return getattr(state, "economy", None)


def coverage():
    """{system: jump distance} currently inside the scanner radius."""
    origin = _origin()
    stars = getattr(state, "stars", None) or []
    if origin is None or not stars:
        return {}
    from core import scanner
    return galaxy_view.jump_distances(stars, origin, scanner.radius())


def _snapshot_market(ms):
    """Copy one live MarketState into a stable, serialisable record."""
    market = ms.market or {}
    buy = {}
    sell = {}
    for good in COMMODITIES:
        if good in market:
            price = int(market[good])
            buy[good] = price
            sell[good] = int(sell_price(price))
    return {
        "market_id": getattr(ms, "id", None) or ms.name,
        "name": ms.name,
        "locations": list(ms.locations),
        "buy": buy,
        "sell": sell,
    }


def refresh():
    """Refresh every system inside the scanner radius.

    Returns the number of system records that changed.  Systems outside the
    radius are deliberately left untouched, so their records stay STALE.
    """
    distances = coverage()
    if not distances:
        return 0

    records = _records()
    ec = _economy()
    changed = 0

    for name in distances:
        markets = ec.markets_in.get(name, ()) if ec is not None else ()
        snapshots = {}
        for ms in markets:
            snap = _snapshot_market(ms)
            snapshots[snap["market_id"]] = snap

        record = {
            "system_id": name,
            "name": name,
            "discovered": True,
            "updated_day": int(state.day),
            "markets": snapshots,
        }
        if records.get(name) != record:
            changed += 1
        records[name] = record

    # Keep the older exploration record in sync as well.
    galaxy_view.update_scanner(state.stars)
    return changed


def _status_with_coverage(system, distances):
    record = _records().get(system)
    if not record or not record.get("discovered"):
        return UNKNOWN
    return LIVE if system in distances else STALE


def status(system):
    """LIVE / STALE / UNKNOWN for one system name."""
    return _status_with_coverage(system, coverage())


def last_update(system):
    """In-game day when this system's market record was last refreshed."""
    record = _records().get(system) or {}
    try:
        return int(record.get("updated_day"))
    except (TypeError, ValueError):
        return None


def _copy_market(snapshot):
    return {
        "market_id": snapshot.get("market_id"),
        "name": snapshot.get("name") or snapshot.get("market_id") or "market",
        "locations": list(snapshot.get("locations") or []),
        "buy": {g: int(p) for g, p in (snapshot.get("buy") or {}).items()
                if g in COMMODITIES},
        "sell": {g: int(p) for g, p in (snapshot.get("sell") or {}).items()
                 if g in COMMODITIES},
    }


def system_markets(system, state_now=None):
    """Market snapshots to display for a system.

    LIVE records are read from the actual economy so the Exchange can never
    show an out-of-date price under a LIVE label.  STALE records are read
    from the player's saved intelligence only.
    """
    if state_now is None:
        state_now = status(system)
    if state_now == UNKNOWN:
        return []

    if state_now == LIVE:
        ec = _economy()
        if ec is not None and ec.markets_in.get(system):
            return [_snapshot_market(ms) for ms in ec.markets_in[system]]

    record = _records().get(system) or {}
    return [_copy_market(m) for m in (record.get("markets") or {}).values()]


def known_systems():
    """[(system, status, updated_day, markets)] for every recorded system."""
    rows = []
    distances = coverage()
    for name, record in _records().items():
        if not record.get("discovered"):
            continue
        state_now = _status_with_coverage(name, distances)
        if state_now == UNKNOWN:
            continue
        rows.append((name, state_now, last_update(name),
                     system_markets(name, state_now)))
    return rows


def directory():
    """Every visible star, ordered for the System Market Directory."""
    records = _records()
    distances = coverage()
    here = _origin()
    rows = []
    for star in getattr(state, "stars", None) or []:
        name = star.name
        state_now = _status_with_coverage(name, distances)
        record = records.get(name) or {}
        markets = record.get("markets") or {}
        rows.append({
            "system": name,
            "status": state_now,
            "updated_day": last_update(name),
            "jumps": distances.get(name),
            "market_count": len(markets),
            "goods_count": len({g for m in markets.values()
                                for g in (m.get("buy") or {})}),
            "is_current": name == here,
        })

    def rank(row):
        if row["is_current"]:
            return 0
        return {LIVE: 1, STALE: 2, UNKNOWN: 3}[row["status"]]

    def order(row):
        if row["status"] == STALE:
            # Most recently recorded first among stale systems.
            return (rank(row), -(row["updated_day"] or 0), row["system"])
        return (rank(row), row["jumps"] if row["jumps"] is not None else 999,
                row["system"])

    return sorted(rows, key=order)


def commodity_quotes(good):
    """Every known market quote for one commodity, cheapest buy first."""
    quotes = []
    for system, state_now, day, markets in known_systems():
        for market in markets:
            buy = market["buy"].get(good)
            sell = market["sell"].get(good)
            if buy is None and sell is None:
                continue
            quotes.append({
                "good": good,
                "system": system,
                "market_id": market["market_id"],
                "market": market["name"],
                "buy": buy,
                "sell": sell,
                "status": state_now,
                "updated_day": day,
            })
    quotes.sort(key=lambda q: (q["buy"] if q["buy"] is not None else 10 ** 9,
                               q["system"], q["market"]))
    return quotes


def best_quotes(good):
    """(cheapest buy, dearest listed price, best sell) for a commodity."""
    quotes = commodity_quotes(good)
    buys = [q for q in quotes if q["buy"] is not None]
    sells = [q for q in quotes if q["sell"] is not None]
    cheapest = min(buys, key=lambda q: (q["buy"], q["system"], q["market"])) \
        if buys else None
    dearest = max(buys, key=lambda q: (q["buy"], q["system"], q["market"])) \
        if buys else None
    best_sell = max(sells, key=lambda q: (q["sell"], q["system"], q["market"])) \
        if sells else None
    return cheapest, dearest, best_sell


def known_average(good):
    """Mean known buy price for a good, or None if no price is recorded."""
    prices = [q["buy"] for q in commodity_quotes(good) if q["buy"] is not None]
    return sum(prices) / len(prices) if prices else None


def commodity_table():
    """One summary row per commodity across all known markets."""
    rows = []
    for good in COMMODITIES:
        cheapest, dearest, best_sell = best_quotes(good)
        spread = 0
        if cheapest is not None and best_sell is not None \
                and best_sell["market_id"] != cheapest["market_id"]:
            spread = max(0, best_sell["sell"] - cheapest["buy"])
        rows.append({
            "good": good,
            "cheapest": cheapest,
            "dearest": dearest,
            "best_sell": best_sell,
            "spread": spread,
        })
    return rows


def opportunities():
    """Potential buy-low / sell-high pairs from known intelligence.

    The result is informational: it does not account for cargo space, fuel
    or the final station spread beyond the recorded sell price.
    """
    rows = []
    stars = getattr(state, "stars", None) or []
    for good in COMMODITIES:
        quotes = commodity_quotes(good)
        buys = [q for q in quotes if q["buy"] is not None]
        sells = [q for q in quotes if q["sell"] is not None]
        if not buys or not sells:
            continue

        cheapest = min(buys, key=lambda q: (
            q["buy"], 0 if q["status"] == LIVE else 1, q["system"], q["market"]))
        sell_options = [q for q in sells
                        if q["market_id"] != cheapest["market_id"]]
        if not sell_options:
            continue
        best_sell = max(sell_options, key=lambda q: (
            q["sell"], 1 if q["status"] == LIVE else 0, q["system"], q["market"]))
        spread = best_sell["sell"] - cheapest["buy"]
        if spread <= 0:
            continue

        hops = galaxy_view.jumps_between(stars, cheapest["system"],
                                         best_sell["system"])
        status_now = LIVE if (cheapest["status"] == LIVE
                              and best_sell["status"] == LIVE) else STALE
        rows.append({
            "good": good,
            "buy": cheapest,
            "sell": best_sell,
            "spread": spread,
            "hops": hops,
            "status": status_now,
            "updated_day": min(
                d for d in (cheapest["updated_day"], best_sell["updated_day"])
                if d is not None
            ) if (cheapest["updated_day"] is not None
                  or best_sell["updated_day"] is not None) else None,
        })

    rows.sort(key=lambda row: (row["spread"], row["good"]), reverse=True)
    return rows


def overview():
    """Counts and freshness for the Exchange overview."""
    distances = coverage()
    records = _records()
    live = [name for name in distances
            if name in records and records[name].get("discovered")]
    stale = [name for name, record in records.items()
             if record.get("discovered") and name not in distances]
    market_records = sum(len(record.get("markets") or {})
                         for record in records.values())
    tracked = {good for record in records.values()
               for market in (record.get("markets") or {}).values()
               for good in (market.get("buy") or {})}
    updates = [last_update(name) for name in live]
    updates = [day for day in updates if day is not None]
    return {
        "detected": len(distances),
        "known_systems": len(records),
        "live_systems": len(live),
        "stale_systems": len(stale),
        "unknown_systems": max(0, len(getattr(state, "stars", None) or [])
                               - len(records)),
        "market_records": market_records,
        "commodities": len(tracked),
        "last_sweep": max(updates) if updates else None,
    }


# ---------------------------------------------------------------------------
# Persistence helpers (handled by core.save; no files are touched here)
# ---------------------------------------------------------------------------

def to_dict():
    """Serialisable copy of the player's market intelligence."""
    systems = {}
    for name, record in _records().items():
        if not record.get("discovered"):
            continue
        markets = {}
        for market_id, market in (record.get("markets") or {}).items():
            markets[str(market_id)] = {
                "market_id": str(market.get("market_id") or market_id),
                "name": str(market.get("name") or market_id),
                "locations": [str(loc) for loc in (market.get("locations") or [])],
                "buy": {g: int(p) for g, p in (market.get("buy") or {}).items()
                        if g in COMMODITIES},
                "sell": {g: int(p) for g, p in (market.get("sell") or {}).items()
                         if g in COMMODITIES},
            }
        systems[str(name)] = {
            "system_id": str(record.get("system_id") or name),
            "name": str(record.get("name") or name),
            "discovered": True,
            "updated_day": int(record.get("updated_day") or 0),
            "markets": markets,
        }
    return {"version": _FORMAT_VERSION, "systems": systems}


def from_dict(payload):
    """Rebuild validated intelligence from save data or an empty dict.

    Older saves simply have no intelligence section.  A saved status is
    never trusted: status is derived from where the player is now, so a
    record saved as STALE cannot be loaded back as LIVE.
    """
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("systems", payload)
    if not isinstance(raw, dict):
        return {}

    systems = {}
    for name, record in raw.items():
        if not isinstance(record, dict) or record.get("discovered") is False:
            continue
        markets = {}
        raw_markets = record.get("markets")
        if not isinstance(raw_markets, dict):
            raw_markets = {}
        for market_id, market in raw_markets.items():
            if not isinstance(market, dict):
                continue
            buy = {}
            for good, price in (market.get("buy") or {}).items():
                if good not in COMMODITIES:
                    continue
                try:
                    buy[good] = max(1, int(price))
                except (TypeError, ValueError):
                    continue
            sell = {}
            for good, price in (market.get("sell") or {}).items():
                if good not in COMMODITIES:
                    continue
                try:
                    sell[good] = max(1, int(price))
                except (TypeError, ValueError):
                    continue
            markets[str(market_id)] = {
                "market_id": str(market.get("market_id") or market_id),
                "name": str(market.get("name") or market_id),
                "locations": [str(loc) for loc in (market.get("locations") or [])],
                "buy": buy,
                "sell": sell,
            }
        try:
            updated_day = int(record.get("updated_day") or 0)
        except (TypeError, ValueError):
            updated_day = 0
        systems[str(name)] = {
            "system_id": str(record.get("system_id") or name),
            "name": str(record.get("name") or name),
            "discovered": True,
            "updated_day": updated_day,
            "markets": markets,
        }
    return systems
