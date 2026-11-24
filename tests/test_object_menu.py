"""Ship menu (S) and surveying an object (V) (core/listmenu.py,
core/survey.py). tcod is stubbed if missing.
Run:  python -m unittest tests.test_object_menu -v
"""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    import tcod  # noqa: F401
except ImportError:
    for _name in ("tcod", "tcod.event", "tcod.console", "tcod.context",
                  "tcod.tileset", "miniaudio", "numpy"):
        sys.modules[_name] = MagicMock()

from core import events, listmenu, missions, newgame, state, survey
from core.missions import Mission

K = sys.modules["tcod"].event.KeySym


class Ev:
    def __init__(self, sym, mod=0):
        self.sym, self.mod = sym, mod


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        state.tutorial_run = False
        newgame.build_galaxy(777, persist=False)
        newgame.reset_run()

    def setUp(self):
        newgame.reset_run()
        state.surveyed_objects = set()
        state.missions = []
        state.completed_mission_keys = set()
        star = next(s for s in state.stars if s.name == "Sol")
        state.current_star, state.current_system = star, star.system
        self.planet = star.system.planets[0]
        self.gate = star.system.jump_points[0]
        state.game_state = "SYSTEM"
        self.sit_on(self.planet)

    def sit_on(self, obj):
        state.system_player_x, state.system_player_y = obj.x, obj.y

    def scan_contract(self, obj):
        m = Mission("S1", "Site Survey", "x", "survey", 300, [], "active", "Earth", obj.name, 2,
                    dest_system=state.current_system.name, source_system="Elsewhere",
                    key="k-scan", objective="scan")
        state.missions = [m]
        return m


class Survey(Base):
    def test_object_at_ship(self):
        self.assertIs(survey.object_at_ship(), self.planet)
        self.sit_on(self.gate)
        self.assertIs(survey.object_at_ship(), self.gate)
        state.system_player_x += 1
        self.assertIsNone(survey.object_at_ship())

    def test_survey_burns_fuel_once_and_reports(self):
        before = state.fuel
        survey.survey_object(self.planet)
        self.assertEqual(state.fuel, before - survey.SURVEY_FUEL)
        self.assertTrue(survey.is_surveyed(self.planet))
        self.assertTrue(any("Survey report" in m for m in state.messages))
        survey.survey_object(self.planet)                    # again: refused, free
        self.assertEqual(state.fuel, before - survey.SURVEY_FUEL)

    def test_survey_completes_the_site_contract(self):
        m = self.scan_contract(self.planet)
        credits = state.credits
        done = survey.survey_object(self.planet)
        self.assertEqual(done, [m])
        self.assertEqual(m.status, "completed")
        self.assertEqual(state.credits, credits + 300)

    def test_wrong_object_does_not_complete_it(self):
        other = state.current_system.stations[0] if state.current_system.stations else None
        if other is None:
            self.skipTest("Sol has no station")
        m = self.scan_contract(self.planet)
        survey.survey_object(other)
        self.assertEqual(m.status, "active")

    def test_never_leaves_you_too_dry_for_a_gate(self):
        state.fuel = survey._cheapest_jump() + survey.SURVEY_FUEL - 1
        ok, why = survey.can_survey(self.planet)
        self.assertFalse(ok)
        before = state.fuel
        survey.survey_object(self.planet)
        self.assertEqual(state.fuel, before)
        self.assertFalse(survey.is_surveyed(self.planet))
        state.fuel += 1
        self.assertTrue(survey.can_survey(self.planet)[0])

    def test_gates_cannot_be_surveyed(self):
        self.assertFalse(survey.can_survey(self.gate)[0])

    def test_handing_in_a_site_survey_on_the_board_pays_nothing(self):
        m = self.scan_contract(self.planet)
        state.current_location = self.planet
        state.visible_missions = [m]
        state.selected_mission_index = 0
        state.game_state = "MISSIONS"
        credits = state.credits
        events._missions(Ev(K.RETURN), "")
        self.assertEqual((m.status, state.credits), ("active", credits))


