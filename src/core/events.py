"""Keyboard input handling, one function per game_state screen."""

import tcod
import time
import random

from core import state, audio, entities, galaxy_view, fonts, tutorial
from core.entities import ITEMS
from core.missions import generate_missions
from core.debt import advance_day, check_deadline
from core.world import FUEL_PRICES, sell_price
from core import travel, quickmenu
from core.save import save_progress
from core.encounter import check_arrival, check_jump

LOOK_SCREENS = ("SYSTEM", "GALAXY")

OVERLAY_KEYS = {
    tcod.event.KeySym.I: "INVENTORY",
    tcod.event.KeySym.L: "MESSAGES",
    tcod.event.KeySym.P: "MISSION_LOG",
    tcod.event.KeySym.H: "HELP",
    tcod.event.KeySym.E: "EXCHANGE",
    tcod.event.KeySym.O: "RADIO",
    tcod.event.KeySym.J: "NOTEBOOK",
    tcod.event.KeySym.K: "PRICELOG",
}
NO_OVERLAY_STATES = ("TITLE", "STORY", "LAUNCH", "HYPERSPACE", "GAME_OVER", "VICTORY")


def _close_overlay():
    state.game_state = state.overlay_return or "SYSTEM"
    state.overlay_return = None

def handle_event(event, story_text, context):
    """Dispatch a KeyDown event to the right handler based on game_state."""
    # Writing a note: every key (and typed text) goes to the notebook
    if state.note_input is not None:
        _note_typing(event)
        return

    # Paying down the loan: digits, M (max), ENTER (pay), ESC (cancel)
    if state.debt_input is not None:
        _debt_typing(event)
        return

    # Mouse wheel zooms the galaxy chart and scrolls the story text
    if isinstance(event, tcod.event.MouseWheel):
        if state.game_state == "GALAXY":
            if event.y > 0:
                _galaxy_zoom_in()
            elif event.y < 0:
                _galaxy_zoom_out()
        elif state.game_state == "STORY":
            if event.y > 0:
                _story_scroll(-STORY_WHEEL_STEP)
            elif event.y < 0:
                _story_scroll(STORY_WHEEL_STEP)
        return

    if not isinstance(event, tcod.event.KeyDown):
        return

    # Q box: Y / ENTER confirms, anything else cancels. On the title screen
    # it quits the game; in a session it saves and goes back to the title.
    if state.quit_confirm:
        state.quit_confirm = False
        if event.sym in (tcod.event.KeySym.Y, tcod.event.KeySym.RETURN, tcod.event.KeySym.KP_ENTER):
            if state.game_state == "TITLE":
                audio.shutdown()
                raise SystemExit()
            from core import newgame
            newgame.return_to_title()
        return

    # Quick menu (SPACE): while it's open it gets every key
    if state.quick_menu:
        quickmenu.handle(event)
        return

    # F9: switch between the modern and the classic (original) UI
    if event.sym == tcod.event.KeySym.F9 and state.UI_TOGGLE:
        mode = fonts.toggle_ui(context)
        if state.game_state != "TITLE":
            state.add_message(f"{mode.capitalize()} UI")
        return

    # F10: cycle fonts (works everywhere, including the title screen)
    if event.sym == tcod.event.KeySym.F10:
        name = fonts.cycle(context)
        if state.game_state != "TITLE":
            state.add_message(f"Font: {name}")
        return

    # Tutorial: SPACE continues an info step, T hides / resumes it
    if event.sym == tcod.event.KeySym.SPACE and tutorial.on_space():
        return
    if event.sym == tcod.event.KeySym.SPACE and quickmenu.available():
        state.look_mode = False
        quickmenu.open_menu()
        return
    if event.sym == tcod.event.KeySym.T:
        if state.game_state == "TITLE":
            tutorial.set_enabled(not tutorial.enabled())
            return
        if state.game_state not in tutorial.HIDDEN_STATES:
            tutorial.toggle()
            return

    # Global overlays: I = cargo, L = comms log, P = contract log, H = handbook.
    # Pressing the same key again closes it; another overlay key switches.
    overlay = OVERLAY_KEYS.get(event.sym)
    if overlay == "EXCHANGE" and state.game_state == "COMBAT":
        overlay = None          # E is "Escape" on the combat menu
    if overlay and state.game_state not in NO_OVERLAY_STATES:
        if state.game_state == overlay:
            _close_overlay()
        else:
            if state.game_state not in OVERLAY_KEYS.values():
                state.overlay_return = state.game_state
            state.game_state = overlay
            state.message_scroll = 0
            if overlay == "EXCHANGE":
                from core import market_intel
                if market_intel.refresh():
                    save_progress()
        return

    if event.sym == tcod.event.KeySym.Q and state.seed_input is None:
        if state.game_state in ("GAME_OVER", "VICTORY"):
            from core import newgame
            newgame.return_to_title()
            return
        state.quit_confirm = True
        return

    # F4: mute / unmute the music
    if event.sym == tcod.event.KeySym.F4:
        muted = audio.toggle_music_mute()
        if state.game_state != "TITLE":
            state.add_message("Music muted" if muted else "Music on")
        return

    # Volume: F5/F6 music down/up, F7/F8 sound effects down/up
    vol_keys = {tcod.event.KeySym.F5: ("music", -0.1), tcod.event.KeySym.F6: ("music", 0.1),
                tcod.event.KeySym.F7: ("sfx", -0.1), tcod.event.KeySym.F8: ("sfx", 0.1)}
    if event.sym in vol_keys:
        channel, step = vol_keys[event.sym]
        if channel == "music":
            if audio.music_muted():
                audio.toggle_music_mute()      # changing the volume unmutes
            v = audio.set_music_volume(audio.music_volume() + step)
            label = "Music"
        else:
            v = audio.set_sfx_volume(audio.sfx_volume() + step)
            label = "Sound effects"
            audio.play_sfx("sfx/NenadSimic - Muffled Distant Explosion.ogg", volume=0.5)
        if state.game_state != "TITLE":
            state.add_message(f"{label} volume {round(v * 100)}%")
        return
    
    if event.sym == tcod.event.KeySym.F11:
        window = context.sdl_window

        if window.fullscreen:
            window.fullscreen = False
        else:
            window.fullscreen = True

    if event.sym == tcod.event.KeySym.D:
        state.day += 1

    if event.sym == tcod.event.KeySym.M:
        if state.game_state not in ("TITLE", "STORY", "LAUNCH", "HYPERSPACE", "GALAXY",
                                    "GAME_OVER", "VICTORY", "COMBAT"):
            # overlays (cargo, log...) remember the screen under them
            back = state.game_state
            if back in OVERLAY_KEYS.values():
                back = state.overlay_return or "SYSTEM"
            state.galaxy_return = back
            state.autopilot = None
            state.game_state = "GALAXY"
            state.look_mode = False
            state.galaxy_preview = None
            if state.current_star:
                galaxy_view.center_on(state.current_star.x, state.current_star.y)
            return

    if event.sym == tcod.event.KeySym.X and state.game_state in LOOK_SCREENS:
        state.look_mode = not state.look_mode
        if state.look_mode:
            if state.game_state == "SYSTEM":
                state.look_x = state.system_player_x
                state.look_y = state.system_player_y
            elif state.game_state == "GALAXY":
                _galaxy_start_scan()
        return
    
    # (the galaxy chart handles its own scan cursor in _galaxy)
    if state.look_mode and state.game_state == "SYSTEM":
        if event.sym == tcod.event.KeySym.UP:
            state.look_y -= 1
        elif event.sym == tcod.event.KeySym.DOWN:
            state.look_y += 1
        elif event.sym == tcod.event.KeySym.LEFT:
            state.look_x -= 1
        elif event.sym == tcod.event.KeySym.RIGHT:
            state.look_x += 1
        elif event.sym == tcod.event.KeySym.ESCAPE:
            state.look_mode = False
        elif event.sym in _key("RETURN", "KP_ENTER"):
            # fly to the scanned spot
            state.look_mode = False
            target = state.look_object
            name = target.name if target is not None else "the marked spot"
            travel.start_autopilot(state.look_x, state.look_y, name)
        return
        
    handler = HANDLERS.get(state.game_state)
    if handler:
        handler(event, story_text)


