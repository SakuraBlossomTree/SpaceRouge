"""Saving and resuming a run (core/save.py, core/newgame.py continue_run).

Uses a temporary save file. tcod is stubbed if it isn't installed, since the
save code never draws anything.
Run:  python -m unittest tests.test_save_run -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    import tcod  # noqa: F401
except ImportError:                       # headless: the save code doesn't need it
    for _name in ("tcod", "tcod.event", "tcod.console", "tcod.context",
                  "tcod.tileset", "miniaudio", "numpy"):
        sys.modules[_name] = MagicMock()

from core import economy, encounter, newgame, state
from core import save as savegame
from core.entities import Item
from core.missions import Mission

SEED = 424242


class RunSaveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls._old_path = savegame.SAVE_PATH

    @classmethod
    def tearDownClass(cls):
        savegame.SAVE_PATH = cls._old_path
        cls._dir.cleanup()

    def setUp(self):
        savegame.SAVE_PATH = Path(self._dir.name) / "save.json"
        if savegame.SAVE_PATH.exists():
            savegame.SAVE_PATH.unlink()
        state.tutorial_run = False
        state.story_texts = []
        newgame.build_galaxy(SEED, persist=False)
        newgame.reset_run()

    def _play(self):
        """Put the run into a recognisable mid-game state, docked at Sol."""
        sol = next(s for s in state.stars if s.name == "Sol")
        state.current_star, state.current_system = sol, sol.system
        loc = sol.system.planets[0]
        state.current_location = state.current_object = loc
        state.game_state = "LOCATION"
        state.credits = 777
        state.fuel, state.max_fuel = 63.5, 150
        state.day = 23
        state.debt = 4100
        state.player_ship.max_hull, state.player_ship.hull = 125, 40
        state.inventory.space = 30
        state.inventory.items = [Item("Food", 1), Item("Ore", 2, origin_system="Sol", mission_key="k1")]
        state.upgrades = {"cargo": 1, "fuel": 1, "hull": 1, "scanrange": 1}
        state.cost_basis = {"Food": [1, 9.5]}
        state.completed_mission_keys = {"done-1"}
        state.missions = [
            Mission("M1", "Haul", "Take ore.", "cargo", 300, [], "active", loc.name,
                    "Elsewhere", 2, cargo="Ore", amount=1, dest_system="Alpha Prime",
                    source_system="Sol", key="k1"),
            Mission("M2", "Not taken", "Nope.", "cargo", 100, [], "available", loc.name,
                    "Elsewhere", 1, key="k2"),
        ]
        newgame.begin_run()
        savegame.save_progress()

    def test_round_trip(self):
        self._play()
        self.assertTrue(savegame.saved_run())
        newgame.build_galaxy(1, persist=False)          # title shows another galaxy
        newgame.reset_run()
        newgame.refresh_continue()
        self.assertEqual(state.continue_info["day"], 23)

        self.assertTrue(newgame.continue_run())
        self.assertEqual(state.galaxy_seed, SEED)
        self.assertEqual((state.credits, state.day, state.debt), (777, 23, 4100))
        self.assertEqual((state.fuel, state.max_fuel), (63.5, 150))
        self.assertEqual((state.player_ship.hull, state.player_ship.max_hull), (40, 125))
        self.assertEqual(state.inventory.space, 30)
        self.assertEqual([(i.name, i.size, i.origin_system, i.mission_key)
                          for i in state.inventory.items],
                         [("Food", 1, None, None), ("Ore", 2, "Sol", "k1")])
        self.assertEqual(state.upgrades["cargo"], 1)
        self.assertEqual(state.upgrades["scanrange"], 1)
        self.assertEqual(state.cost_basis, {"Food": [1, 9.5]})
        self.assertEqual(state.completed_mission_keys, {"done-1"})
        self.assertEqual([m.key for m in state.missions], ["k1"])       # only the active one
        self.assertEqual(state.missions[0].dest_system, "Alpha Prime")
        self.assertEqual(state.game_state, "LOCATION")
        self.assertEqual(state.current_location.name, state.current_system.planets[0].name)
        self.assertTrue(state.run_active)

    def test_economy_fast_forward_matches_playing(self):
        """Resuming at day 23 rebuilds the same markets as ticking there."""
        for _ in range(23 // economy.PRICE_UPDATE_DAYS):
            economy.tick(economy.PRICE_UPDATE_DAYS)
        played = {ms.id: dict(ms.market) for ms in state.economy.markets}
        self._play()
        self.assertTrue(newgame.continue_run())
        resumed = {ms.id: dict(ms.market) for ms in state.economy.markets}
        self.assertEqual(played, resumed)

    def test_game_over_clears_the_run(self):
        self._play()
        savegame.clear_run()
        self.assertIsNone(savegame.saved_run())
        self.assertFalse(state.run_active)
        self.assertIn("seed", json.loads(savegame.SAVE_PATH.read_text()))   # galaxy seed kept

    def test_run_survives_title_changes(self):
        """Picking another galaxy on the title must not delete the saved run."""
        self._play()
        state.run_active = False
        newgame.build_galaxy(99, persist=True)
        self.assertEqual(savegame.saved_run()["seed"], SEED)

    def test_corrupt_saves_do_not_crash(self):
        for bad in ('not json', '{"run": 5}', '{"run": {"version": 1}}',
                    '{"run": {"version": 1, "seed": 1, "day": 3, "system": "Nowhere"}}'):
            savegame.SAVE_PATH.write_text(bad)
            newgame.refresh_continue()
            if state.continue_info:               # looks usable but doesn't fit the galaxy
                self.assertFalse(newgame.continue_run())
                self.assertEqual(state.game_state, "TITLE")
            self.assertFalse(state.run_active)

    def test_autosave_only_when_something_changed(self):
        self._play()
        savegame.SAVE_PATH.unlink()
        savegame.reset_autosave()
        self.assertTrue(savegame.autosave())
        self.assertFalse(savegame.autosave())
        state.credits += 5
        self.assertTrue(savegame.autosave())
        self.assertEqual(savegame.saved_run()["credits"], 782)

    def test_autosave_skips_combat_and_tutorial(self):
        self._play()
        savegame.reset_autosave()
        state.game_state = "COMBAT"
        self.assertFalse(savegame.autosave())
        state.game_state, state.tutorial_run = "SYSTEM", True
        self.assertFalse(savegame.autosave())

    def test_quitting_mid_fight_counts_as_a_defeat(self):
        from core.combat import CombatManager
        from core.ships import spawn_pirate
        self._play()
        state.credits = 1000
        state.player_ship.hull = 100
        state.current_combat = CombatManager(state.player_ship, spawn_pirate())
        state.game_state = "COMBAT"
        savegame.on_exit()
        run = savegame.saved_run()
        self.assertEqual(run["credits"], 1000 - int(1000 * encounter.PLUNDER_SHARE))
        self.assertEqual(run["hull"], int(125 * encounter.DEFEAT_HULL_SHARE))


if __name__ == "__main__":
    unittest.main()
