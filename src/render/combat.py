"""Render the COMBAT screen."""

from core import state
from core.combat import CombatManager

# Layout constants
PLAYER_COL  = 4
ENEMY_COL   = 44
STATS_ROW   = 4
LOG_ROW     = 14
ACTION_ROW  = 22

ACTION_LABELS = ["[A] Attack", "[D] Defend", "[E] Escape"]

SELECT_COLOR = (255, 255,   0)
NORMAL_COLOR = (255, 255, 255)
HEADER_COLOR = (140, 140, 140)
HULL_HI      = (100, 220, 100)   # healthy hull
HULL_MID     = (220, 220,  60)   # damaged hull
HULL_LO      = (220,  60,  60)   # critical hull
DIVIDER      = (80,  80,  80)


def _hull_color(current, maximum):
    ratio = current / maximum if maximum else 0
    if ratio > 0.5:
        return HULL_HI
    elif ratio > 0.25:
        return HULL_MID
    return HULL_LO


def _hull_bar(current, maximum, width=20):
    """Return a filled/empty bar string of fixed width."""
    ratio = current / maximum if maximum else 0
    filled = round(ratio * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def draw(console, width, height):
    combat = state.current_combat
    if combat is None:
        return

    player = combat.player
    enemy  = combat.enemy

    # --- Title --------------------------------------------------------------
    title = "-- COMBAT --"
    console.print(width // 2 - len(title) // 2, 2, title, fg=HEADER_COLOR)

    # --- Player stats (left) ------------------------------------------------
    console.print(PLAYER_COL, STATS_ROW,     "YOUR SHIP",         fg=HEADER_COLOR)
    console.print(PLAYER_COL, STATS_ROW + 1, player.name)

    hull_color = _hull_color(player.hull, player.max_hull)
    console.print(PLAYER_COL, STATS_ROW + 2,
                  f"Hull: {player.hull}/{player.max_hull}", fg=hull_color)
    console.print(PLAYER_COL, STATS_ROW + 3,
                  _hull_bar(player.hull, player.max_hull), fg=hull_color)

    console.print(PLAYER_COL, STATS_ROW + 5, f"ATK: {player.attack}",   fg=NORMAL_COLOR)
    console.print(PLAYER_COL, STATS_ROW + 6, f"DEF: {player.defense}",  fg=NORMAL_COLOR)
    console.print(PLAYER_COL, STATS_ROW + 7, f"ENG: {player.engine}",   fg=NORMAL_COLOR)

    if player.defending:
        console.print(PLAYER_COL, STATS_ROW + 9, "[DEFENDING]", fg=(100, 180, 255))

    # --- Enemy stats (right) ------------------------------------------------
    console.print(ENEMY_COL, STATS_ROW,     "ENEMY",             fg=HEADER_COLOR)
    console.print(ENEMY_COL, STATS_ROW + 1, enemy.name)

    e_hull_color = _hull_color(enemy.hull, enemy.max_hull)
    console.print(ENEMY_COL, STATS_ROW + 2,
                  f"Hull: {enemy.hull}/{enemy.max_hull}", fg=e_hull_color)
    console.print(ENEMY_COL, STATS_ROW + 3,
                  _hull_bar(enemy.hull, enemy.max_hull), fg=e_hull_color)

    # --- Divider ------------------------------------------------------------
    console.print(2, LOG_ROW - 1, "-" * (width - 4), fg=DIVIDER)

    # --- Combat log ---------------------------------------------------------
    console.print(2, LOG_ROW - 2, "Combat Log", fg=HEADER_COLOR)
    for i, line in enumerate(combat.log.lines):
        console.print(4, LOG_ROW + i, line)

    # --- Action menu or outcome --------------------------------------------
    console.print(2, ACTION_ROW - 1, "-" * (width - 4), fg=DIVIDER)

    if combat.active:
        if combat.turn == CombatManager.TURN_PLAYER:
            console.print(2, ACTION_ROW, "Your turn:", fg=HEADER_COLOR)
            for i, label in enumerate(ACTION_LABELS):
                color = SELECT_COLOR if i == state.combat_selected_action else NORMAL_COLOR
                marker = ">" if i == state.combat_selected_action else " "
                console.print(4, ACTION_ROW + 1 + i, f"{marker} {label}", fg=color)
            console.print(2, ACTION_ROW + 5,
                          "UP/DOWN - Select   ENTER - Confirm", fg=HEADER_COLOR)
        else:
            console.print(2, ACTION_ROW, "Enemy is acting...", fg=HEADER_COLOR)

    else:
        # Combat ended — show outcome
        outcome_msgs = {
            CombatManager.OUTCOME_VICTORY: (
                f"VICTORY! Salvage worth {combat.salvage} credits recovered.",
                SELECT_COLOR,
            ),
            CombatManager.OUTCOME_DEFEAT: (
                "DEFEATED. Your ship limps to the nearest station.",
                HULL_LO,
            ),
            CombatManager.OUTCOME_ESCAPED: (
                "Escaped! Your hands won't stop shaking.",
                HULL_MID,
            ),
        }
        msg, color = outcome_msgs.get(combat.outcome, ("Combat ended.", NORMAL_COLOR))
        console.print(4, ACTION_ROW, msg, fg=color)
        console.print(4, ACTION_ROW + 2, "ENTER - Continue", fg=HEADER_COLOR)
