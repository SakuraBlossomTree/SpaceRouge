"""Interactive tutorial: a short list of steps that complete as you play.

Each step is either
  * "info" - read it and press SPACE, or
  * "do"   - finish when its check() sees the player has done the thing.

It starts automatically the first time you reach the Sol system (unless it
was switched off on the title screen). T hides / resumes it, H opens the
Pilot's Handbook for the full reference.
"""

import time

from core import state, fonts


def _moved():
    b = state.tutorial_baseline
    return (state.system_player_x, state.system_player_y) != b.get("pos")


def _bought():
    return len(state.inventory.items) > state.tutorial_baseline.get("items", 0)


def _active_missions():
    return sum(1 for m in state.missions if m.status == "active")


def _took_contract():
    return _active_missions() > state.tutorial_baseline.get("active", 0)


def _used_chart():
    b = state.tutorial_baseline
    return (state.galaxy_zoom != b.get("zoom")
            or (round(state.galaxy_cam_x), round(state.galaxy_cam_y)) != b.get("cam"))


def _snapshot():
    return {
        "pos": (state.system_player_x, state.system_player_y),
        "items": len(state.inventory.items),
        "active": _active_missions(),
        "zoom": state.galaxy_zoom,
        "cam": (round(state.galaxy_cam_x), round(state.galaxy_cam_y)),
    }


# title, body, kind, check
STEPS = [
    ("Welcome aboard, pilot",
     "That's you: the yellow @ in the Sol system. The panels on the right "
     "show your ship, your loan and the comms log.",
     "info", None),
    ("Take the helm",
     "Use the arrow keys to fly (on Hard every move burns fuel). TAB is the "
     "autopilot: it flies you to the next planet, station or gate.",
     "do", _moved),
    ("Dock at Earth",
     "Fly onto Earth (the blue ○ on the map) - or press TAB until the "
     "autopilot heads there - and press ENTER to dock.",
     "do", lambda: state.game_state == "LOCATION"),
    ("Visit the Trading Post",
     "Press 1, or select Trading Post and press ENTER.",
     "do", lambda: state.game_state == "MARKET"),
    ("Buy some cargo",
     "Pick a good with ↑↓ and press → or B to buy one. Goods marked ▼ low are "
     "cheap here - sell them where they show ▲ high.",
     "do", _bought),
    ("Find work",
     "Press 3 (or TAB) to go straight to the Missions Board. 1, 3 and 5 work "
     "on every station screen.",
     "do", lambda: state.game_state == "MISSIONS"),
    ("Take a contract",
     "Select a contract and press ENTER to accept it. Fly the cargo to its "
     "destination and deliver it there to get paid.",
     "do", _took_contract),
    ("Open the galaxy chart",
     "Press M to open the galaxy chart - it works from anywhere, even while "
     "docked, and M again brings you back.",
     "do", lambda: state.game_state == "GALAXY"),
    ("Zoom and scroll",
     "Zoom with + / - or the mouse wheel and scroll with the arrows. Your "
     "contract's destination is marked ☼; C centres on you.",
     "do", _used_chart),
    ("Find a jump gate",
     "Close the chart (M), undock (ESC), then fly onto a Θ jump gate (TAB "
     "helps) and press ENTER to see where it leads and how much fuel it needs.",
     "do", lambda: state.game_state == "JUMPPOINT"),
    ("Mind the loan",
     "Jumps cost fuel, a toll and a day. Every 7 days an instalment is taken from "
     "your credits - miss four and the bounty hunters come. Press H any time "
     "for the Pilot's Handbook, and SPACE for the quick menu (every screen "
     "and every place in the system). Good luck!",
     "info", None),
]

HIDDEN_STATES = ("TITLE", "STORY", "GAME_OVER", "HYPERSPACE", "COMBAT")


def enabled():
    return fonts.settings().get("tutorial", True)


def set_enabled(on):
    fonts.settings()["tutorial"] = bool(on)
    fonts.save_settings()


def current():
    if 0 <= state.tutorial_step < len(STEPS):
        return STEPS[state.tutorial_step]
    return None


def _begin_step(i):
    state.tutorial_step = i
    state.tutorial_baseline = _snapshot()
    state.tutorial_step_time = time.time()


def _advance():
    if state.tutorial_step + 1 >= len(STEPS):
        state.tutorial_step = len(STEPS)
        state.tutorial_active = False
        state.tutorial_done = True
        state.add_message("Tutorial complete. Press H for the Pilot's Handbook.")
    else:
        _begin_step(state.tutorial_step + 1)


def update():
    """Call once per frame: starts the tutorial and checks step completion."""
    if (not state.tutorial_started and enabled()
            and state.game_state == "SYSTEM" and state.current_system is not None):
        state.tutorial_started = True
        state.tutorial_active = True
        _begin_step(0)
        return
    if not state.tutorial_active:
        return
    step = current()
    if step is None:
        return
    _, _, kind, check = step
    # short delay so you can see the step before it completes
    if kind == "do" and time.time() - state.tutorial_step_time > 0.4 and check():
        _advance()


def on_space():
    """SPACE continues an info step. Returns True if the key was used."""
    if not state.tutorial_active or state.game_state in HIDDEN_STATES:
        return False
    step = current()
    if step and step[2] == "info":
        _advance()
        return True
    return False


def toggle():
    """T: hide / resume, or restart once finished."""
    if state.tutorial_active:
        state.tutorial_active = False
        state.add_message("Tutorial hidden. Press T to bring it back.")
        return
    state.tutorial_started = True
    state.tutorial_active = True
    if state.tutorial_done or not (0 <= state.tutorial_step < len(STEPS)):
        state.tutorial_done = False
        _begin_step(0)
    else:
        _begin_step(state.tutorial_step)