DIGIT_KEYS = {getattr(tcod.event.KeySym, f"{p}{d}"): str(d)
              for p in ("N", "KP_") for d in range(10)
              if hasattr(tcod.event.KeySym, f"{p}{d}")}


def _title(event, story_text):
    from core import newgame
    sym = event.sym

    # typing a seed
    if state.seed_input is not None:
        if sym in DIGIT_KEYS and len(state.seed_input) < 10:
            state.seed_input += DIGIT_KEYS[sym]
        elif sym == tcod.event.KeySym.BACKSPACE:
            state.seed_input = state.seed_input[:-1]
        elif sym in _key("RETURN", "KP_ENTER"):
            if state.seed_input:
                newgame.build_galaxy(int(state.seed_input))
            state.seed_input = None
        elif sym == tcod.event.KeySym.ESCAPE:
            state.seed_input = None
        return

    practice = tutorial.enabled()     # tutorial ON: play the practice galaxy first

    if sym == tcod.event.KeySym.RETURN:
        if practice:
            # the title's galaxy waits; the tutorial plays on its own fixed seed
            newgame.begin_tutorial_run()
        else:
            # Commit the galaxy currently on the title (fresh or restored with L).
            save_progress()
        state.game_state = "STORY"
        state.story_scroll = 0
        state.story_follow = True
    elif practice:
        return                      # S / L pick the real galaxy: tutorial OFF only
    elif sym == tcod.event.KeySym.S:
        state.seed_input = ""
    elif sym == tcod.event.KeySym.L and state.last_seed is not None \
            and state.last_seed != state.galaxy_seed:
        newgame.build_galaxy(state.last_seed, restore=True)


STORY_LINE_STEP = 1
STORY_PAGE_STEP = 18
STORY_WHEEL_STEP = 3


def _story_scroll(delta):
    """Scroll the story text; negative moves up, positive moves down."""
    state.story_follow = False
    state.story_scroll = max(0, state.story_scroll + delta)


def _story(event, story_text):
    sym = event.sym
    if sym in _key("UP", "PAGEUP"):
        _story_scroll(-STORY_PAGE_STEP if sym == tcod.event.KeySym.PAGEUP
                      else -STORY_LINE_STEP)
    elif sym in _key("DOWN", "PAGEDOWN"):
        _story_scroll(STORY_PAGE_STEP if sym == tcod.event.KeySym.PAGEDOWN
                      else STORY_LINE_STEP)
    elif sym == tcod.event.KeySym.SPACE:
        state.story_char_index = len(story_text)
        state.story_follow = True
    elif sym == tcod.event.KeySym.RETURN:
        if state.story_char_index >= len(story_text):
            state.story_index += 1
            state.story_scroll = 0
            state.story_follow = True
            if state.story_index >= len(state.story_texts):
                # story over: the ship's launch sequence plays, then the game
                from render import launch
                launch.start()
                state.game_state = "LAUNCH"
            else:
                state.story_char_index = 0
                state.last_story_time = 0


def _launch(event, story_text):
    if event.sym in _key("RETURN", "KP_ENTER", "SPACE", "ESCAPE"):
        from render import launch
        launch.finish(skipped=True)


def _key(*names):
    """KeySyms by name, skipping any this tcod version doesn't have."""
    return tuple(getattr(tcod.event.KeySym, n) for n in names
                 if hasattr(tcod.event.KeySym, n))


