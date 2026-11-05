"""Price log (K): remembers every market price you've seen.

Automatic: every time you dock at a market (or open its Trading Post), the
prices it has on that day are written down. The log shows, for each good,
the cheapest and dearest you've seen it and where - so you can see at a
glance "move Food from Earth to Mars for +9 cr/unit".

Saved per galaxy seed in pricelog.json, same as the notebook.
"""

import json
from pathlib import Path

from core import state

PATH = Path("pricelog.json")

_data = None


def _load():
    global _data
    if _data is None:
        try:
            _data = json.loads(PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _data = {}
    return _data


def _save():
    try:
        PATH.write_text(json.dumps(_data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _galaxy():
    """{ good -> { place -> {price, system, day} } } for this galaxy."""
    return _load().setdefault(str(state.galaxy_seed), {})


def record(location, system, day):
    """Note the prices at a market (overwrites the old entry for that place)."""
    if location is None or system is None or not getattr(location, "market", None):
        return 0
    g = _galaxy()
    for good, price in location.market.items():
        g.setdefault(good, {})[location.name] = {
            "price": int(price), "system": system.name, "day": int(day),
        }
    _save()
    return len(location.market)


def forget(seed):
    """Drop everything recorded for a galaxy seed (the practice galaxy)."""
    if _load().pop(str(seed), None) is not None:
        _save()


def clear():
    _load()[str(state.galaxy_seed)] = {}
    _save()


def summary():
    """[(good, min_entry, max_entry, spread, seen, last_day)] with one row
    per good, sorted alphabetically. min_entry / max_entry are None if the
    good has never been seen."""
    g = _galaxy()
    out = []
    # include every commodity, even unseen, so the table has stable rows
    from core.world import COMMODITIES
    for good in COMMODITIES:
        places = g.get(good, {})
        if not places:
            out.append((good, None, None, 0, 0, None))
            continue
        entries = [{"place": p, **data} for p, data in places.items()]
        lo = min(entries, key=lambda e: e["price"])
        hi = max(entries, key=lambda e: e["price"])
        spread = hi["price"] - lo["price"]
        last_day = max(e["day"] for e in entries)
        out.append((good, lo, hi, spread, len(entries), last_day))
    return out


def for_good(good):
    """Every market that has sold `good`, cheapest first."""
    g = _galaxy()
    return sorted(({"place": p, **data} for p, data in g.get(good, {}).items()),
                  key=lambda e: e["price"])
