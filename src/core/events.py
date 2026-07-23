"""Keyboard input handling, one function per game_state screen."""

import tcod
import time
import random

from core import state, audio, entities
from core.entities import ITEMS
from core.missions import generate_missions
from core.debt import advance_day
from core.world import FUEL_PRICES
from core.save import save
from core.encounter import check_arrival, check_jump

LOOK_SCREENS = ("SYSTEM", "GALAXY")

def handle_event(event, story_text, context):
    """Dispatch a KeyDown event to the right handler based on game_state."""
    if not isinstance(event, tcod.event.KeyDown):
        return

    # Global hotkey: open inventory from (almost) anywhere
    if event.sym == tcod.event.KeySym.I and state.game_state != "TITLE":
        state.previous_state = state.game_state
        state.game_state = "INVENTORY"
        return

    if event.sym == tcod.event.KeySym.L and state.game_state != "TITLE":
        state.previous_state = state.game_state
        state.game_state = "MESSAGES"
        return
    
    if event.sym == tcod.event.KeySym.P and state.game_state != "TITLE":
        state.previous_state = state.game_state
        state.game_state = "MISSION_LOG"
        return

    if event.sym == tcod.event.KeySym.Q:
        audio.device.stop()
        raise SystemExit()
    
    if event.sym == tcod.event.KeySym.F11:
        window = context.sdl_window

        if window.fullscreen:
            window.fullscreen = False
        else:
            window.fullscreen = True

    if event.sym == tcod.event.KeySym.D:
        state.day += 1

    if event.sym == tcod.event.KeySym.M:
        if state.game_state not in ("TITLE", "STORY", "HYPERSPACE", "GALAXY"):
            state.previous_state = state.game_state
            state.game_state = "GALAXY"
            return

    if event.sym == tcod.event.KeySym.X and state.game_state in LOOK_SCREENS:
        state.look_mode = not state.look_mode
        if state.look_mode:
            if state.game_state == "SYSTEM":
                state.look_x = state.system_player_x
                state.look_y = state.system_player_y
            elif state.game_state == "GALAXY":
                state.look_x = state.player_x
                state.look_y = state.player_y
        return
    
    if state.look_mode and state.game_state in LOOK_SCREENS:
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


def _title(event, story_text):
    if event.sym == tcod.event.KeySym.RETURN:
        state.game_state = "STORY"


def _story(event, story_text):
    if event.sym == tcod.event.KeySym.SPACE:
        state.story_char_index = len(story_text)
    elif event.sym == tcod.event.KeySym.RETURN:
        if state.story_char_index >= len(story_text):
            state.story_index += 1
            if state.story_index >= len(state.story_texts):
                state.game_state = "SYSTEM"
            else:
                state.story_char_index = 0
                state.last_story_time = 0


def _galaxy(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE or event.sym == tcod.event.KeySym.M:
        state.game_state = "SYSTEM"


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
    
    # Factor 4: System archetype affects local space conditions
    archetype_efficiency = {
        "Nebula": 1.3,      # Dense gas clouds increase resistance
        "Cluster": 1.1,     # Crowded stars require more navigation
        "Void": 0.9,        # Empty space is more efficient
        "Core": 1.4,        # High gravity wells near core
        "Rim": 0.85,        # Outer rim has less interference
    }
    system_modifier = archetype_efficiency.get(state.current_system.archetype, 1.0)
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

        audio.play("sfx/Reverse-Time-Loop-isaiah658.ogg")

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
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "SYSTEM"
    elif event.sym == tcod.event.KeySym.N1:
        state.previous_state = state.game_state
        state.game_state = "MARKET"
    elif event.sym == tcod.event.KeySym.N3:
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
    
    elif event.sym == tcod.event.KeySym.N5:
        archetype = state.current_system.archetype
        price_per_unit = FUEL_PRICES.get(archetype)

        if price_per_unit is None:
            state.add_message("No civilian refueling available here.")
            return
        
        fuel_needed = state.max_fuel - state.fuel
        if fuel_needed == 0:
            state.add_message("Fuel tank is already full.")
            return
        
        cost = fuel_needed * price_per_unit

        if state.credits < cost:
            state.add_message(f"Not enough credits to refuel. Need {cost} credits.")
            return
        
        state.credits -= cost
        state.fuel = state.max_fuel
        state.add_message(f"Refueled for {cost} credits ({price_per_unit}/unit).")


def _market(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = state.previous_state

    elif event.sym == tcod.event.KeySym.N1:
        food_price = state.current_location.market["Food"]
        item = ITEMS["Food"]

        if state.credits >= food_price and state.inventory.free_space() >= item.size:
            state.credits -= food_price
            state.inventory.items.append(item)
            state.add_message("Bought Food")

    elif event.sym == tcod.event.KeySym.N2:
        for item in state.inventory.items:
            if item.name == "Food":
                food_price = state.current_location.market["Food"]
                state.inventory.items.remove(item)
                state.credits += food_price
                state.add_message("Sold food")
                break

    elif event.sym == tcod.event.KeySym.N3:
        fuel_needed = state.max_fuel - state.fuel
        cost = fuel_needed * 2
        if state.credits >= cost:
            state.credits -= cost
            state.fuel = state.max_fuel
            state.add_message(f"Refueled for {cost} credits")
        else:
            state.add_message("Not enough credits for refuel")


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
                state.previous_state = state.game_state
                state.game_state = "GALAXY"
                break

def _inventory(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = state.previous_state


def _message(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = state.previous_state

def _m_log(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "SYSTEM"
    
def update_hyperspace():
    
    if not state.hyperspace_complete and time.time() - state.hyperspace_timer > 0.5:

        state.hyperspace_timer = time.time()
        state.hyperspace_stage += 1

    if state.hyperspace_stage >= 10 and not state.hyperspace_complete:

        state.hyperspace_complete = True
        state.hyperspace_complete_timer = time.time()

        audio.play(
            "sfx/NenadSimic - Muffled Distant Explosion.ogg"
        )

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
}