ZOOM_IN_KEYS = _key("PLUS", "EQUALS", "KP_PLUS")
ZOOM_OUT_KEYS = _key("MINUS", "KP_MINUS")
ARROWS = {
    tcod.event.KeySym.UP: (0, -1),
    tcod.event.KeySym.DOWN: (0, 1),
    tcod.event.KeySym.LEFT: (-1, 0),
    tcod.event.KeySym.RIGHT: (1, 0),
}
SCROLL_STEP = 4        # cells per arrow press
SCROLL_STEP_FAST = 12  # with Shift held


def _galaxy_anchor():
    """Zoom around the scan cursor if it's active, otherwise the screen centre."""
    if state.look_mode:
        return (state.look_x, state.look_y)
    return None


def _galaxy_zoom_in():
    """Zoom in; at the closest zoom, zoom 'into' a star = its system preview."""
    if state.galaxy_preview:
        return
    if state.galaxy_zoom == 0:
        from render.galaxy import preview_target
        star = preview_target(state.stars)
        if star is not None:
            _open_preview(star)
        return
    galaxy_view.zoom(1, _galaxy_anchor())


def _galaxy_zoom_out():
    if state.galaxy_preview:
        _close_preview()
        return
    galaxy_view.zoom(-1, _galaxy_anchor())


def _open_preview(star):
    state.galaxy_preview = star.name
    state.look_x, state.look_y = star.x, star.y


def _close_preview():
    """Back to the chart at x2, centred on the star we were looking at."""
    star = next((s for s in state.stars if s.name == state.galaxy_preview), None)
    state.galaxy_preview = None
    if star is not None:
        galaxy_view.set_zoom(0)
        galaxy_view.center_on(star.x, star.y)
        if state.look_mode:
            state.look_x, state.look_y = star.x, star.y


def _preview_step(step):
    """Previous / next system in the preview (nearest-first from you)."""
    origin = state.current_star or (state.stars[0] if state.stars else None)
    if origin is None:
        return
    order = sorted(state.stars, key=lambda st: (st.x - origin.x) ** 2 + (st.y - origin.y) ** 2)
    names = [s.name for s in order]
    i = names.index(state.galaxy_preview) if state.galaxy_preview in names else -1
    _open_preview(order[(i + step) % len(order)])


def _galaxy_preview_keys(sym, shift):
    """Keys while the system preview is open. Returns True if handled."""
    K = tcod.event.KeySym
    if sym in ZOOM_OUT_KEYS or sym in (K.ESCAPE, K.X, K.Z, K.BACKSPACE):
        _close_preview()
    elif sym == K.TAB:
        _preview_step(-1 if shift else 1)
    elif sym in (K.RIGHT, K.DOWN):
        _preview_step(1)
    elif sym in (K.LEFT, K.UP):
        _preview_step(-1)
    elif sym in _key("C", "HOME"):
        if state.current_star:
            _open_preview(state.current_star)
    elif sym == K.M:
        state.galaxy_preview = None
        return False          # let M close the chart as usual
    return True


def _galaxy_start_scan():
    state.look_mode = True
    if state.current_star:
        sx, sy = galaxy_view.project(state.current_star.x, state.current_star.y)
        if galaxy_view.on_screen(sx, sy):
            state.look_x, state.look_y = state.current_star.x, state.current_star.y
            return
    state.look_x, state.look_y = state.galaxy_cam_x, state.galaxy_cam_y


def _galaxy_snap_cursor():
    """Snap the cursor onto the cell grid so it moves one cell per press."""
    sx, sy = galaxy_view.project(state.look_x, state.look_y)
    state.look_x, state.look_y = galaxy_view.unproject(sx, sy)


# screens the galaxy chart can return to (everything else: back to the system)
RETURNABLE = ("SYSTEM", "LOCATION", "MARKET", "MISSIONS", "SHIPYARD", "JUMPPOINT",
              "INVENTORY", "MESSAGES", "MISSION_LOG", "HELP", "EXCHANGE", "RADIO", "NOTEBOOK", "PRICELOG")


def _galaxy(event, story_text):
    sym = event.sym
    shift = bool(getattr(event, "mod", 0) & tcod.event.Modifier.SHIFT)

    if state.galaxy_preview and _galaxy_preview_keys(sym, shift):
        return

    if sym == tcod.event.KeySym.ESCAPE:
        if state.look_mode:
            state.look_mode = False
            return
        sym = tcod.event.KeySym.M
    if sym == tcod.event.KeySym.M:
        state.look_mode = False
        state.mission_nav_target = None
        state.galaxy_preview = None
        back = state.galaxy_return
        state.galaxy_return = None
        state.game_state = back if back in RETURNABLE else "SYSTEM"
        return

    # ENTER on a scanned star: open its system preview
    if sym in _key("RETURN", "KP_ENTER") and state.look_mode:
        from render.galaxy import preview_target
        star = preview_target(state.stars)
        if star is not None:
            _open_preview(star)
        return

    # zoom (zooming in past x2 opens the system preview)
    if sym in ZOOM_IN_KEYS:
        _galaxy_zoom_in()
        return
    if sym in ZOOM_OUT_KEYS:
        _galaxy_zoom_out()
        return
    if sym == tcod.event.KeySym.Z:
        # cycle: full -> wide -> x1 -> x2 -> full ...
        nxt = (state.galaxy_zoom - 1) % len(galaxy_view.ZOOMS)
        galaxy_view.set_zoom(nxt, _galaxy_anchor())
        return

    if sym == tcod.event.KeySym.N:
        state.galaxy_minimap = not state.galaxy_minimap
        return
    if sym == tcod.event.KeySym.R:
        state.galaxy_routes = not state.galaxy_routes
        return

    # recentre on your ship
    if sym in _key("C", "HOME"):
        if state.current_star:
            galaxy_view.center_on(state.current_star.x, state.current_star.y)
            if state.look_mode:
                state.look_x, state.look_y = state.current_star.x, state.current_star.y
        return

    # TAB: hop the scan cursor between stars, nearest to your position first
    if sym == tcod.event.KeySym.TAB:
        origin = state.current_star or (state.stars[0] if state.stars else None)
        if origin is None:
            return
        order = sorted(state.stars, key=lambda st: (st.x - origin.x) ** 2 + (st.y - origin.y) ** 2)
        state.galaxy_tab_index = (state.galaxy_tab_index + (-1 if shift else 1)) % len(order)
        target = order[state.galaxy_tab_index]
        state.look_mode = True
        state.look_x, state.look_y = target.x, target.y
        galaxy_view.follow(target.x, target.y, margin=10)
        return

    if sym in ARROWS:
        dx, dy = ARROWS[sym]
        if state.look_mode:
            _galaxy_snap_cursor()
            step = galaxy_view.scale() * (5 if shift else 1)
            state.look_x = max(0, min(galaxy_view.GALAXY_W, state.look_x + dx * step))
            state.look_y = max(0, min(galaxy_view.GALAXY_H, state.look_y + dy * step))
            galaxy_view.follow(state.look_x, state.look_y)
        else:
            n = SCROLL_STEP_FAST if shift else SCROLL_STEP
            galaxy_view.scroll(dx * n, dy * n)


