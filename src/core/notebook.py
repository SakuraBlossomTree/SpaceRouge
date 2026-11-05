"""The pilot's notebook (J): your own notes, plus one-key price records.

Notes are kept per galaxy (seed) in notebook.json, so prices you wrote down
in one galaxy don't get mixed up with another.
"""

import json
import time
from pathlib import Path

from core import state

PATH = Path("notebook.json")
MAX_LEN = 200

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


def notes():
    """This galaxy's notes, oldest first: [{"day", "text"}]."""
    return _load().setdefault(str(state.galaxy_seed), [])


def forget(seed):
    """Drop every note for a galaxy seed (the practice galaxy restarts clean)."""
    if _load().pop(str(seed), None) is not None:
        _save()


def add(text):
    text = text.strip()[:MAX_LEN]
    if not text:
        return False
    notes().append({"day": state.day, "text": text})
    _save()
    return True


def delete(i):
    n = notes()
    if 0 <= i < len(n):
        n.pop(i)
        _save()


def price_record():
    """'Earth (Sol): Food 11, Water 10, ...' for the market you're docked at."""
    loc = state.current_location
    if loc is None or not getattr(loc, "market", None) or state.current_system is None:
        return None
    short = {"Rare Minerals": "Rare Min", "Luxury Goods": "Luxury", "Electronics": "Electr",
             "Machinery": "Machin"}
    prices = ", ".join(f"{short.get(g, g)} {p}" for g, p in loc.market.items())
    return f"{loc.name} ({state.current_system.name}): {prices}"
