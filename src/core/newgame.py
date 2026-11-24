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
    state.run_active = False        # a run only starts once the player really begins one
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
    state.surveyed_objects = set()
    state.hack_done, state.hack_lock = {}, {}
    state.heat = state.heat_day = 0
    state.galaxy_scanned_systems = set()
    state.exchange_tab = 0
    state.exchange_index = 0
    economy.init(stars, seed)
    from core import story_relay
    story_relay.install(stars)       # the dead relay station for the first story mission

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
    refresh_continue()
    return build_galaxy(cli_seed(), persist=False)


def refresh_continue():
    """Look at save.json for a run the title's Continue (C) can resume."""
    state.continue_info = savegame.continue_summary()



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
    state.list_menu = None
    state.nav_wheel = False
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
    begin_run()

    state.add_message(f"Practice over. Your real game starts now - galaxy seed {state.galaxy_seed}.")
    state.add_message("Press H for the Pilot's Handbook, SPACE for the quick menu.")


def return_to_title():
    """Q in a session: save, then back to the main menu with a fresh galaxy
    waiting (the one just left is L - "Last galaxy"). The practice galaxy is
    never saved."""
    from core import tutorial

    if not state.tutorial_run:
        savegame.on_exit()
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
    refresh_continue()


# ---------------------------------------------------------------------------
# Runs: starting, saving and resuming one
# ---------------------------------------------------------------------------

def begin_run():
    """A real run starts now: from here on it is auto-saved (core/save.py)."""
    state.run_active = True
    savegame.reset_autosave()


def _int(value, default=0, lo=None, hi=None):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def _float(value, default=0.0, lo=None):
    try:
        n = float(value)
    except (TypeError, ValueError):
        n = default
    return max(lo, n) if lo is not None else n


def apply_run(run):
    """Put a saved run (core/save.py run_snapshot) onto a freshly built galaxy
    of the same seed. Raises ValueError for a save that doesn't fit."""
    from core.entities import Item
    from core.missions import Mission
    from core import economy as eco

    by_name = {s.name: s for s in state.stars}
    star = by_name.get(run.get("system"))
    if star is None:
        raise ValueError("saved system not in this galaxy")

    ship = state.player_ship
    state.day = _int(run.get("day"), 1, lo=1)
    state.move_counter = _int(run.get("move_counter"), 0, lo=0)
    state.credits = _int(run.get("credits"), state.STARTING_CREDITS, lo=0)
    state.debt = _int(run.get("debt"), state.starting_debt, lo=0)
    state.loan_deadline_day = _int(run.get("loan_deadline_day"), state.STARTING_DEADLINE_DAY, lo=1)
    state.victory_seen = bool(run.get("victory_seen")) or state.debt <= 0
    state.max_fuel = _float(run.get("max_fuel"), state.STARTING_FUEL, lo=1)
    state.fuel = min(state.max_fuel, _float(run.get("fuel"), state.max_fuel, lo=0))
    ship.max_hull = _int(run.get("max_hull"), ship.max_hull, lo=1)
    ship.hull = _int(run.get("hull"), ship.max_hull, lo=1, hi=ship.max_hull)
    state.inventory.space = _int(run.get("cargo_space"), state.STARTING_CARGO, lo=1)
    state.inventory.items = [
        Item(str(i.get("name")), _int(i.get("size"), 1, lo=1),
             origin_system=i.get("origin_system"), mission_key=i.get("mission_key"))
        for i in run.get("items", []) if isinstance(i, dict) and i.get("name")]
    state.upgrades = {str(k): _int(v, 0, lo=0) for k, v in (run.get("upgrades") or {}).items()}
    state.cost_basis = {str(k): [_int(v[0], 0, lo=0), _float(v[1], 0.0, lo=0)]
                        for k, v in (run.get("cost_basis") or {}).items()
                        if isinstance(v, (list, tuple)) and len(v) == 2}
    state.completed_mission_keys = set(str(k) for k in run.get("completed_mission_keys", []))
    state.relay_records = bool(run.get("relay_records"))
    state.surveyed_objects = set(str(k) for k in run.get("surveyed", []))
    state.hack_done = {str(k): str(v) for k, v in (run.get("hack_done") or {}).items()}
    state.hack_lock = {str(k): _int(v, 0, lo=0) for k, v in (run.get("hack_lock") or {}).items()}
    state.heat = _int(run.get("heat"), 0, lo=0, hi=100)
    state.heat_day = _int(run.get("heat_day"), 0, lo=0)

    missions = []
    for m in run.get("missions", []):
        if not isinstance(m, dict):
            continue
        fields = {k: m.get(k) for k in ("id", "title", "description", "mission_type",
                                         "reward_credits", "reward_items", "status", "source",
                                         "destination", "difficulty", "cargo", "amount",
                                         "systems_to_visit", "dest_system", "source_system", "key",
                                         "objective")}
        fields["reward_items"] = fields["reward_items"] or []
        fields["objective"] = fields["objective"] or "arrive"
        mission = Mission(**fields)
        mission.day = m.get("day")
        missions.append(mission)
    state.missions = missions

    # the world: markets move on without the player, so fast-forward them
    _restore_progress(run.get("progress"))
    eco.tick(eco.PRICE_UPDATE_DAYS * (state.day // eco.PRICE_UPDATE_DAYS))

    # position
    state.current_star = star
    state.current_system = star.system
    state.system_player_x = _int(run.get("x"), 40, lo=0)
    state.system_player_y = _int(run.get("y"), 25, lo=0)
    state.current_location = None
    state.current_object = None
    state.current_planet = None
    state.game_state = "SYSTEM"
    name = run.get("location")
    if name:
        for loc in [*star.system.planets, *star.system.stations]:
            if loc.name == name:
                state.current_location = state.current_object = loc
                state.location_index = 0
                state.game_state = "LOCATION"
                break
    market_intel.refresh()


def continue_run():
    """C on the title screen: resume the saved run. Returns True on success;
    a save that can't be applied is reported and a fresh galaxy is left on the title."""
    from core import tutorial

    run = savegame.saved_run()
    if run is None:
        refresh_continue()
        return False
    try:
        build_galaxy(int(run["seed"]), restore=False, persist=False)
        reset_run()
        apply_run(run)
    except (ValueError, KeyError, TypeError, AttributeError) as err:
        print(f"[save] could not resume the saved run: {err}")
        build_galaxy(None, persist=False)
        reset_run()
        state.current_star = None
        state.current_system = None
        state.game_state = "TITLE"
        return False

    state.tutorial_run = False
    state.tutorial_started = True
    state.tutorial_active = False
    state.tutorial_done = True
    state.tutorial_step = len(tutorial.STEPS)
    state.story_index = len(state.story_texts) - 1 if state.story_texts else 0
    state.last_seed = state.galaxy_seed
    begin_run()
    state.add_message(f"Run resumed: day {state.day}, {state.credits} credits.")
    return True