def _system(event, story_text):
    """Flying inside a system is free: fuel is only used by jump gates."""
    moves = {
        tcod.event.KeySym.UP: (0, -1), tcod.event.KeySym.DOWN: (0, 1),
        tcod.event.KeySym.LEFT: (-1, 0), tcod.event.KeySym.RIGHT: (1, 0),
    }
    sym = event.sym
    if sym in moves:
        state.autopilot = None              # taking the stick cancels autopilot
        dx, dy = moves[sym]
        travel.step(dx, dy)

    elif sym == tcod.event.KeySym.TAB:
        shift = bool(getattr(event, "mod", 0) & tcod.event.Modifier.SHIFT)
        travel.autopilot_next_target(-1 if shift else 1)

    elif sym in _key("RETURN", "KP_ENTER"):
        if not state.current_object:
            return
        state.autopilot = None
        if hasattr(state.current_object, "destination"):
            state.game_state = "JUMPPOINT"
        else:
            state.current_location = state.current_object
            state.location_index = 0
            state.add_message(f"Docked at {state.current_object.name}.")
            state.game_state = "LOCATION"

    elif sym == tcod.event.KeySym.F1:
        from core.ships import spawn_pirate
        from core.combat import CombatManager
        state.current_combat = CombatManager(state.player_ship, spawn_pirate())
        state.previous_state = state.game_state
        state.game_state = "COMBAT"

def _jumppoint(event, story_text):

    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "SYSTEM"

    elif event.sym == tcod.event.KeySym.RETURN:

        need = travel.jump_fuel(state.current_object)
        if state.fuel < need:
            state.add_message(f"Not enough fuel: this jump needs {need}, you have "
                              f"{state.fuel:.0f}. Refuel at a station (5).")
            travel.check_stranded()
            return
        state.fuel -= need
        # A jump is a fresh departure; don't let the old in-system move
        # counter trigger another day immediately after arriving.
        state.move_counter = 0
        advance_day()

        state.pending_destination = (state.current_object.destination)

        state.pending_origin = (state.current_system.name)

        state.hyperspace_stage = 0
        state.hyperspace_complete = False
        state.hyperspace_timer = time.time()

        audio.play_sfx("sfx/Reverse-Time-Loop-isaiah658.ogg", tag="hyperspace")

        state.game_state = "HYPERSPACE"

def _planet(event, story_text):
    if event.sym == tcod.event.KeySym.UP:
        state.planet_player_y -= 1
    elif event.sym == tcod.event.KeySym.DOWN:
        state.planet_player_y += 1
    elif event.sym == tcod.event.KeySym.LEFT:
        state.planet_player_x -= 1
    elif event.sym == tcod.event.KeySym.RIGHT:
        state.planet_player_x += 1
    elif event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "SYSTEM"

STATION_SCREENS = ("LOCATION", "MARKET", "MISSIONS")


def _station_nav(event):
    """Keys that work on every docked screen (station menu, Trading Post,
    Missions Board): 1-5 open a facility directly, TAB / Shift+TAB move to
    the next / previous screen. Returns True if the key was used."""
    from render.location import LOCATION_ITEMS
    sym = event.sym
    number_keys = [tcod.event.KeySym.N1, tcod.event.KeySym.N2, tcod.event.KeySym.N3,
                   tcod.event.KeySym.N4, tcod.event.KeySym.N5, tcod.event.KeySym.N6]
    number_keys += [k for k in _key("KP_1", "KP_2", "KP_3", "KP_4", "KP_5", "KP_6")]
    if sym in number_keys:
        i = number_keys.index(sym) % 6
        state.location_index = i
        LOCATION_ACTIONS.get(LOCATION_ITEMS[i][2], _closed)()
        return True
    if sym == tcod.event.KeySym.TAB:
        shift = bool(getattr(event, "mod", 0) & tcod.event.Modifier.SHIFT)
        order = ["LOCATION", "MARKET", "MISSIONS"]
        if not state.current_location.market:
            order.remove("MARKET")
        i = order.index(state.game_state) if state.game_state in order else 0
        target = order[(i + (-1 if shift else 1)) % len(order)]
        {"LOCATION": _open_station, "MARKET": _open_market,
         "MISSIONS": _open_missions}[target]()
        return True
    return False


def _open_station():
    state.game_state = "LOCATION"


# ---------------------------------------------------------------------------
# Going places directly (used by the quick menu)
# ---------------------------------------------------------------------------

