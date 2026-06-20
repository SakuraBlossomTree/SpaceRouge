"""Mutable game state shared across modules.

Kept as plain module-level variables (same approach as the original
script) so the rest of the code can `import state` and read/write
`state.credits`, `state.game_state`, etc. without a big refactor into
classes.
"""

from core.entities import Inventory

# --- Meta / flow control ----------------------------------------------------

game_state = "TITLE"
previous_state = None

# --- Player position per screen --------------------------------------------

player_x = 40
player_y = 25

system_player_x = 40
system_player_y = 25

planet_player_x = 40
planet_player_y = 25

# --- Current context ---------------------------------------------------------

current_star = None
current_system = None
current_object = None
current_location = None
current_planet = None

# --- Economy ------------------------------------------------------------------

credits = 100
inventory = Inventory(20)

# --- Messages -----------------------------------------------------------------

messages = []


def add_message(text):
    messages.append(text)
    if len(messages) > 10:
        messages.pop(0)


# --- Story / title typewriter progress ----------------------------------------

story_char_index = 0
last_story_time = 0.0