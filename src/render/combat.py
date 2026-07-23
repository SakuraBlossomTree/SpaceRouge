# render/combat.py
"""Render the COMBAT screen with simple ship sprites and effects."""

import time

from core import state
from core.combat import CombatManager
from effects.combat import CombatEffectManager, get_combat_layout


# ----------------------------------------------------------------------
# UI constants
# ----------------------------------------------------------------------
ACTION_LABELS = ["[A] Attack", "[D] Defend", "[E] Escape"]

SELECT_COLOR = (255, 255, 0)
NORMAL_COLOR = (255, 255, 255)
HEADER_COLOR = (140, 140, 140)

HULL_HI = (100, 220, 100)    # healthy hull
HULL_MID = (220, 220, 60)    # damaged hull
HULL_LO = (220, 60, 60)      # critical hull
DIVIDER = (80, 80, 80)


# ----------------------------------------------------------------------
# Effect manager for this screen
# ----------------------------------------------------------------------
_effects = CombatEffectManager()
_active_combat = None
_last_time = time.monotonic()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
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


# ----------------------------------------------------------------------
# Main draw function
# ----------------------------------------------------------------------
def draw(console, width, height):
    global _active_combat, _last_time

    now = time.monotonic()
    dt = min(0.1, max(0.0, now - _last_time))
    _last_time = now

    combat = state.current_combat
    if combat is None:
        _active_combat = None
        _effects.reset()
        return

    # If a new combat started, reset effects.
    if combat is not _active_combat:
        _effects.reset()
        _active_combat = combat

    layout = get_combat_layout(width, height)

    # Consume combat events emitted by core logic.
    for event in getattr(combat, "events", []):
        _effects.handle_event(event, layout)

    if hasattr(combat, "events"):
        combat.events.clear()

    # Advance animations.
    _effects.update(dt)

    player = combat.player
    enemy = combat.enemy

    stats_row = layout["stats_row"]
    player_col = layout["player_col"]
    enemy_col = layout["enemy_col"]
    log_row = layout["log_row"]
    action_row = layout["action_row"]

    # --- Title ----------------------------------------------------------
    title = "-- COMBAT --"
    console.print(width // 2 - len(title) // 2, layout["title_y"], title, fg=HEADER_COLOR)

    # --- Player stats (left) --------------------------------------------
    console.print(player_col, stats_row, "YOUR SHIP", fg=HEADER_COLOR)
    console.print(player_col, stats_row + 1, player.name)

    hull_color = _hull_color(player.hull, player.max_hull)
    console.print(
        player_col,
        stats_row + 2,
        f"Hull: {player.hull}/{player.max_hull}",
        fg=hull_color,
    )
    console.print(
        player_col,
        stats_row + 3,
        _hull_bar(player.hull, player.max_hull),
        fg=hull_color,
    )

    console.print(player_col, stats_row + 5, f"ATK: {player.attack}", fg=NORMAL_COLOR)
    console.print(player_col, stats_row + 6, f"DEF: {player.defense}", fg=NORMAL_COLOR)
    console.print(player_col, stats_row + 7, f"ENG: {player.engine}", fg=NORMAL_COLOR)

    if player.defending:
        console.print(player_col, stats_row + 9, "[DEFENDING]", fg=(100, 180, 255))

    # --- Enemy stats (right) --------------------------------------------
    console.print(enemy_col, stats_row, "ENEMY", fg=HEADER_COLOR)
    console.print(enemy_col, stats_row + 1, enemy.name)

    e_hull_color = _hull_color(enemy.hull, enemy.max_hull)
    console.print(
        enemy_col,
        stats_row + 2,
        f"Hull: {enemy.hull}/{enemy.max_hull}",
        fg=e_hull_color,
    )
    console.print(
        enemy_col,
        stats_row + 3,
        _hull_bar(enemy.hull, enemy.max_hull),
        fg=e_hull_color,
    )

    # --- Combat log -----------------------------------------------------
    console.print(2, log_row - 1, "-" * (width - 4), fg=DIVIDER)
    console.print(2, log_row - 2, "Combat Log", fg=HEADER_COLOR)

    for i, line in enumerate(combat.log.lines):
        console.print(4, log_row + i, line)

    # --- Ships + visual effects -----------------------------------------
    # Draw after UI text so ships/effects are visible.
    _effects.draw_ships(console, layout, combat)
    _effects.draw_effects(console)

    # --- Action menu or outcome -----------------------------------------
    console.print(2, action_row - 1, "-" * (width - 4), fg=DIVIDER)

    if combat.active:
        if combat.turn == CombatManager.TURN_PLAYER:
            console.print(2, action_row, "Your turn:", fg=HEADER_COLOR)

            # Simple selection pulse.
            blink = int(now * 3) % 2 == 0

            for i, label in enumerate(ACTION_LABELS):
                if i == state.combat_selected_action:
                    color = (255, 255, 150) if blink else SELECT_COLOR
                    marker = ">"
                else:
                    color = NORMAL_COLOR
                    marker = " "

                console.print(4, action_row + 1 + i, f"{marker} {label}", fg=color)

            console.print(
                2,
                action_row + 5,
                "UP/DOWN - Select   ENTER - Confirm",
                fg=HEADER_COLOR,
            )
        else:
            console.print(2, action_row, "Enemy is acting...", fg=HEADER_COLOR)
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
        console.print(4, action_row, msg, fg=color)
        console.print(4, action_row + 2, "ENTER - Continue", fg=HEADER_COLOR)