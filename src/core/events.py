"""Keyboard input handling, one function per game_state screen."""

import tcod
import time
import random

from core import state, audio
from core.entities import FOOD


# state.hyperspace_delay = random.uniform(0.2, 1)

def handle_event(event, story_text, context):
    """Dispatch a KeyDown event to the right handler based on game_state."""
    if not isinstance(event, tcod.event.KeyDown):
        return

    # Global hotkey: open inventory from (almost) anywhere
    if event.sym == tcod.event.KeySym.I and state.game_state != "TITLE":
        state.previous_state = state.game_state
        state.game_state = "INVENTORY"
        return

    if event.sym == tcod.event.KeySym.P and state.game_state != "TITLE":
        state.previous_state = state.game_state
        state.game_state = "MESSAGES"
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
            state.game_state = "SYSTEM"


def _galaxy(event, story_text):
    if event.sym == tcod.event.KeySym.M:
        state.game_state = "SYSTEM"


def _system(event, story_text):
    if event.sym == tcod.event.KeySym.UP:
        state.system_player_y -= 1
    elif event.sym == tcod.event.KeySym.DOWN:
        state.system_player_y += 1
    elif event.sym == tcod.event.KeySym.LEFT:
        state.system_player_x -= 1
    elif event.sym == tcod.event.KeySym.RIGHT:
        state.system_player_x += 1
    elif event.sym == tcod.event.KeySym.M:
        state.game_state = "GALAXY"
    elif event.sym == tcod.event.KeySym.RETURN:
        if not state.current_object:
            return
        if hasattr(state.current_object, "destination"):
            state.game_state = "JUMPPOINT"
        else:
            state.current_location = state.current_object
            state.game_state = "LOCATION"

def _jumppoint(event, story_text):

    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = "SYSTEM"

    elif event.sym == tcod.event.KeySym.RETURN:

        if state.credits < state.current_object.cost:
            state.add_message("Not enough credits.")
            return

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

        state.visible_missions = [
            mission for mission in state.missions
            if mission.source == state.current_location.name
        ]

        state.selected_mission_index = 0


def _market(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = state.previous_state

    elif event.sym == tcod.event.KeySym.N1:
        food_price = state.current_location.market["Food"]

        if state.credits >= food_price and state.inventory.free_space() >= FOOD.size:
            state.credits -= food_price
            state.inventory.items.append(FOOD)
            state.add_message("Bought Food")

    elif event.sym == tcod.event.KeySym.N2:
        for item in state.inventory.items:
            if item.name == "Food":
                food_price = state.current_location.market["Food"]
                state.inventory.items.remove(item)
                state.credits += food_price
                state.add_message("Sold food")
                break


def _missions(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = state.previous_state

    elif event.sym == tcod.event.KeySym.UP:
        state.selected_mission_index = (state.selected_mission_index - 1) % len(state.missions)
    
    elif event.sym == tcod.event.KeySym.DOWN:
        state.selected_mission_index = (state.selected_mission_index + 1) % len(state.missions)
    
    elif event.sym == tcod.event.KeySym.RETURN:
        mission = state.visible_missions[state.selected_mission_index]

        if mission.status == "available":
            mission.status = "active"
            state.add_message(f"Mission accepted: {mission.title}")

        elif mission.status == "active" and mission.destination == state.current_location.name:
            state.credits += mission.reward_credits
            for item_name in mission.reward_items:
                state.add_message(f"Received item: {item_name}")

            mission.status = "completed"
            state.add_message(f"Mission complete: {mission.title} (+{mission.reward_credits} credits)")

        else:
            state.add_message("This mission isn't available.")

def _inventory(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = state.previous_state


def _message(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = state.previous_state
    
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
    "INVENTORY": _inventory,
    "MESSAGES": _message,
}