def goto_screen(screen):
    """Open a screen from wherever you are, keeping track of how to get back."""
    gs = state.game_state
    state.look_mode = False
    if screen == "GALAXY":
        if gs in OVERLAY_KEYS.values():
            gs = state.overlay_return or "SYSTEM"
        if gs != "GALAXY":
            state.galaxy_return = gs
        state.autopilot = None
        state.galaxy_preview = None
        state.game_state = "GALAXY"
        if state.current_star:
            galaxy_view.center_on(state.current_star.x, state.current_star.y)
    elif screen in OVERLAY_KEYS.values():
        if gs not in OVERLAY_KEYS.values():
            state.overlay_return = gs
        state.message_scroll = 0
        state.game_state = screen
    else:                                   # a base screen: close everything on top
        state.galaxy_return = None
        state.overlay_return = None
        state.galaxy_preview = None
        state.game_state = screen


def goto_station(screen):
    """Station menu / Trading Post / Missions Board, from any screen while docked."""
    state.galaxy_return = None
    state.overlay_return = None
    {"LOCATION": _open_station, "MARKET": _open_market,
     "MISSIONS": _open_missions, "SHIPYARD": _open_shipyard}[screen]()


def quick_refuel():
    _refuel()


def undock():
    name = state.current_location.name if state.current_location else "the station"
    state.galaxy_return = None
    state.overlay_return = None
    state.game_state = "SYSTEM"
    state.add_message(f"Undocked from {name}.")


def fly_to(obj, then):
    """Autopilot to a planet / station / gate; then dock, trade or open the
    jump menu when you get there."""
    goto_screen("SYSTEM")
    if (obj.x, obj.y) == (state.system_player_x, state.system_player_y):
        arrive(then, obj)
        return
    name = f"the gate to {obj.destination}" if hasattr(obj, "destination") else obj.name
    travel.start_autopilot(obj.x, obj.y, name)
    state.autopilot_then = (then, obj)


def arrive(then, obj):
    """What fly_to does on arrival."""
    if then == "jump":
        state.current_object = obj
        state.game_state = "JUMPPOINT"
        return
    state.current_location = obj
    state.current_object = obj
    state.location_index = 0
    state.add_message(f"Docked at {obj.name}.")
    state.game_state = "LOCATION"
    if then == "trade" and obj.market:
        _open_market()


def _location(event, story_text):
    from render.location import LOCATION_ITEMS
    sym = event.sym
    n = len(LOCATION_ITEMS)

    if sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "SYSTEM"
        state.add_message(f"Undocked from {state.current_location.name}.")
        return
    if _station_nav(event):
        return
    if sym == tcod.event.KeySym.UP:
        state.location_index = (state.location_index - 1) % n
        return
    if sym == tcod.event.KeySym.DOWN:
        state.location_index = (state.location_index + 1) % n
        return

    if sym not in _key("RETURN", "KP_ENTER"):
        return

    action = LOCATION_ITEMS[state.location_index][2]
    LOCATION_ACTIONS.get(action, _closed)()


def _closed():
    state.add_message("That facility is closed for now.")


def _open_market():
    if not state.current_location.market:
        state.add_message("No market at this location.")
        return
    state.market_index = 0
    state.location_index = 0
    state.game_state = "MARKET"
    # remember today's prices in the price log
    from core import pricelog
    pricelog.record(state.current_location, state.current_system, state.day)


def _open_missions():
    state.location_index = 2
    state.game_state = "MISSIONS"

    # Only generate if this location has no available missions yet
    # a board is only current for the day it was posted; a new day means new contracts
    existing_sources = {m.source for m in state.missions
                        if m.status == "available" and m.day == state.day}

    if state.current_location.name not in existing_sources:
        new_missions = generate_missions(
            state.current_location,
            state.current_system,
            state.stars,
            count=4,
            completed=state.completed_mission_keys,
            day=state.day,
        )
        state.missions = [m for m in state.missions if m.status == "active"]
        state.missions.extend(new_missions)

    state.visible_missions = [
        m for m in state.missions
        if m.source == state.current_location.name
        or (m.status == "active" and m.destination == state.current_location.name)
    ]

    state.selected_mission_index = 0


def _open_shipyard():
    state.location_index = 1
    state.game_state = "SHIPYARD"


def _shipyard(event, story_text):
    from core import shipyard
    sym = event.sym
    n = len(shipyard.UPGRADES)
    if sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "LOCATION"
    elif _station_nav(event):
        return
    elif sym == tcod.event.KeySym.UP:
        state.shipyard_index = (state.shipyard_index - 1) % n
    elif sym == tcod.event.KeySym.DOWN:
        state.shipyard_index = (state.shipyard_index + 1) % n
    elif sym in _key("RETURN", "KP_ENTER"):
        ok, message = shipyard.buy(shipyard.UPGRADES[state.shipyard_index][0])
        state.add_message(message)
        if ok:
            save_progress()


_DIGIT_KEYS = {}
for _d in range(10):
    for _name in (f"N{_d}", f"KP_{_d}"):
        if hasattr(tcod.event.KeySym, _name):
            _DIGIT_KEYS[getattr(tcod.event.KeySym, _name)] = str(_d)


def _open_debt():
    """Station menu > Pay Debt: opens the amount panel."""
    state.location_index = 5
    state.game_state = "LOCATION"
    if state.debt <= 0:
        state.add_message("You have no debt left.")
        return
    state.debt_input = ""


def _pay_debt(amount):
    """Pay `amount` credits toward the loan right now. Returns True if paid."""
    amount = min(amount, state.debt)
    if amount <= 0:
        state.add_message("Type an amount to pay.")
        return False
    if amount > state.credits:
        state.add_message(f"You only have {state.credits} credits.")
        return False
    state.credits -= amount
    state.debt -= amount
    state.add_message(f"Paid {amount} credits toward your loan. Debt is now {state.debt}.")
    if state.debt == 0:
        state.add_message("Your loan is fully paid off. You own your ship!")
        if not state.victory_seen:
            state.game_state = "VICTORY"
    return True


def _victory(event, story_text):
    """Loan paid off: C / ENTER go back to flying (Q goes to the main menu, handled globally)."""
    if event.sym in _key("C", "RETURN", "KP_ENTER"):
        state.victory_seen = True
        state.game_state = "LOCATION"
        state.add_message("Free flight: the loan is paid. Keep trading as long as you like.")


