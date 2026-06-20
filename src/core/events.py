"""Keyboard input handling, one function per game_state screen."""

import tcod

from core import state
from core.entities import FOOD


def handle_event(event, story_text):
    """Dispatch a KeyDown event to the right handler based on game_state."""
    if not isinstance(event, tcod.event.KeyDown):
        return

    # Global hotkey: open inventory from (almost) anywhere
    if event.sym == tcod.event.KeySym.I and state.game_state != "TITLE":
        state.previous_state = state.game_state
        state.game_state = "INVENTORY"
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
        if state.current_object:
            state.current_location = state.current_object
            state.game_state = "LOCATION"


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


def _inventory(event, story_text):
    if event.sym == tcod.event.KeySym.ESCAPE:
        state.game_state = state.previous_state


HANDLERS = {
    "TITLE": _title,
    "STORY": _story,
    "GALAXY": _galaxy,
    "SYSTEM": _system,
    "PLANET": _planet,
    "LOCATION": _location,
    "MARKET": _market,
    "INVENTORY": _inventory,
}