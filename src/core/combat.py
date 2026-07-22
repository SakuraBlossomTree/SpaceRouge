"""CombatManager — owns a single combat encounter from start to finish.

Does NOT handle drawing or input — those live in render/combat.py and
core/events.py respectively. This module is pure game logic.
"""

import random


class CombatLog:
    """Rolling message log for combat events."""

    def __init__(self, max_lines=6):
        self.lines = []
        self.max_lines = max_lines

    def add(self, text):
        self.lines.append(text)
        if len(self.lines) > self.max_lines:
            self.lines.pop(0)

    def clear(self):
        self.lines = []


class CombatManager:
    """Manages one combat encounter between the player ship and an enemy."""

    # Possible outcomes set on combat end
    OUTCOME_VICTORY = "VICTORY"
    OUTCOME_DEFEAT  = "DEFEAT"
    OUTCOME_ESCAPED = "ESCAPED"

    # Turn owners
    TURN_PLAYER = "PLAYER"
    TURN_ENEMY  = "ENEMY"

    def __init__(self, player_ship, enemy_ship):
        self.player = player_ship
        self.enemy  = enemy_ship

        self.turn    = self.TURN_PLAYER
        self.outcome = None          # set when combat ends
        self.active  = True          # False once combat is resolved
        self.salvage = 0             # credits worth of loot on victory

        self.log = CombatLog()
        self.log.add(f"A {enemy_ship.name} attacks!")

    # ------------------------------------------------------------------
    # Player actions
    # ------------------------------------------------------------------

    def player_attack(self):
        """Player attacks the enemy."""
        if not self._player_can_act():
            return

        damage = self.player.attack + random.randint(-3, 3)
        actual = self.enemy.take_damage(damage)
        self.log.add(f"You fire! {actual} damage to {self.enemy.name}.")

        if not self.enemy.is_alive():
            self._resolve_victory()
            return

        self._end_player_turn()

    def player_defend(self):
        """Player braces — reduces incoming damage this round."""
        if not self._player_can_act():
            return

        self.player.defending = True
        self.log.add("You brace for impact. Defense doubled this turn.")
        self._end_player_turn()

    def player_escape(self):
        """Player attempts to flee. Success depends on engine ratings."""
        if not self._player_can_act():
            return

        # Higher player engine vs enemy engine = better escape chance
        escape_chance = 0.3 + (self.player.engine - self.enemy.engine) * 0.04
        escape_chance = max(0.1, min(0.9, escape_chance))   # clamp 10%-90%

        if random.random() < escape_chance:
            self.log.add("Engines at full burn — you escape!")
            self._end_combat(self.OUTCOME_ESCAPED)
        else:
            self.log.add("Escape failed! The enemy cuts you off.")
            self._end_player_turn()

    # ------------------------------------------------------------------
    # Enemy turn (called automatically after player acts)
    # ------------------------------------------------------------------

    def _enemy_turn(self):
        """Simple enemy AI — always attacks for now."""
        if not self.active:
            return

        self.enemy.reset_turn_modifiers()

        damage = self.enemy.attack + random.randint(-2, 2)
        actual = self.player.take_damage(damage)
        self.log.add(f"{self.enemy.name} fires! {actual} damage to your hull.")

        if not self.player.is_alive():
            self._resolve_defeat()
            return

        self.player.reset_turn_modifiers()
        self.turn = self.TURN_PLAYER

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _player_can_act(self):
        return self.active and self.turn == self.TURN_PLAYER

    def _end_player_turn(self):
        self.turn = self.TURN_ENEMY
        self._enemy_turn()

    def _resolve_victory(self):
        self.salvage = self.enemy.loot_value + random.randint(0, 10)
        self.log.add(f"{self.enemy.name} destroyed! Salvage: {self.salvage} credits.")
        self._end_combat(self.OUTCOME_VICTORY)

    def _resolve_defeat(self):
        self.log.add("Hull breached. Systems failing...")
        self._end_combat(self.OUTCOME_DEFEAT)

    def _end_combat(self, outcome):
        self.outcome = outcome
        self.active  = False