def _debt_typing(event):
    if not isinstance(event, tcod.event.KeyDown):
        return
    sym = event.sym
    if sym == tcod.event.KeySym.ESCAPE:
        state.debt_input = None
    elif sym in _key("RETURN", "KP_ENTER"):
        amount = int(state.debt_input) if state.debt_input else 0
        if _pay_debt(amount):
            state.debt_input = None
    elif sym in _key("BACKSPACE", "DELETE"):
        state.debt_input = state.debt_input[:-1]
    elif sym == tcod.event.KeySym.M:
        state.debt_input = str(max(0, min(state.credits, state.debt)))
    elif sym in _DIGIT_KEYS and len(state.debt_input) < 9:
        state.debt_input = (state.debt_input + _DIGIT_KEYS[sym]).lstrip("0")


def _refuel():
    archetype = state.current_system.archetype
    price_per_unit = FUEL_PRICES.get(archetype)

    if price_per_unit is None:
        state.add_message("No civilian refueling available here.")
        return

    fuel_needed = state.max_fuel - state.fuel
    if fuel_needed <= 0.01:
        state.add_message("Fuel tank is already full.")
        return

    cost = int(round(fuel_needed * price_per_unit))

    if state.credits < cost:
        state.add_message(f"Not enough credits to refuel. Need {cost} credits.")
        return

    state.credits -= cost
    state.fuel = state.max_fuel
    state.add_message(f"Refueled for {cost} credits ({price_per_unit}/unit).")


LOCATION_ACTIONS = {
    "market": _open_market,
    "missions": _open_missions,
    "debt": _open_debt,
    "shipyard": _open_shipyard,
    "refuel": _refuel,
}


def _market(event, story_text):
    from render.market import market_goods
    sym = event.sym
    goods = market_goods()

    if sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "LOCATION"
        return
    if _station_nav(event):
        return
    if not goods:
        return

    if sym == tcod.event.KeySym.UP:
        state.market_index = (state.market_index - 1) % len(goods)
    elif sym == tcod.event.KeySym.DOWN:
        state.market_index = (state.market_index + 1) % len(goods)
    elif sym in (tcod.event.KeySym.RIGHT, tcod.event.KeySym.B, tcod.event.KeySym.RETURN):
        _buy(goods[state.market_index])
    elif sym in (tcod.event.KeySym.LEFT, tcod.event.KeySym.S):
        _sell(goods[state.market_index])


def _buy(name):
    price = state.current_location.market[name]
    item = ITEMS[name]
    if state.credits < price:
        state.add_message(f"Not enough credits for {name}.")
        return
    if state.inventory.free_space() < item.size:
        state.add_message("Not enough cargo space.")
        return
    state.credits -= price
    state.inventory.items.append(item)
    if state.economy:
        state.economy.player_trade(state.current_location, name, 1)
    basis = state.cost_basis.setdefault(name, [0, 0.0])
    basis[0] += 1
    basis[1] += price
    state.add_message(f"Bought 1 {name} for {price} cr.")


def _sell(name):
    price = sell_price(state.current_location.market[name])
    for item in state.inventory.items:
        if item.name == name and not item.mission_key:     # contract cargo is not for sale
            state.inventory.items.remove(item)
            state.credits += price
            if state.economy:
                state.economy.player_trade(state.current_location, name, -1)
            note = ""
            basis = state.cost_basis.get(name)
            if basis and basis[0] > 0:
                avg = basis[1] / basis[0]
                basis[0] -= 1
                basis[1] -= avg
                if basis[0] <= 0:
                    state.cost_basis.pop(name, None)
                diff = price - avg
                note = f" (+{diff:.0f} profit)" if diff >= 0 else f" ({diff:.0f} loss)"
            state.add_message(f"Sold 1 {name} for {price} cr{note}.")
            return
    if any(i.name == name and i.mission_key for i in state.inventory.items):
        state.add_message(f"Your {name} is contract cargo - deliver it, don't sell it.")
        return
    state.add_message(f"You have no {name} to sell.")


def _combat(event, story_text):
    combat = state.current_combat
    if combat is None:
        return

    # --- Combat still active: navigate actions and confirm ------------------
    if combat.active:
        if event.sym == tcod.event.KeySym.UP:
            state.combat_selected_action = (state.combat_selected_action - 1) % 3
        elif event.sym == tcod.event.KeySym.DOWN:
            state.combat_selected_action = (state.combat_selected_action + 1) % 3
        elif event.sym == tcod.event.KeySym.RETURN:
            if combat.turn == combat.TURN_PLAYER:
                action = state.combat_selected_action
                if action == 0:
                    combat.player_attack()
                elif action == 1:
                    combat.player_defend()
                elif action == 2:
                    combat.player_escape()

    # --- Combat over: press ENTER to resolve and continue -------------------
    else:
        if event.sym == tcod.event.KeySym.RETURN:
            _resolve_combat_outcome(combat)


def _resolve_combat_outcome(combat):
    """Apply post-combat effects and return to the game."""
    from core.combat import CombatManager

    if combat.outcome == CombatManager.OUTCOME_VICTORY:
        state.credits += combat.salvage
        state.add_message(f"Salvage recovered: +{combat.salvage} credits.")

    elif combat.outcome == CombatManager.OUTCOME_DEFEAT:
        if state.player_ship.hull <= 0:
            state.last_killed_by = combat.enemy.name
            state.current_combat = None
            state.combat_selected_action = 0
            state.game_over_reason = f"You got killed by {state.last_killed_by}"
            state.game_state = "GAME_OVER"
            return

        damage_taken = state.player_ship.max_hull - state.player_ship.hull
        repair_cost = damage_taken * 2
        state.credits = max(0, state.credits - repair_cost)
        state.player_ship.hull = state.player_ship.max_hull

        state.add_message(f"Repairs cost {repair_cost} credits.")
        state.add_message("Dropped off at nearest station.")

        state.current_combat = None
        state.combat_selected_action = 0
        state.game_state = "SYSTEM"
        return

    elif combat.outcome == CombatManager.OUTCOME_ESCAPED:
        state.add_message("Escaped from combat.")

    # Victory or escaped — return to where they were before combat
    state.current_combat = None
    state.combat_selected_action = 0
    state.game_state = state.previous_state



