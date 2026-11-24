"""Pirate encounters, defeat, and hull repair (core/encounter.py, core/repair.py).

No tcod needed: these modules are pure game logic.
Run:  python -m unittest tests.test_encounters -v
"""

import random
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core import encounter, repair, state
from core.ships import PlayerShip


class FakeEconomy:
    def __init__(self, raided=()):
        self.raided = {frozenset(e) for e in raided}

    def route_raided(self, a, b):
        return frozenset((a, b)) in self.raided


class Base(unittest.TestCase):
    def setUp(self):
        self._saved = (state.credits, state.player_ship, state.economy, state.tutorial_run)
        state.credits = 1000
        state.player_ship = PlayerShip()
        state.economy = None
        state.tutorial_run = False

    def tearDown(self):
        state.credits, state.player_ship, state.economy, state.tutorial_run = self._saved


class JumpChance(Base):
    def test_depends_on_archetype(self):
        self.assertLess(encounter.jump_chance("A", "B", "Military"),
                        encounter.jump_chance("A", "B", "Frontier"))

    def test_unknown_archetype_uses_default(self):
        self.assertEqual(encounter.jump_chance("A", "B", None), encounter.DEFAULT_JUMP_CHANCE)

    def test_raid_adds_bonus_in_both_directions(self):
        state.economy = FakeEconomy([("A", "B")])
        base = encounter.ARCHETYPE_JUMP_CHANCE["Mining"]
        self.assertAlmostEqual(encounter.jump_chance("A", "B", "Mining"), base + encounter.RAID_BONUS)
        self.assertAlmostEqual(encounter.jump_chance("B", "A", "Mining"), base + encounter.RAID_BONUS)
        self.assertAlmostEqual(encounter.jump_chance("A", "C", "Mining"), base)

    def test_tutorial_has_no_pirates(self):
        state.tutorial_run = True
        random.seed(1)
        self.assertTrue(all(encounter.check_jump(state.player_ship, "A", "B", "Frontier") is None
                            for _ in range(200)))

    def test_encounter_rate_roughly_matches_chance(self):
        random.seed(7)
        n = 4000
        hits = sum(encounter.check_jump(state.player_ship, "A", "B", "Frontier") is not None
                   for _ in range(n))
        self.assertAlmostEqual(hits / n, encounter.ARCHETYPE_JUMP_CHANCE["Frontier"], delta=0.03)

    def test_old_signature_still_works(self):
        random.seed(3)
        results = [encounter.check_jump(state.player_ship) for _ in range(500)]
        self.assertTrue(any(r is not None for r in results))


class Defeat(Base):
    def test_plunders_credits_and_leaves_hull(self):
        state.player_ship.hull = 0
        lost = encounter.apply_defeat(state.player_ship)
        self.assertEqual(lost, 250)
        self.assertEqual(state.credits, 750)
        self.assertEqual(state.player_ship.hull, 20)

    def test_broke_player_survives(self):
        state.credits = 0
        state.player_ship.hull = 0
        self.assertEqual(encounter.apply_defeat(state.player_ship), 0)
        self.assertGreater(state.player_ship.hull, 0)

    def test_hull_floor_is_one(self):
        state.player_ship.max_hull = 3
        state.player_ship.hull = 0
        encounter.apply_defeat(state.player_ship)
        self.assertEqual(state.player_ship.hull, 1)


class Repair(Base):
    def test_full_repair(self):
        state.player_ship.hull = 60
        self.assertEqual(repair.cost(), 40 * repair.PRICE_PER_HULL)
        points, paid = repair.repair()
        self.assertEqual((points, paid), (40, 40 * repair.PRICE_PER_HULL))
        self.assertEqual(state.player_ship.hull, 100)
        self.assertEqual(state.credits, 1000 - paid)

    def test_partial_repair_when_short_of_credits(self):
        state.player_ship.hull = 20
        state.credits = 51
        points, paid = repair.repair()
        self.assertEqual(points, 25)
        self.assertEqual(state.player_ship.hull, 45)
        self.assertEqual(state.credits, 51 - paid)
        self.assertGreaterEqual(state.credits, 0)

    def test_nothing_to_repair_or_no_money(self):
        self.assertEqual(repair.repair(), (0, 0))
        state.player_ship.hull = 10
        state.credits = 1
        self.assertEqual(repair.repair(), (0, 0))
        self.assertEqual(state.credits, 1)

    def test_upgraded_hull_counts_damage_against_new_max(self):
        state.player_ship.max_hull = 125
        state.player_ship.hull = 100
        self.assertEqual(repair.damage(), 25)


if __name__ == "__main__":
    unittest.main()