class SurveyKey(Base):
    def test_v_surveys_the_object_under_the_ship(self):
        fuel = state.fuel
        survey.survey_here()
        self.assertTrue(survey.is_surveyed(self.planet))
        self.assertEqual(state.fuel, fuel - survey.SURVEY_FUEL)

    def test_v_in_open_space_says_so(self):
        state.system_player_x += 1
        fuel = state.fuel
        self.assertEqual(survey.survey_here(), [])
        self.assertEqual(state.fuel, fuel)
        self.assertIn("Nothing to survey", state.messages[-1])

    def test_v_on_a_gate_is_refused(self):
        self.sit_on(self.gate)
        fuel = state.fuel
        survey.survey_here()
        self.assertEqual(state.fuel, fuel)

    def test_v_key_in_the_system_screen(self):
        events._system(Ev(K.V), "")
        self.assertTrue(survey.is_surveyed(self.planet))

    def test_v_completes_a_site_contract(self):
        m = self.scan_contract(self.planet)
        events._system(Ev(K.V), "")
        self.assertEqual(m.status, "completed")


class ShipMenu(Base):
    def test_in_space_refuel_and_repair_need_docking(self):
        state.player_ship.hull = 50
        state.fuel = 10
        _, _, info, items = listmenu.ship_menu()
        by = {i["label"]: i for i in items}
        self.assertFalse(by["Refuel"]["enabled"])
        self.assertFalse(by["Repair hull"]["enabled"])
        self.assertEqual(by["Refuel"]["note"], "dock first")
        self.assertTrue(by["Cargo hold"]["enabled"])
        self.assertIn("Fuel", dict(info))

    def test_docked_refuel_and_repair_work(self):
        state.current_location = self.planet
        state.game_state = "LOCATION"
        state.player_ship.hull = 50
        state.fuel = 10
        state.credits = 5000
        _, _, _, items = listmenu.ship_menu()
        by = {i["label"]: i for i in items}
        self.assertTrue(by["Repair hull"]["enabled"])
        by["Repair hull"]["action"]()
        self.assertEqual(state.player_ship.hull, state.player_ship.max_hull)
        if by["Refuel"]["enabled"]:
            by["Refuel"]["action"]()
            self.assertEqual(state.fuel, state.max_fuel)

    def test_open_and_close_with_s(self):
        listmenu.open_ship_menu()
        self.assertEqual(state.list_menu, "ship")
        listmenu.handle(Ev(K.S))
        self.assertIsNone(state.list_menu)

    def test_keys(self):
        listmenu.open_ship_menu()
        first = state.list_menu_index
        listmenu.handle(Ev(K.DOWN))
        self.assertNotEqual(state.list_menu_index, first)
        listmenu.handle(Ev(K.UP))
        self.assertEqual(state.list_menu_index, first)
        listmenu.handle(Ev(K.ESCAPE))
        self.assertIsNone(state.list_menu)

    def test_number_key_picks_a_row(self):
        listmenu.open_ship_menu()
        listmenu.handle(Ev([k for k, v in listmenu.NUMBER_KEYS.items() if v == 0][0]))
        self.assertEqual(state.game_state, "INVENTORY")
        self.assertIsNone(state.list_menu)

    def test_everything_opens_the_quick_menu(self):
        listmenu.open_ship_menu()
        _, _, _, items = listmenu.current()
        listmenu.handle(Ev([k for k, v in listmenu.NUMBER_KEYS.items() if v == len(items) - 1][0]))
        self.assertTrue(state.quick_menu)
        state.quick_menu = False


class SaveRoundTrip(Base):
    def test_objective_and_surveyed_survive_a_save(self):
        import tempfile
        from core import save as savegame
        old = savegame.SAVE_PATH
        savegame.SAVE_PATH = Path(tempfile.mkdtemp()) / "save.json"
        try:
            m = self.scan_contract(self.planet)
            survey.survey_object(self.planet) if False else state.surveyed_objects.add(survey.key(self.planet))
            newgame.begin_run()
            savegame.save_progress()
            newgame.build_galaxy(1, persist=False)
            newgame.reset_run()
            self.assertTrue(newgame.continue_run())
            self.assertEqual(state.missions[0].objective, "scan")
            self.assertEqual(state.missions[0].destination, self.planet.name)
            self.assertIn(survey.key(self.planet), state.surveyed_objects)
        finally:
            savegame.SAVE_PATH = old
            state.run_active = False


if __name__ == "__main__":
    unittest.main()
