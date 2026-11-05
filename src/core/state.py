"""Mutable game state shared across modules.

Kept as plain module-level variables (same approach as the original
script) so the rest of the code can `import state` and read/write
`state.credits`, `state.game_state`, etc. without a big refactor into
classes.
"""

from core.entities import Inventory
from core.ships import PlayerShip

# --- Meta / flow control ----------------------------------------------------

game_state = "TITLE"
previous_state = None

# Screen to return to when closing an overlay (inventory / log / mission log).
# Kept separate from previous_state so overlays never break the
# LOCATION -> MARKET -> back chain.
overlay_return = None

# --- Menu cursors -----------------------------------------------------------

location_index = 0   # selected row on the station menu
market_index = 0     # selected commodity in the market

# --- Player position per screen --------------------------------------------

# Galaxy chart camera (world coords of the screen centre) and zoom level
galaxy_cam_x = 96.0
galaxy_cam_y = 72.0
galaxy_zoom = 1          # index into core.galaxy_view.ZOOMS
galaxy_tab_index = -1    # TAB cycling through stars on the chart
galaxy_minimap = True    # N toggles the overview minimap
galaxy_preview = None    # star name whose system map is shown (zoom in past x2)

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
starting_debt = 5000

# What a fresh run starts with (core/newgame.py reset_run() puts these back)
STARTING_CREDITS = 1000
STARTING_CARGO = 20
STARTING_FUEL = 100
STARTING_DEADLINE_DAY = 31   # day the lender repossesses the ship

hyperspace_stage = 0
hyperspace_timer = 0.0
hyperspace_complete = False
hyperspace_complete_timer = 0.0

# --- Economy ------------------------------------------------------------------

credits = STARTING_CREDITS
inventory = Inventory(STARTING_CARGO)

player_ship = PlayerShip()

# --- Combat -----------------------------------------------------------------

current_combat = None       # CombatManager instance when in combat
combat_selected_action = 0  # 0=Attack 1=Defend 2=Escape
last_seen_by = None

# --- Missions -------------------------------------------------------------------

missions = []
visible_missions = []
selected_mission_index = 0
completed_mission_keys = set()
cost_basis = {}                  # good -> [units, credits paid] for goods you bought to trade   # contracts finished this galaxy; never reposted

# --- Messages -----------------------------------------------------------------

messages = []
MAX_MESSAGES = 200
message_scroll = 0   # lines scrolled up from the bottom on the MESSAGES screen


def add_message(text):
    messages.append(text)
    if len(messages) > MAX_MESSAGES:
        messages.pop(0)


# --- Story / title typewriter progress ----------------------------------------

story_char_index = 0
last_story_time = 0.0
story_scroll = 0         # first visible wrapped line
story_follow = True      # keep the newest text in view while it is revealed


# DEBUG menu interface so that I can quickly check what I am implementing
DEBUG = False
DEBUG_SCREEN = "GALAXY"

# F9 switches between the modern UI and the classic (original) UI.
# Set to False to lock the game to the modern UI and disable the F9 key.
UI_TOGGLE = True

# Look mode to inspect stuff that you will not go to
look_mode = False
look_x = 0
look_y = 0
look_object = None   # whatever the look cursor is over (set by renderers)

# We need fuel to make the player miserable 
fuel = STARTING_FUEL
max_fuel = STARTING_FUEL

# day counter for the player (this can be later changed to an actual calendar)
day = 1
move_counter = 0

# this is debt mechanic if the player wants to win the game he has to remove the debt entirely
debt = starting_debt     # no instalments: it only goes down when the player pays
loan_deadline_day = STARTING_DEADLINE_DAY  # lender repossesses the ship on this day if debt is left

# this is the game over screen
game_over_reason = ""
upgrades = {}               # shipyard upgrade levels (scanrange = Long-Range System Scanner)
shipyard_index = 0
victory_seen = False     # the loan-paid-off screen has been shown (and dismissed)

# This tracks the story index
story_index = 0
story_texts = []

galaxy_seed = 0

mission_nav_target = None

# Screen the galaxy chart (M) returns to when it's closed
galaxy_return = None

# Autopilot inside a system: (x, y, name) to fly to, cancelled by any arrow key
autopilot = None
autopilot_next = 0.0
autopilot_index = -1      # TAB cycles through the system's planets/stations/gates
autopilot_then = None     # ("dock" | "trade" | "jump", object) to do on arrival

# Q asks "Quit the game?" first
quit_confirm = False

# Notebook (J): selected note, text being typed (None = not typing)
note_index = 0
note_input = None
debt_input = None          # text typed on the Pay Debt panel (None = panel closed)

# Price log (K): selected commodity row
pricelog_index = 0

# Radio (O): selected station
radio_index = 0

# Quick menu (SPACE): open?, selected row
quick_menu = False
quick_index = 0

# --- Tutorial & help -----------------------------------------------------------

tutorial_started = False
tutorial_active = False
tutorial_done = False
tutorial_step = 0
tutorial_step_time = 0.0
tutorial_baseline = {}
tutorial_run = False    # True while playing the fixed practice galaxy (nothing is saved)
real_seed = None        # the galaxy the title screen showed; the real game starts on it

help_page = 0

# --- Economy -------------------------------------------------------------------
# core.economy.Economy: NPC traders, live prices, companies & stocks
economy = None
exchange_tab = 0
exchange_index = 0
market_scanner = True     # standard Long-Range System Scanner is fitted free
market_intel = {}         # system name -> player-recorded market intelligence
galaxy_scanned_systems = set()  # permanent exploration record
galaxy_routes = False     # R on the galaxy chart: show trade-route heat

# --- Seeds -------------------------------------------------------------------------
last_seed = None        # galaxy seed from the previous run (save.json)
seed_input = None       # text being typed on the title screen (S), or None
