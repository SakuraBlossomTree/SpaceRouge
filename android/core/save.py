"""Simple save/load for the galaxy seed."""

import json
from pathlib import Path

SAVE_PATH = Path("save.json")


def save(seed):
    """Save the galaxy seed to disk."""
    data = {"seed": int(seed)}
    with SAVE_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f)


def load():
    """The seed saved last time, or None."""
    try:
        with SAVE_PATH.open("r", encoding="utf-8") as f:
            seed = json.load(f).get("seed")
        return int(seed) if seed is not None else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None
