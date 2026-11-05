"""Save/load the galaxy seed and the player's market intelligence.

The original format was just ``{"seed": 12345}``.  New saves add scanner
progress and the recorded market intelligence while keeping every old file
loadable.  The live Economy itself is never serialised: it is rebuilt from
the seed, and only the player's separate records are restored.
"""

import json
from pathlib import Path

SAVE_PATH = Path("save.json")
VERSION = 2


def _read():
    """The raw save dictionary, or {} if the file is missing/corrupt."""
    try:
        with SAVE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_data():
    """The whole save dictionary (never raises)."""
    return _read()


def load():
    """The seed saved last time, or None (compatible with old saves)."""
    try:
        seed = _read().get("seed")
        return int(seed) if seed is not None else None
    except (TypeError, ValueError):
        return None


def save(seed, progress=None):
    """Save the galaxy seed plus optional scanner/intelligence progress."""
    data = {"seed": int(seed), "version": VERSION}
    if isinstance(progress, dict):
        data.update(progress)
    try:
        with SAVE_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass
    return data


def save_progress(seed=None):
    """Write current scanner level, market intelligence and survey record."""
    from core import market_intel, state

    try:
        galaxy_seed = int(seed if seed is not None else state.galaxy_seed)
    except (TypeError, ValueError):
        return None
    try:
        scanner_level = max(0, int(state.upgrades.get("scanrange", 0)))
    except (TypeError, ValueError):
        scanner_level = 0
    scanned = getattr(state, "galaxy_scanned_systems", set())
    if not isinstance(scanned, (set, list, tuple)):
        scanned = set()
    return save(galaxy_seed, {
        "scanner_level": scanner_level,
        "market_intel": market_intel.to_dict(),
        "scanned_systems": sorted(str(name) for name in scanned),
    })


def load_progress(seed):
    """Scanner/intelligence fields for a seed, or {} for a new/old save."""
    data = _read()
    try:
        if data.get("seed") is None or int(data.get("seed")) != int(seed):
            return {}
    except (TypeError, ValueError):
        return {}

    try:
        scanner_level = max(0, int(data.get("scanner_level", 0)))
    except (TypeError, ValueError):
        scanner_level = 0
    scanned = data.get("scanned_systems")
    if not isinstance(scanned, list):
        scanned = []
    return {
        "scanner_level": scanner_level,
        "market_intel": data.get("market_intel") or {},
        "scanned_systems": [str(name) for name in scanned],
    }
