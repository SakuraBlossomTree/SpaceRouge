"""Build a galaxy from a seed.

Everything that makes a galaxy - star positions and names, systems,
planets, stations, markets, jump gates, the economy's companies and NPC
fleets (and the 60-day warm-up), and the contracts each station posts -
comes from the galaxy seed. The same seed always rebuilds the same galaxy.

    python src/main.py --seed 12345     start in a specific galaxy
    title screen: S                     type a seed
    title screen: L                     replay the galaxy from last time
"""

import sys

from core import state, economy
from core.save import save, load
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


def build_galaxy(seed=None):
    """(Re)build the whole galaxy. seed=None makes a new random one."""
    stars, seed = generate_stars(seed)
    state.stars = stars
    state.galaxy_seed = seed
    state.current_star = None
    state.current_system = None
    state.missions = []
    economy.init(stars, seed)
    save(seed)
    print(f"[seed] galaxy seed: {seed}")
    return stars


def startup():
    """Remember last run's seed, then build this run's galaxy."""
    state.last_seed = load()
    return build_galaxy(cli_seed())
