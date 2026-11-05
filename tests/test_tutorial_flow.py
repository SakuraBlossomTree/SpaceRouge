"""Tutorial: the fixed practice galaxy, the hand-off to the real game, and
that the handbook / tutorial text still fits and reads its numbers from the game."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core import encounter, fonts, newgame, notebook, pricelog, state, travel, tutorial
from core import save as savegame
from core.entities import ITEMS
from core.missions import generate_missions

REAL_SEED = 424242


def _quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class PracticeGalaxyTests(unittest.TestCase):
    """The tutorial seed has to keep teaching the steps it describes."""

    @classmethod
    def setUpClass(cls):
        _quiet(newgame.build_galaxy, tutorial.TUTORIAL_SEED, persist=False)
        cls.sol = next(s for s in state.stars if s.name == "Sol")

    def test_earth_has_a_market_and_sol_has_gates(self):
        earth = self.sol.system.planets[0]
        self.assertEqual(earth.name, "Earth")
        self.assertTrue(earth.market)
        self.assertTrue(self.sol.system.jump_points)

    def test_earth_posts_short_affordable_deliveries(self):
        state.day = 1
        earth = self.sol.system.planets[0]
        board = generate_missions(earth, self.sol.system, state.stars,
                                  count=4, completed=set(), day=1)
        easy = []
        for m in board:
            if m.mission_type != "cargo":
                continue
            fits = ITEMS[m.cargo].size * m.amount <= state.STARTING_CARGO
            route = travel.route_estimate(state.stars, "Sol", m.dest_system)
            if fits and route and route[0] <= 2 and route[1] <= state.STARTING_FUEL:
                easy.append(m)
        self.assertGreaterEqual(len(easy), 2, "tutorial board needs short, fitting contracts")


class TutorialRunTests(unittest.TestCase):
    def setUp(self):
        state.tutorial_run = False
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.patches = [
            mock.patch.object(savegame, "SAVE_PATH", tmp / "save.json"),
            mock.patch.object(pricelog, "PATH", tmp / "pricelog.json"),
            mock.patch.object(notebook, "PATH", tmp / "notebook.json"),
            mock.patch.object(pricelog, "_data", {}),
            mock.patch.object(notebook, "_data", {}),
            mock.patch.object(fonts, "settings", return_value={"tutorial": True}),
            mock.patch.object(fonts, "save_settings"),
        ]
        for p in self.patches:
            p.start()
        _quiet(newgame.build_galaxy, REAL_SEED, persist=True)
        self.save_path = tmp / "save.json"

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        state.tutorial_run = False
        state.real_seed = None
        self.tmp.cleanup()

    def test_enter_loads_the_practice_galaxy_and_saves_nothing(self):
        before = self.save_path.read_text()
        _quiet(newgame.begin_tutorial_run)
        self.assertTrue(state.tutorial_run)
        self.assertEqual(state.galaxy_seed, tutorial.TUTORIAL_SEED)
        self.assertEqual(state.real_seed, REAL_SEED)
        self.assertIsNone(savegame.save_progress())
        self.assertEqual(self.save_path.read_text(), before)
        self.assertEqual(json.loads(before)["seed"], REAL_SEED)

    def test_no_pirates_in_the_practice_galaxy(self):
        _quiet(newgame.begin_tutorial_run)
        self.assertIsNone(encounter.roll_encounter(1.0, state.player_ship))

    def test_finishing_starts_a_fresh_real_game(self):
        _quiet(newgame.begin_tutorial_run)
        # mess the practice run up: spend money, take debt, move the clock
        state.credits, state.debt, state.day, state.fuel = 7, 1, 20, 3
        state.messages.append("practice message")
        state.tutorial_active = True
        state.tutorial_step = len(tutorial.STEPS) - 1
        state.game_state = "SYSTEM"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(tutorial.on_space())

        self.assertFalse(state.tutorial_run)
        self.assertEqual(state.galaxy_seed, REAL_SEED)
        self.assertEqual(json.loads(self.save_path.read_text())["seed"], REAL_SEED)
        self.assertEqual(state.credits, state.STARTING_CREDITS)
        self.assertEqual(state.debt, state.starting_debt)
        self.assertEqual(state.day, 1)
        self.assertEqual(state.fuel, state.STARTING_FUEL)
        self.assertEqual(state.inventory.space, state.STARTING_CARGO)
        self.assertFalse(state.inventory.items)
        self.assertEqual(state.game_state, "SYSTEM")
        self.assertEqual(state.current_system.name, "Sol")
        self.assertNotIn("practice message", state.messages)
        self.assertFalse(tutorial.enabled())
        self.assertFalse(state.tutorial_active)

    def test_practice_notes_and_prices_start_empty_each_time(self):
        state.galaxy_seed = tutorial.TUTORIAL_SEED
        notebook.add("old practice note")
        _quiet(newgame.begin_tutorial_run)
        self.assertEqual(notebook.notes(), [])


class TextTests(unittest.TestCase):
    def setUp(self):
        _quiet(newgame.build_galaxy, REAL_SEED, persist=False)

    def test_every_tutorial_step_has_text(self):
        for step in tutorial.STEPS:
            self.assertTrue(tutorial.body_text(step).strip(), step[0])

    def test_tutorial_and_handbook_quote_the_real_loan(self):
        from core import debt
        from render import help as handbook
        quoted = f"{state.starting_debt:,}"
        days = f"{debt.loan_days()} days"
        self.assertIn(quoted, tutorial.body_text(tutorial.STEPS[0]))
        self.assertIn(days, tutorial.body_text(tutorial.STEPS[0]))
        goal = handbook._expand(handbook.PAGES[0][1])[1]
        self.assertIn(quoted, goal)
        self.assertIn(days, goal)

    def test_handbook_pages_fit_the_window(self):
        from render import help as handbook, ui
        iw = handbook.W - 6
        avail = min(46, ui.MAP_H - 2) - 3 - 6
        for title, paras in handbook.PAGES:
            rows = 0
            for p in handbook._expand(paras):
                if p.startswith("*"):
                    rows += (1 if rows else 0) + 1
                elif " | " in p:
                    key, desc = p.split(" | ", 1)
                    self.assertLessEqual(len(key), 15, f"{title}: key {key!r} overlaps its text")
                    self.assertLessEqual(len(desc), iw - 17, f"{title}: {desc!r} is cut off")
                    rows += 1
                else:
                    rows += len(ui.wrap(p, iw))
            self.assertLessEqual(rows, avail, f"handbook page {title!r} overflows")
        self.assertEqual(len(handbook.TABS), len(handbook.PAGES))


if __name__ == "__main__":
    unittest.main()
