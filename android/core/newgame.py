"""Build a galaxy from a seed.

Everything that makes a galaxy - star positions and names, systems,
planets, stations, markets, jump gates, the economy's companies and NPC
fleets (and the 60-day warm-up), and the contracts each station posts -
comes from the galaxy seed. The same seed always rebuilds the same galaxy.

    python src/main.py --seed 12345     start in a specific galaxy
    title screen: S                     type a seed
    title screen: L                     replay the last galaxy (and restore
                                        scanner upgrades / market intelligence)
"""

import sys

from core import market_intel, scanner, state, economy
from core import save as savegame
from core.world import generate_stars


def cli_seed():
    """--seed N from the command line, or None."""
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a.startswith("--seed="):
            a, val = "--seed", a.split("=", 1)[1]
        elif a == "--seed" and i + 1 < len(args):
            val = args[i + 1]
        else:
            continue
        try:
            return int(val)
        except ValueError:
            print(f"[seed] not a number: {val!r}, using a random galaxy")
    return None


def _restore_progress(progress):
    """Apply saved scanner level, intelligence and survey data (validated)."""
    if not progress:
        return
    scanner.restore_level(progress.get("scanner_level", 0))
    state.market_intel = market_intel.from_dict(progress.get("market_intel"))
    known = progress.get("scanned_systems") or []
    valid = {star.name for star in state.stars}
    state.galaxy_scanned_systems = {name for name in known if name in valid}


def build_galaxy(seed=None, restore=False, persist=True):
    """(Re)build the whole galaxy. seed=None makes a new random one.

    restore=True keeps the scanner upgrades and recorded market intelligence
    from save.json when it belongs to the same seed.  persist=False is used
    at startup so the previous save remains intact until the player actually
    chooses a galaxy (or presses L to replay it).
    """
    stars, seed = generate_stars(seed)
    state.stars = stars
    state.galaxy_seed = seed
    state.current_star = None
    state.current_system = None
    state.missions = []
    state.completed_mission_keys = set()
    state.move_counter = 0
    state.victory_seen = False
    state.cost_basis = {}
    state.upgrades = {}
    state.market_scanner = True    # the standard scanner is fitted free
    state.market_intel = {}
    state.galaxy_scanned_systems = set()
    state.exchange_tab = 0
    state.exchange_index = 0
    economy.init(stars, seed)

    if restore:
        _restore_progress(savegame.load_progress(seed))

    if persist:
        savegame.save_progress(seed)
    print(f"[seed] galaxy seed: {seed}")
    return stars


def startup():
    """Remember last run's seed, then build this run's galaxy.

    The previous save is intentionally not overwritten here: the title
    screen can still replay it with L, after which normal play is saved.
    """
    data = savegame.load_data()
    try:
        state.last_seed = int(data.get("seed")) if data.get("seed") is not None else None
    except (TypeError, ValueError):
        state.last_seed = None
    return build_galaxy(cli_seed(), persist=False)
