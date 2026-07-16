"""Simple save/load for the galaxy seed."""

import json
from pathlib import Path

SAVE_PATH = Path("save.json")

def save(seed):
    """Save the galaxy seed and optional mission seed to disk."""
    data = {"seed": seed}
    with SAVE_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f)