def _missions(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "LOCATION"
    elif _station_nav(event):
        return

    elif event.sym == tcod.event.KeySym.UP:
        if state.visible_missions:
            state.selected_mission_index = (state.selected_mission_index - 1) % len(state.visible_missions)

    elif event.sym == tcod.event.KeySym.DOWN:
        if state.visible_missions:
            state.selected_mission_index = (state.selected_mission_index + 1) % len(state.visible_missions)

    elif event.sym == tcod.event.KeySym.RETURN:
        if not state.visible_missions:
            return

        mission = state.visible_missions[state.selected_mission_index]

        if mission.status == "available":
            if mission.mission_type == "cargo":
                item = entities.ITEMS[mission.cargo]
                space_needed = item.size * mission.amount

                if state.inventory.free_space() < space_needed:
                    state.add_message("Not enough cargo space for this mission.")
                    return

                # Tag each unit with where it came from, so only this
                # contract's cargo can be handed in for it.
                for _ in range(mission.amount):
                    state.inventory.items.append(entities.Item(
                        item.name, item.size,
                        origin_system=mission.source_system,
                        mission_key=mission.key))

            mission.status = "active"
            state.add_message(f"Mission accepted: {mission.title}")

        elif mission.status == "active" and state.current_location and mission.destination == state.current_location.name:
            if mission.mission_type == "cargo":
                item = entities.ITEMS[mission.cargo]
                carried = sum(1 for i in state.inventory.items if i.mission_key == mission.key)

                if carried < mission.amount:
                    state.add_message("You don't have the required cargo anymore.")
                    return

                removed = 0
                for cargo_item in list(state.inventory.items):
                    if cargo_item.mission_key == mission.key and removed < mission.amount:
                        state.inventory.items.remove(cargo_item)
                        removed += 1

            state.credits += mission.reward_credits
            for item_name in mission.reward_items:
                state.add_message(f"Received item: {item_name}")

            mission.status = "completed"
            state.completed_mission_keys.add(mission.key)
            state.add_message(f"Mission complete: {mission.title} (+{mission.reward_credits} credits)")

        else:
            state.add_message("This mission isn't available.")
    
    elif event.sym == tcod.event.KeySym.V:
        if not state.visible_missions:
            return
        mission = state.visible_missions[state.selected_mission_index]
        dest_system = getattr(mission, 'dest_system', None)
        if not dest_system:
            return
        
        # find the star and place look cursor on it
        for star in state.stars:
            if star.name == dest_system:
                state.look_x = star.x
                state.look_y = star.y
                state.look_mode = True
                state.mission_nav_target = dest_system
                state.galaxy_preview = None
                galaxy_view.center_on(star.x, star.y)
                state.galaxy_return = state.game_state
                state.game_state = "GALAXY"
                break

def _inventory(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        _close_overlay()


def _message(event, story_text):
    from render.messages import max_scroll
    if event.sym == tcod.event.KeySym.ESCAPE:
        _close_overlay()
    elif event.sym == tcod.event.KeySym.UP:
        state.message_scroll = min(max_scroll(), state.message_scroll + 1)
    elif event.sym == tcod.event.KeySym.DOWN:
        state.message_scroll = max(0, state.message_scroll - 1)
    elif event.sym == tcod.event.KeySym.PAGEUP:
        state.message_scroll = min(max_scroll(), state.message_scroll + 20)
    elif event.sym == tcod.event.KeySym.PAGEDOWN:
        state.message_scroll = max(0, state.message_scroll - 20)


def _help(event, story_text):
    from render.help import PAGES
    if event.sym == tcod.event.KeySym.ESCAPE:
        _close_overlay()
    elif event.sym in (tcod.event.KeySym.RIGHT, tcod.event.KeySym.DOWN, tcod.event.KeySym.TAB):
        state.help_page = (state.help_page + 1) % len(PAGES)
    elif event.sym in (tcod.event.KeySym.LEFT, tcod.event.KeySym.UP):
        state.help_page = (state.help_page - 1) % len(PAGES)


def _exchange(event, story_text):
    from render.exchange import TABS, tab_count
    sym = event.sym
    if sym == tcod.event.KeySym.ESCAPE:
        _close_overlay()
        return
    tab_keys = [getattr(tcod.event.KeySym, f"N{i + 1}") for i in range(len(TABS))]
    if sym in tab_keys:
        state.exchange_tab, state.exchange_index = tab_keys.index(sym), 0
    elif sym in (tcod.event.KeySym.RIGHT, tcod.event.KeySym.TAB):
        state.exchange_tab, state.exchange_index = (state.exchange_tab + 1) % len(TABS), 0
    elif sym == tcod.event.KeySym.LEFT:
        state.exchange_tab, state.exchange_index = (state.exchange_tab - 1) % len(TABS), 0
    elif sym in (tcod.event.KeySym.UP, tcod.event.KeySym.DOWN):
        n = tab_count(state.exchange_tab)
        if n:
            step = -1 if sym == tcod.event.KeySym.UP else 1
            state.exchange_index = (state.exchange_index + step) % n
    elif sym == tcod.event.KeySym.F and state.DEBUG and state.economy:
        state.economy.tick()      # debug: run the economy one day forward
        from core import market_intel
        if market_intel.refresh():
            save_progress()


def _radio(event, story_text):
    """Ship's radio: ↑↓ station, ENTER tune in, ←→ prev/next track,
    TAB play mode, +/- volume, X on/off."""
    from render.radio import stations
    sym = event.sym
    tracks = stations()
    if sym == tcod.event.KeySym.ESCAPE:
        _close_overlay()
    elif sym in (tcod.event.KeySym.UP, tcod.event.KeySym.DOWN) and tracks:
        step = -1 if sym == tcod.event.KeySym.UP else 1
        state.radio_index = (state.radio_index + step) % len(tracks)
    elif sym in _key("RETURN", "KP_ENTER") and tracks:
        track = tracks[state.radio_index % len(tracks)]
        if audio.music_muted():
            audio.toggle_music_mute()
        audio.radio_play(track)
    elif sym == tcod.event.KeySym.RIGHT:
        audio.radio_next()
    elif sym == tcod.event.KeySym.LEFT:
        audio.radio_prev()
    elif sym == tcod.event.KeySym.TAB:
        mode = audio.radio_cycle_mode()
        state.add_message(f"Radio: {mode.replace('order', 'in order').replace('repeat', 'repeat one')}")
    elif sym in ZOOM_IN_KEYS or sym in ZOOM_OUT_KEYS:
        step = 0.1 if sym in ZOOM_IN_KEYS else -0.1
        if audio.music_muted():
            audio.toggle_music_mute()
        audio.set_music_volume(audio.music_volume() + step)
    elif sym == tcod.event.KeySym.X:
        audio.toggle_music_mute()


def _pricelog(event, story_text):
    """Price log: ↑↓ pick a commodity, C clears the whole log."""
    from core import pricelog
    rows = pricelog.summary()
    sym = event.sym
    if sym == tcod.event.KeySym.ESCAPE:
        _close_overlay()
    elif sym in (tcod.event.KeySym.UP, tcod.event.KeySym.DOWN) and rows:
        step = -1 if sym == tcod.event.KeySym.UP else 1
        state.pricelog_index = (state.pricelog_index + step) % len(rows)
    elif sym == tcod.event.KeySym.C:
        pricelog.clear()
        state.pricelog_index = 0
        state.add_message("Price log cleared.")


def _notebook(event, story_text):
    """Notebook: ENTER write, R note this market's prices, ↑↓ select, DEL delete."""
    from core import notebook
    sym = event.sym
    notes = notebook.notes()
    if sym == tcod.event.KeySym.ESCAPE:
        _close_overlay()
    elif sym in _key("RETURN", "KP_ENTER"):
        state.note_input = ""
    elif sym == tcod.event.KeySym.R:
        record = notebook.price_record()
        if record and notebook.add(record):
            state.note_index = len(notebook.notes()) - 1
            from core import pricelog
            pricelog.record(state.current_location, state.current_system, state.day)
            state.add_message(f"Noted prices at {state.current_location.name}.")
    elif sym in (tcod.event.KeySym.UP, tcod.event.KeySym.DOWN) and notes:
        step = -1 if sym == tcod.event.KeySym.UP else 1
        state.note_index = max(0, min(len(notes) - 1, state.note_index + step))
    elif sym in _key("DELETE", "BACKSPACE") and notes:
        notebook.delete(state.note_index)
        state.note_index = max(0, min(state.note_index, len(notebook.notes()) - 1))


def _note_typing(event):
    from core import notebook
    if isinstance(event, tcod.event.TextInput):
        if len(state.note_input) < notebook.MAX_LEN:
            state.note_input += event.text
        return
    if not isinstance(event, tcod.event.KeyDown):
        return
    sym = event.sym
    if sym == tcod.event.KeySym.ESCAPE:
        state.note_input = None
    elif sym == tcod.event.KeySym.BACKSPACE:
        state.note_input = state.note_input[:-1]
    elif sym in _key("RETURN", "KP_ENTER"):
        if notebook.add(state.note_input):
            state.note_index = len(notebook.notes()) - 1
        state.note_input = None


def _m_log(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        _close_overlay()
    
def update_hyperspace():
    
    if not state.hyperspace_complete and time.time() - state.hyperspace_timer > 0.5:

        state.hyperspace_timer = time.time()
        state.hyperspace_stage += 1

    if state.hyperspace_stage >= 10 and not state.hyperspace_complete:

        state.hyperspace_complete = True
        state.hyperspace_complete_timer = time.time()

        audio.stop_sfx("hyperspace")
        audio.play_sfx("sfx/NenadSimic - Muffled Distant Explosion.ogg")

    if state.hyperspace_complete:

        if time.time() - state.hyperspace_complete_timer > 1.0:

            destination = state.pending_destination
            origin_system = state.pending_origin

            for star in state.stars:

                if star.name == destination:

                    state.current_star = star
                    state.current_system = star.system

                    for jumppoint in state.current_system.jump_points:

                        if jumppoint.destination == origin_system:

                            state.system_player_x = jumppoint.x
                            state.system_player_y = jumppoint.y

                            break

                    state.add_message(
                        f"You jumped to {destination} System"
                    )

                    state.pending_destination = None
                    state.pending_origin = None

                    state.hyperspace_complete = False
                    state.hyperspace_stage = 0

                    state.game_state = "SYSTEM"
                    from core import market_intel
                    market_intel.refresh()
                    save_progress()
                    check_deadline()
                    travel.check_stranded()

                    break

HANDLERS = {
    "TITLE": _title,
    "STORY": _story,
    "LAUNCH": _launch,
    "GALAXY": _galaxy,
    "SYSTEM": _system,
    "JUMPPOINT": _jumppoint,
    "PLANET": _planet,
    "LOCATION": _location,
    "MARKET": _market,
    "MISSIONS": _missions,
    "COMBAT": _combat,
    "INVENTORY": _inventory,
    "MESSAGES": _message,
    "MISSION_LOG": _m_log,
    "HELP": _help,
    "EXCHANGE": _exchange,
    "RADIO": _radio,
    "NOTEBOOK": _notebook,
    "PRICELOG": _pricelog,
    "VICTORY": _victory,
    "SHIPYARD": _shipyard,
}