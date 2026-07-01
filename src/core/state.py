"""Mutable game state shared across modules.

Kept as plain module-level variables (same approach as the original
script) so the rest of the code can `import state` and read/write
`state.credits`, `state.game_state`, etc. without a big refactor into
classes.
"""

from core.entities import Inventory
from core.missions import load_mission

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

stars = []

current_star = None
current_system = None
current_object = None
current_location = None
current_planet = None
pending_destination = None
pending_origin = None

hyperspace_stage = 0
hyperspace_timer = 0.0
hyperspace_complete = False
hyperspace_complete_timer = 0.0

# --- Economy ------------------------------------------------------------------

credits = 100
inventory = Inventory(20)

# --- Missions -------------------------------------------------------------------

missions = load_mission()
visible_missions = []
selected_mission_index = 0

# --- Messages -----------------------------------------------------------------

messages = []


def add_message(text):
    messages.append(text)
    if len(messages) > 10:
        messages.pop(0)


# --- Story / title typewriter progress ----------------------------------------

story_char_index = 0
last_story_time = 0.0


# DEBUG menu interface so that I can quickly check what I am implementing
DEBUG = False
DEBUG_SCREEN = "MARKET"

# Look mode to inspect stuff that you will not go to
look_mode = False
look_x = 0
look_y = 0

# We need fuel to make the player miserable 
fuel = 100
max_fuel = 100
