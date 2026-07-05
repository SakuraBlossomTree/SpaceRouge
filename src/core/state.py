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

credits = 1000
inventory = Inventory(20)

# --- Missions -------------------------------------------------------------------

missions = []
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
DEBUG_SCREEN = "GALAXY"

# Look mode to inspect stuff that you will not go to
look_mode = False
look_x = 0
look_y = 0

# We need fuel to make the player miserable 
fuel = 100
max_fuel = 100

# day counter for the player (this can be later changed to an actual calendar)
day = 1
move_counter = 0

# this is debt mechanic if the player wants to win the game he has to remove the debt entirely
debt = 250000
weekly_payment = 5000
missed_payments = 0
next_payment_day = 8 # first payment due on day 8

# this is the game over screen
game_over_reason = ""

# This tracks the story index
story_index = 0
story_texts = []

galaxy_seed = 0