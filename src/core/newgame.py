"""Build a galaxy from a seed.

Everything that makes a galaxy - star positions and names, systems,
planets, stations, markets, jump gates, the economy's companies and NPC
fleets (and the 60-day warm-up), and the contracts each station posts -
comes from the galaxy seed. The same seed always rebuilds the same galaxy.

    python src/main.py --seed 12345     start in a specific galaxy
    title screen: S                     type a seed
    title screen: L                     replay the last galaxy (and restore
                                        scanner upgrades / market intelligence)

Tutorial: with the tutorial ON, ENTER on the title screen loads a fixed
practice galaxy (tutorial.TUTORIAL_SEED) instead, so every step works the
same for everyone. Nothing from it is saved. When the tutorial ends,
start_real_game() wipes the run and starts the galaxy the title screen was
showing (a random seed, or the one given with --seed / S / L).
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



# ---------------------------------------------------------------------------
# Tutorial: practice galaxy first, then the real game
# ---------------------------------------------------------------------------

def reset_run():
    """Put the player's ship, money, loan, clock and screens back to a fresh
    start. build_galaxy() already resets the galaxy-side state."""
    from core.entities import Inventory
    from core.ships import PlayerShip

    state.credits = state.STARTING_CREDITS
    state.inventory = Inventory(state.STARTING_CARGO)
    state.player_ship = PlayerShip()
    state.fuel = state.max_fuel = state.STARTING_FUEL
    state.day = 1
    state.move_counter = 0
    state.debt = state.starting_debt
    state.loan_deadline_day = state.STARTING_DEADLINE_DAY
    state.game_over_reason = ""
    state.messages = []
    state.message_scroll = 0

    state.visible_missions = []
    state.selected_mission_index = 0
    state.mission_nav_target = None
    state.current_combat = None
    state.combat_selected_action = 0
    state.previous_state = None
    state.overlay_return = None
    state.galaxy_return = None
    state.pending_destination = None
    state.pending_origin = None
    state.current_object = None
    state.current_location = None
    state.current_planet = None

    state.autopilot = None
    state.autopilot_then = None
    state.autopilot_index = -1
    state.system_player_x, state.system_player_y = 40, 25
    state.planet_player_x, state.planet_player_y = 40, 25
    state.galaxy_cam_x, state.galaxy_cam_y = 96.0, 72.0
    state.galaxy_zoom = 1
    state.galaxy_tab_index = -1
    state.galaxy_preview = None
    state.look_mode = False

    state.quick_menu = False
    state.quit_confirm = False
    state.note_input = None
    state.debt_input = None
    state.seed_input = None
    state.location_index = state.market_index = state.shipyard_index = 0
    state.note_index = state.pricelog_index = state.radio_index = 0
    state.help_page = 0


def _enter_sol():
    sol = next((s for s in state.stars if s.name == "Sol"), state.stars[0])
    state.current_star = sol
    state.current_system = sol.system
    return sol


def begin_tutorial_run():
    """ENTER on the title with the tutorial ON: load the practice galaxy.

    The galaxy the title screen was showing is remembered so the real game
    can start on it afterwards. The practice galaxy is never written to
    save.json, and its price log / notebook always start empty.
    """
    from core import notebook, pricelog, tutorial

    state.real_seed = state.galaxy_seed
    state.tutorial_run = True
    pricelog.forget(tutorial.TUTORIAL_SEED)
    notebook.forget(tutorial.TUTORIAL_SEED)
    build_galaxy(tutorial.TUTORIAL_SEED, persist=False)
    reset_run()


def start_real_game():
    """Tutorial finished: drop the practice run and start the real one.

    Switches the tutorial off for next time (T on the title turns it back
    on), rebuilds the galaxy the title screen showed, and puts the pilot
    back in Sol with a fresh ship, loan and clock.
    """
    from core import tutorial

    seed = state.real_seed
    state.real_seed = None
    state.tutorial_run = False
    tutorial.set_enabled(False)

    build_galaxy(seed, restore=True, persist=True)
    reset_run()
    _enter_sol()
    state.game_state = "SYSTEM"

    state.tutorial_started = True
    state.tutorial_active = False
    state.tutorial_done = True
    state.tutorial_step = len(tutorial.STEPS)

    state.add_message(f"Practice over. Your real game starts now - galaxy seed {state.galaxy_seed}.")
    state.add_message("Press H for the Pilot's Handbook, SPACE for the quick menu.")


def return_to_title():
    """Q in a session: save, then back to the main menu with a fresh galaxy
    waiting (the one just left is L - "Last galaxy"). The practice galaxy is
    never saved."""
    from core import tutorial

    if not state.tutorial_run:
        savegame.save_progress()
        state.last_seed = state.galaxy_seed
    state.tutorial_run = False
    state.real_seed = None

    build_galaxy(None, persist=False)
    reset_run()
    state.current_star = None
    state.current_system = None

    state.hyperspace_stage = 0
    state.hyperspace_timer = 0.0
    state.hyperspace_complete = False
    state.hyperspace_complete_timer = 0.0

    state.story_index = 0          # the story plays again on the next start
    state.story_char_index = 0
    state.story_scroll = 0
    state.story_follow = True

    state.tutorial_started = False
    state.tutorial_active = False
    state.tutorial_done = False
    state.tutorial_step = 0
    state.tutorial_baseline = {}

    state.game_state = "TITLE"
