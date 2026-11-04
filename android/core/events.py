"""Keyboard input handling, one function per game_state screen."""

import tcod
import time
import random

from core import state, audio, entities, galaxy_view, fonts, tutorial
from core.entities import ITEMS
from core.missions import generate_missions
from core.debt import advance_day
from core.world import FUEL_PRICES, FUEL_CONSUMPTION_MODIFIERS
from core.save import save
from core.encounter import check_arrival, check_jump

LOOK_SCREENS = ("SYSTEM", "GALAXY")

OVERLAY_KEYS = {
    tcod.event.KeySym.I: "INVENTORY",
    tcod.event.KeySym.L: "MESSAGES",
    tcod.event.KeySym.P: "MISSION_LOG",
    tcod.event.KeySym.H: "HELP",
    tcod.event.KeySym.E: "EXCHANGE",
}
NO_OVERLAY_STATES = ("TITLE", "STORY", "HYPERSPACE", "GAME_OVER")


def _close_overlay():
    state.game_state = state.overlay_return or "SYSTEM"
    state.overlay_return = None

def handle_event(event, story_text, context):
    """Dispatch a KeyDown event to the right handler based on game_state."""
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
        return

    if event.sym == tcod.event.KeySym.Q and state.seed_input is None:
        audio.shutdown()
        raise SystemExit()

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
        if state.game_state not in ("TITLE", "STORY", "HYPERSPACE", "GALAXY",
                                    "GAME_OVER", "COMBAT"):
            state.previous_state = state.game_state
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

    if sym == tcod.event.KeySym.RETURN:
        state.game_state = "STORY"
        state.story_scroll = 0
        state.story_follow = True
    elif sym == tcod.event.KeySym.S:
        state.seed_input = ""
    elif sym == tcod.event.KeySym.L and state.last_seed is not None \
            and state.last_seed != state.galaxy_seed:
        newgame.build_galaxy(state.last_seed)


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
                state.game_state = "SYSTEM"
            else:
                state.story_char_index = 0
                state.last_story_time = 0


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
        state.game_state = "SYSTEM"
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


def _calculate_fuel_consumption():
    """Calculate fuel consumption based on multiple factors for realistic simulation."""
    base_consumption = 1.0
    
    # Factor 1: Cargo weight - heavier cargo increases consumption
    cargo_weight = len(state.inventory.items) * 0.15
    if cargo_weight > 0:
        base_consumption += cargo_weight
    
    # Factor 2: Ship condition - damaged hull increases drag/inefficiency
    hull_damage_ratio = 1.0 - (state.player_ship.hull / state.player_ship.max_hull)
    damage_penalty = hull_damage_ratio * 0.3
    base_consumption += damage_penalty
    
    # Factor 3: Random variance (±0.2) for unpredictability
    variance = random.uniform(-0.2, 0.2)
    base_consumption += variance
    
    # Factor 4: Local system conditions affect fuel use
    archetype = getattr(state.current_system, "archetype", None)
    system_modifier = FUEL_CONSUMPTION_MODIFIERS.get(archetype, 1.0)
    base_consumption *= system_modifier
    
    # Factor 5: Debt pressure - high debt means less maintained engines
    if state.debt > 5000:
        base_consumption *= 1.1
    elif state.debt > 10000:
        base_consumption *= 1.2
    
    # Ensure minimum consumption is at least 0.5
    return max(0.5, base_consumption)


def _system(event, story_text):
    moved = False

    if event.sym == tcod.event.KeySym.UP:
        state.system_player_y -= 1
        moved = True
    elif event.sym == tcod.event.KeySym.DOWN:
        state.system_player_y += 1
        moved = True
    elif event.sym == tcod.event.KeySym.LEFT:
        state.system_player_x -= 1
        moved = True
    elif event.sym == tcod.event.KeySym.RIGHT:
        state.system_player_x += 1
        moved = True

    if moved:
        fuel_cost = _calculate_fuel_consumption()
        
        if state.fuel <= 0:
            state.add_message("No fuel!")
            # undo the move
            if event.sym == tcod.event.KeySym.UP:
                state.system_player_y += 1
            elif event.sym == tcod.event.KeySym.DOWN:
                state.system_player_y -= 1
            elif event.sym == tcod.event.KeySym.LEFT:
                state.system_player_x += 1
            elif event.sym == tcod.event.KeySym.RIGHT:
                state.system_player_x -= 1
            state.game_over_reason = "You ran out of fuel and drifted into the void."
            state.game_state = "GAME_OVER"
        elif state.fuel < fuel_cost:
            # Not enough fuel for this movement
            state.add_message(f"Need {fuel_cost:.1f} fuel, only {state.fuel:.1f} remaining!")
            # undo the move
            if event.sym == tcod.event.KeySym.UP:
                state.system_player_y += 1
            elif event.sym == tcod.event.KeySym.DOWN:
                state.system_player_y -= 1
            elif event.sym == tcod.event.KeySym.LEFT:
                state.system_player_x += 1
            elif event.sym == tcod.event.KeySym.RIGHT:
                state.system_player_x -= 1
            state.game_over_reason = "You ran out of fuel and drifted into the void."
            state.game_state = "GAME_OVER"
        else:
            state.fuel -= fuel_cost
            state.move_counter += 1
            
            # Display fuel consumption for player awareness
            if fuel_cost != 1.0:
                state.add_message(f"Fuel used: {fuel_cost:.1f}")

            # Every 50 moves = 1 day
            if state.move_counter >= 50:
                state.move_counter = 0
                advance_day()

    elif event.sym == tcod.event.KeySym.RETURN:
        if not state.current_object:
            return
        if hasattr(state.current_object, "destination"):
            state.game_state = "JUMPPOINT"
        else:
            state.current_location = state.current_object
            state.location_index = 0
            state.add_message(f"Docked at {state.current_object.name}.")
            state.game_state = "LOCATION"

    elif event.sym == tcod.event.KeySym.F1:
        from core.ships import spawn_pirate
        from core.combat import CombatManager
        state.current_combat = CombatManager(state.player_ship, spawn_pirate())
        state.previous_state = state.game_state
        state.game_state = "COMBAT"

