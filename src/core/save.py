"""Save/load the galaxy seed, the player's market intelligence and the run.

The original format was just ``{"seed": 12345}``.  Newer saves add scanner
progress and the recorded market intelligence while keeping every old file
loadable.  The live Economy itself is never serialised: it is rebuilt from
the seed (and fast-forwarded to the saved day, see newgame.continue_run), and
only the player's separate records are restored.

The run (ship, credits, cargo, debt, active contracts, position...) lives
under the "run" key with its own seed, so the title screen can pick another
galaxy without losing it. It is written automatically (autosave) whenever
something that matters changes, cleared when the run is lost, and carried over
untouched while no run is active.
"""

import json
from pathlib import Path

from core import state

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

    if getattr(state, "tutorial_run", False):
        return None          # the practice galaxy is never saved
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
    progress = {
        "scanner_level": scanner_level,
        "market_intel": market_intel.to_dict(),
        "scanned_systems": sorted(str(name) for name in scanned),
    }
    run = run_snapshot() if state.run_active else _read().get("run")
    if isinstance(run, dict):
        progress["run"] = run
    return save(galaxy_seed, progress)


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


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

RUN_VERSION = 1
DOCKED_STATES = ("LOCATION", "MARKET", "MISSIONS", "SHIPYARD")
NO_AUTOSAVE_STATES = ("TITLE", "STORY", "LAUNCH", "HYPERSPACE", "COMBAT",
                      "GAME_OVER", "COMPUTER")
MISSION_FIELDS = ("id", "title", "description", "mission_type", "reward_credits",
                  "reward_items", "status", "source", "destination", "difficulty",
                  "cargo", "amount", "systems_to_visit", "dest_system",
                  "source_system", "key", "day", "objective")
ITEM_FIELDS = ("name", "size", "origin_system", "mission_key")


def run_snapshot():
    """Everything about the current run that the galaxy seed cannot rebuild."""
    from core import market_intel
    ship = state.player_ship
    docked = (state.game_state in DOCKED_STATES and state.current_location is not None)
    scanned = getattr(state, "galaxy_scanned_systems", set())
    return {
        "version": RUN_VERSION,
        "seed": int(state.galaxy_seed),
        "credits": int(state.credits),
        "fuel": float(state.fuel),
        "max_fuel": float(state.max_fuel),
        "day": int(state.day),
        "move_counter": int(state.move_counter),
        "debt": int(state.debt),
        "loan_deadline_day": int(state.loan_deadline_day),
        "victory_seen": bool(state.victory_seen),
        "hull": int(ship.hull),
        "max_hull": int(ship.max_hull),
        "cargo_space": int(state.inventory.space),
        "items": [{f: getattr(i, f, None) for f in ITEM_FIELDS} for i in state.inventory.items],
        "upgrades": {str(k): int(v) for k, v in state.upgrades.items()},
        "cost_basis": {str(k): [int(v[0]), float(v[1])] for k, v in state.cost_basis.items()},
        "missions": [{f: getattr(m, f, None) for f in MISSION_FIELDS}
                     for m in state.missions if m.status == "active"],
        "completed_mission_keys": sorted(str(k) for k in state.completed_mission_keys),
        "relay_records": bool(state.relay_records),
        "surveyed": sorted(str(k) for k in state.surveyed_objects),
        "hack_done": {str(k): str(v) for k, v in state.hack_done.items()},
        "hack_lock": {str(k): int(v) for k, v in state.hack_lock.items()},
        "heat": int(state.heat),
        "heat_day": int(state.heat_day),
        "system": state.current_star.name if state.current_star else None,
        "x": int(state.system_player_x),
        "y": int(state.system_player_y),
        "location": state.current_location.name if docked else None,
        "progress": {
            "scanner_level": max(0, int(state.upgrades.get("scanrange", 0))),
            "market_intel": market_intel.to_dict(),
            "scanned_systems": sorted(str(n) for n in scanned),
        },
    }


def saved_run():
    """The run stored in save.json if it looks usable, else None."""
    run = _read().get("run")
    if not isinstance(run, dict) or run.get("version") != RUN_VERSION:
        return None
    try:
        int(run["seed"])
        int(run["day"])
    except (KeyError, TypeError, ValueError):
        return None
    return run


def continue_summary():
    """Short facts about the saved run for the title screen, or None."""
    run = saved_run()
    if run is None:
        return None
    return {"day": run.get("day", 1), "credits": run.get("credits", 0),
            "system": run.get("system") or "?", "debt": run.get("debt", 0)}


def clear_run():
    """The run is over (game over): forget it so Continue isn't offered."""
    state.run_active = False
    state.continue_info = None
    data = _read()
    if "run" in data:
        del data["run"]
        try:
            with SAVE_PATH.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass


_last_fingerprint = None


def _fingerprint():
    s = state
    docked = s.game_state in DOCKED_STATES and s.current_location is not None
    return (s.credits, round(s.fuel, 2), s.day, s.player_ship.hull, s.player_ship.max_hull,
            s.debt, len(s.inventory.items), s.inventory.space, s.max_fuel,
            tuple(sorted(s.upgrades.items())),
            tuple((m.key, m.status) for m in s.missions if m.status == "active"),
            len(s.completed_mission_keys), s.relay_records, len(s.surveyed_objects),
            len(s.hack_done), s.heat,
            s.current_star.name if s.current_star else None,
            s.current_location.name if docked else None)


def reset_autosave():
    """Forget what was last written so the next autosave check writes."""
    global _last_fingerprint
    _last_fingerprint = None


def autosave():
    """Called every frame: write the run when something that matters changed."""
    global _last_fingerprint
    if not state.run_active or state.tutorial_run or state.game_state in NO_AUTOSAVE_STATES:
        return False
    fp = _fingerprint()
    if fp == _last_fingerprint:
        return False
    _last_fingerprint = fp
    save_progress()
    return True


def on_exit():
    """Leaving the session (quit to title, close the window): save the run.
    Walking out of a fight counts as losing it, so quitting is no escape."""
    if state.tutorial_run:
        return
    if state.run_active and state.game_state == "COMBAT":
        combat = state.current_combat
        if combat is not None and combat.active:
            from core import encounter
            encounter.apply_defeat(state.player_ship)
        state.current_combat = None
        state.game_state = "SYSTEM"
    save_progress()
