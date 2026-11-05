"""Interactive tutorial: a short list of steps that complete as you play.

Each step is either
  * "info" - read it and press SPACE, or
  * "do"   - finish when its check() sees the player has done the thing.

With the tutorial ON, the title screen's ENTER loads a fixed practice galaxy
(TUTORIAL_SEED); the tutorial starts when you reach the Sol system. Finishing
it starts your real game on a fresh run and turns the tutorial off. T hides /
resumes it, H opens the Pilot's Handbook for the full reference.
"""

import time

from core import state, fonts

# The galaxy the tutorial is played in, so every step works the same for
# everyone: Earth's board has short, well-paid deliveries and cheap fuel.
TUTORIAL_SEED = 73


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
# A body can be a function so numbers (loan, deadline, prices) always come
# from the game itself instead of being typed in twice.
def _welcome():
    from core import debt
    text = ("That's you: the yellow @ in the Sol system. The panels on the right "
            f"show your ship, your loan and the comms log. You have {debt.loan_days()} "
            f"days to pay off the {state.starting_debt:,} credit loan.")
    if state.tutorial_run:
        text += " This is a practice galaxy - nothing here is saved."
    return text


def _buy_text():
    from core import economy
    from core.world import SELL_SPREAD
    return ("Pick a good with ↑↓ and press → or B to buy one. Goods marked ▼ low are "
            "cheap here - sell them where they show ▲ high. Stations pay "
            f"{round((1 - SELL_SPREAD) * 100)}% of the price, and prices only change "
            f"every {economy.PRICE_UPDATE_DAYS} days.")


def _loan_text():
    from core import debt
    return ("Jumps cost fuel and a day. The lender wants the loan back in "
            f"{debt.loan_days()} days - pay any amount at a station (6: Pay Debt) "
            "and clear it to win. Press H any time for the Pilot's Handbook, and "
            "SPACE for the quick menu (every screen and every place in the system).")


def _finish_text():
    if state.tutorial_run:
        return ("That's the tour, and this was a practice galaxy. Press SPACE to "
                "leave it and start your real game: a fresh ship, loan and clock "
                "on your own galaxy. The tutorial stays off; T on the title brings it back.")
    return "That's the tour. Good luck, pilot!"


STEPS = [
    ("Welcome aboard, pilot", _welcome, "info", None),
    ("Take the helm",
     "Use the arrow keys to fly - it's free, but every 50 moves make a day. TAB is the "
     "autopilot: it flies you to the next planet, station or gate.",
     "do", _moved),
    ("Dock at Earth",
     "Fly onto Earth (the blue ○ on the map) - or press TAB until the "
     "autopilot heads there - and press ENTER to dock.",
     "do", lambda: state.game_state == "LOCATION"),
    ("Visit the Trading Post",
     "Press 1, or select Trading Post and press ENTER.",
     "do", lambda: state.game_state == "MARKET"),
    ("Buy some cargo", _buy_text, "do", _bought),
    ("Find work",
     "Press 3 (or TAB) to go straight to the Missions Board. The number keys 1-6 "
     "work on every station screen. Stations post up to 4 fresh contracts a day.",
     "do", lambda: state.game_state == "MISSIONS"),
    ("Take a contract",
     "Select a contract and press ENTER to accept it - the cargo is loaded into your "
     "hold. Fly it to its destination and deliver it there to get paid. "
     "Contract cargo can't be sold.",
     "do", _took_contract),
    ("Browse the Shipyard",
     "Press 2 to look over the Shipyard: bigger hold, fuel tank and hull, plus "
     "scanners that show more of the galaxy. Don't buy yet - the loan comes first.",
     "do", lambda: state.game_state == "SHIPYARD"),
    ("Check your hold",
     "Press I to open the cargo hold. Contract cargo is listed on its own "
     "rows, tagged with the system it came from - it can only be delivered.",
     "do", lambda: state.game_state == "INVENTORY"),
    ("Open the galaxy chart",
     "Press M to open the galaxy chart - it works from anywhere, even while "
     "docked, and M again brings you back.",
     "do", lambda: state.game_state == "GALAXY"),
    ("Zoom and scroll",
     "Zoom with + / - or the mouse wheel and scroll with the arrows. Zoom in past "
     "x2 for a system preview. Your contract's destination is marked ☼; C centres on you.",
     "do", _used_chart),
    ("Read the Exchange",
     "Press E for the Galactic Exchange: live prices inside your scanner's range, "
     "last-known (STALE) prices outside it, and the best trades nearby. "
     "Scanner upgrades widen the range.",
     "do", lambda: state.game_state == "EXCHANGE"),
    ("Find a jump gate",
     "Close the Exchange and the chart (ESC, then M), leave the station (ESC) and "
     "fly onto a Θ jump gate (TAB helps). Press ENTER on it to see where it leads "
     "and how much fuel it needs.",
     "do", lambda: state.game_state == "JUMPPOINT"),
    ("Mind the loan", _loan_text, "info", None),
    ("Ready for the real thing?", _finish_text, "info", None),
]

HIDDEN_STATES = ("TITLE", "STORY", "GAME_OVER", "VICTORY", "HYPERSPACE", "COMBAT")


def enabled():
    return fonts.settings().get("tutorial", True)


def set_enabled(on):
    fonts.settings()["tutorial"] = bool(on)
    fonts.save_settings()


def body_text(step):
    """The text of a step (a string, or a function that builds it)."""
    body = step[1]
    return body() if callable(body) else body


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
        if state.tutorial_run:
            # the practice galaxy ends here: on to the real game
            from core import newgame
            newgame.start_real_game()
            return
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