def _jumppoint(event, story_text):

    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "SYSTEM"

    elif event.sym == tcod.event.KeySym.RETURN:

        if state.credits < state.current_object.cost:
            state.add_message("Not enough credits.")
            return

        # if state.fuel < 20:
        #     state.add_message("Not enough fuel to jump!")
        #     return

        # state.fuel -= 20

        advance_day()

        state.credits -= state.current_object.cost

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

def _location(event, story_text):
    from render.location import LOCATION_ITEMS
    sym = event.sym
    n = len(LOCATION_ITEMS)

    if sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "SYSTEM"
        return
    if sym == tcod.event.KeySym.UP:
        state.location_index = (state.location_index - 1) % n
        return
    if sym == tcod.event.KeySym.DOWN:
        state.location_index = (state.location_index + 1) % n
        return

    number_keys = [tcod.event.KeySym.N1, tcod.event.KeySym.N2, tcod.event.KeySym.N3,
                   tcod.event.KeySym.N4, tcod.event.KeySym.N5]
    if sym in number_keys:
        state.location_index = number_keys.index(sym)
    elif sym != tcod.event.KeySym.RETURN:
        return

    action = LOCATION_ITEMS[state.location_index][2]
    LOCATION_ACTIONS.get(action, _closed)()


def _closed():
    state.add_message("That facility is closed for now.")


def _open_market():
    if not state.current_location.market:
        state.add_message("No market at this location.")
        return
    state.previous_state = state.game_state
    state.market_index = 0
    state.game_state = "MARKET"


def _open_missions():
    state.previous_state = state.game_state
    state.game_state = "MISSIONS"

    # Only generate if this location has no available missions yet
    existing_sources = {m.source for m in state.missions if m.status == "available"}

    if state.current_location.name not in existing_sources:
        new_missions = generate_missions(
            state.current_location,
            state.current_system,
            state.stars,
            count=4,
        )
        state.missions = [m for m in state.missions if m.status == "active"]
        state.missions.extend(new_missions)

    state.visible_missions = [
        m for m in state.missions
        if m.source == state.current_location.name
        or (m.status == "active" and m.destination == state.current_location.name)
    ]

    state.selected_mission_index = 0


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
    "refuel": _refuel,
}


def _market(event, story_text):
    from render.market import market_goods
    sym = event.sym
    goods = market_goods()

    if sym == tcod.event.KeySym.ESCAPE:
        state.game_state = state.previous_state or "LOCATION"
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
    state.add_message(f"Bought 1 {name} for {price} cr.")


def _sell(name):
    price = state.current_location.market[name]
    for item in state.inventory.items:
        if item.name == name:
            state.inventory.items.remove(item)
            state.credits += price
            if state.economy:
                state.economy.player_trade(state.current_location, name, -1)
            state.add_message(f"Sold 1 {name} for {price} cr.")
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
        state.game_state = state.previous_state

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

                for _ in range(mission.amount):
                    state.inventory.items.append(item)

            mission.status = "active"
            state.add_message(f"Mission accepted: {mission.title}")

        elif mission.status == "active" and state.current_location and mission.destination == state.current_location.name:
            if mission.mission_type == "cargo":
                item = entities.ITEMS[mission.cargo]
                carried = sum(1 for i in state.inventory.items if i.name == item.name)

                if carried < mission.amount:
                    state.add_message("You don't have the required cargo anymore.")
                    return

                removed = 0
                for cargo_item in list(state.inventory.items):
                    if cargo_item.name == item.name and removed < mission.amount:
                        state.inventory.items.remove(cargo_item)
                        removed += 1

            state.credits += mission.reward_credits
            for item_name in mission.reward_items:
                state.add_message(f"Received item: {item_name}")

            mission.status = "completed"
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
                state.previous_state = state.game_state
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
    tab_keys = [tcod.event.KeySym.N1, tcod.event.KeySym.N2,
                tcod.event.KeySym.N3, tcod.event.KeySym.N4]
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

                    break

HANDLERS = {
    "TITLE": _title,
    "STORY": _story,
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
}