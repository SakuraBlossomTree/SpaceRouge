"""Story mission "The Unsent Message": the game-side glue for the hacking
mission in hacking/missions/unsent_message.py.

The hacking engine stays unaware of the game. This module is the only place
that knows both sides:

    install(stars)      add the dead Halcyon Relay station to a system 1-2
                        gate jumps from Sol (after the galaxy is generated,
                        so the galaxy itself is unchanged)
    post(location)      put the hauler's contract on Earth's mission board
    on_computer_update  called every frame while the computer is open; when
                        the hack finishes, record the result for the game
    turn_in_ready /
    on_turned_in        the board gate and the reward when you return

Nothing here is saved: like the board missions, story progress lasts for
the session (a new galaxy starts the story again).
"""

import random

from core import state
from core.entities import Station

MISSION_KEY = "story:unsent_message"
HACK_ID = "unsent_message"          # id in hacking/missions/__init__.py

HAULER = "Dessa Quill"
HAULER_HOME = "Earth"               # the board that posts the contract
RELAY_NAME = "Halcyon Relay"
SETTLEMENT = "Harrow's Reach"
REWARD = 650

RUN_SERIAL = 0      # bumped by every install(); lets the computer drop a stale run
_handled = None     # the hacking Mission object already applied to the game


# ---------------------------------------------------------------------------
# The relay station
# ---------------------------------------------------------------------------

def install(stars):
    """Place the relay. Uses its own random generator (seeded from the galaxy
    seed), so the procedural galaxy is untouched. Returns the info dict."""
    global RUN_SERIAL, _handled
    RUN_SERIAL += 1
    _handled = None
    state.relay = None
    state.relay_records = False
    if state.tutorial_run:
        return None
    from core import travel
    from core.world import SYS_H, SYS_MARGIN, SYS_W, _used_positions

    sol = next((s for s in stars if s.name == "Sol"), None)
    if sol is None:
        return None
    jumps = {}
    for s in stars:
        if s.name == "Sol":
            continue
        est = travel.route_estimate(stars, "Sol", s.name)
        if est:
            jumps[s.name] = est[0]
    pool = sorted(n for n, j in jumps.items() if j == 2) \
        or sorted(n for n, j in jumps.items() if j == 1)
    if not pool:
        return None
    rng = random.Random(f"relay|{state.galaxy_seed}")
    chosen = rng.choice(pool)                  # choose once, then look it up
    star = next(s for s in stars if s.name == chosen)

    used = _used_positions(star.system)
    for _ in range(200):
        x = rng.randrange(SYS_MARGIN, SYS_W - SYS_MARGIN)
        y = rng.randrange(SYS_MARGIN, SYS_H - SYS_MARGIN)
        if (x, y) not in used:
            break
    star.system.stations.append(Station(x, y, RELAY_NAME, "Abandoned", None))
    state.relay = {"system": star.name, "station": RELAY_NAME}
    return state.relay


def is_relay(loc):
    return bool(loc is not None and state.relay and loc.name == state.relay["station"])


# ---------------------------------------------------------------------------
# The contract on the board
# ---------------------------------------------------------------------------

def _make_mission(location):
    from core.missions import Mission
    m = Mission(
        id="STORY-0001", title="The Unsent Message",
        description=(f"Independent hauler {HAULER} can't run her lane: the old "
                     f"{RELAY_NAME} in {state.relay['system']} is broadcasting corrupted "
                     "nav data and ships are steering clear. Dock at the relay, plug "
                     "your slate into its Computer, find out why, and bring her what "
                     "you find."),
        mission_type="hack", reward_credits=REWARD, reward_items=[],
        status="available", source=location.name, destination=location.name,
        difficulty=2, dest_system=state.relay["system"],
        source_system=getattr(state.current_system, "name", None), key=MISSION_KEY)
    m.day = state.day
    return m


def post(location):
    """Called when a mission board is opened: add the story contract to the
    hauler's home board until it has been completed."""
    if state.relay is None or location is None or location.name != HAULER_HOME:
        return
    if MISSION_KEY in state.completed_mission_keys:
        return
    if any(m.key == MISSION_KEY for m in state.missions):
        return
    state.missions.append(_make_mission(location))


def turn_in_ready(mission):
    return mission.mission_type != "hack" or state.relay_records


def not_ready_message():
    return f"{HAULER} is waiting for the records from the {RELAY_NAME}."


def on_turned_in(mission):
    state.add_message(f"{HAULER}: \"{SETTLEMENT}. Three hundred and forty people, and "
                      "nobody told us.\"")
    state.add_message(f"The lane past the {RELAY_NAME} reopens; she is already "
                      f"plotting a run to {SETTLEMENT}.")


# ---------------------------------------------------------------------------
# The hack result
# ---------------------------------------------------------------------------

def on_computer_update(computer):
    """Per-frame check from computer_input.update(). Applies each finished
    hacking run once; a retry builds a new Mission object, so it counts."""
    global _handled
    m = getattr(computer, "mission", None)
    if computer.mission_id != HACK_ID or m is None or not m.finished or m is _handled:
        return
    _handled = m
    if m.status == "success":
        if not state.relay_records:
            state.relay_records = True
            state.add_message(f"{RELAY_NAME}: transmission recovered. "
                              f"Take it back to {HAULER} on {HAULER_HOME}.")
    else:
        state.add_message(f"{RELAY_NAME}: WARDEN cut your link. The terminal can be tried again.")
