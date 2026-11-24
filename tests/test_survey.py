"""Survey contracts (core/missions.py): generation rules and payment on arrival.

tcod is stubbed if missing; nothing here draws anything.
Run:  python -m unittest tests.test_survey -v
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

from core import missions, newgame, state, travel

SEED = 20260607


def boards(days=range(1, 9)):
    """Every contract the first few stations would post over several days."""
    out = []
    for star in state.stars[:12]:
        for loc in [*star.system.planets, *star.system.stations][:2]:
            for day in days:
                for m in missions.generate_missions(loc, star.system, state.stars, day=day):
                    out.append((star, m))
    return out


class Survey(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        state.tutorial_run = False
        newgame.build_galaxy(SEED, persist=False)
        newgame.reset_run()
        cls.all = boards()
        cls.surveys = [(s, m) for s, m in cls.all if m.mission_type == "survey"]

    def setUp(self):
        state.missions = []
        state.credits = 100
        state.completed_mission_keys = set()

    def test_surveys_are_posted(self):
        self.assertGreater(len(self.surveys), 10)
        self.assertTrue(any(m.mission_type == "cargo" for _, m in self.all))

    def test_only_cargo_and_survey_are_generated(self):
        self.assertEqual({m.mission_type for _, m in self.all}, {"cargo", "survey"})

    def test_survey_goes_far_enough_and_is_a_real_place(self):
        names = {s.name for s in state.stars}
        for star, m in self.surveys:
            jumps = travel.route_estimate(state.stars, star.name, m.dest_system)[0]
            self.assertGreaterEqual(jumps, missions.SURVEY_MIN_JUMPS, m.dest_system)
            self.assertLessEqual(jumps, missions.MAX_JUMPS[m.difficulty])
            self.assertIn(m.dest_system, names)
            self.assertNotEqual(m.dest_system, star.name)
            self.assertIsNotNone(m.key)
            self.assertEqual(m.status, "available")
            self.assertGreater(m.reward_credits, 0)

    def test_pays_more_for_longer_surveys(self):
        by_diff = {}
        for star, m in self.surveys:
            jumps = travel.route_estimate(state.stars, star.name, m.dest_system)[0]
            by_diff.setdefault(m.difficulty, []).append((jumps, m.reward_credits))
        for rows in by_diff.values():
            near = [r for j, r in rows if j == min(j for j, _ in rows)]
            far = [r for j, r in rows if j == max(j for j, _ in rows)]
            self.assertGreater(sum(far) / len(far), sum(near) / len(near) - 1)

    def test_generation_is_deterministic(self):
        again = boards(days=range(1, 4))
        first = [(m.key, m.mission_type, m.dest_system, m.reward_credits)
                 for s, m in self.all if m.day in (1, 2, 3)]
        self.assertEqual(first, [(m.key, m.mission_type, m.dest_system, m.reward_credits)
                                 for s, m in again])

    def test_all_three_objectives_are_posted(self):
        self.assertEqual({m.objective for _, m in self.surveys}, {"arrive", "land", "scan"})

    def test_object_surveys_name_a_real_planet_or_station(self):
        from core import story_relay
        for star, m in self.surveys:
            dest = next(s for s in state.stars if s.name == m.dest_system).system
            places = {o.name for o in [*dest.planets, *dest.stations]}
            if m.objective in ("land", "scan"):
                self.assertIn(m.destination, places)
                self.assertNotEqual(m.destination, story_relay.RELAY_NAME)
                self.assertIn(m.destination, m.description)
            self.assertIn(m.dest_system, m.description)

    def test_harder_asks_pay_more(self):
        by = {}
        for star, m in self.surveys:
            jumps = travel.route_estimate(state.stars, star.name, m.dest_system)[0]
            base = m.reward_credits - missions.REWARD_PER_JUMP[m.difficulty] * jumps
            by.setdefault(m.objective, []).append(base)
        avg = {k: sum(v) / len(v) for k, v in by.items()}
        self.assertGreater(avg["scan"], avg["arrive"])

    def _active(self, objective):
        _, m = next((s, m) for s, m in self.surveys if m.objective == objective)
        m = copy.copy(m)
        m.status = "active"
        state.missions = [m]
        return m

    def test_landing_pays_only_at_the_named_place(self):
        m = self._active("land")
        self.assertEqual(missions.complete_surveys(m.dest_system), [])      # arriving is not enough
        self.assertEqual(missions.complete_landings(m.dest_system, "Nowhere"), [])
        self.assertEqual(missions.complete_landings("Other System", m.destination), [])
        self.assertEqual(state.credits, 100)
        self.assertEqual(missions.complete_landings(m.dest_system, m.destination), [m])
        self.assertEqual(state.credits, 100 + m.reward_credits)
        self.assertEqual(missions.complete_landings(m.dest_system, m.destination), [])

    def test_docking_check_runs_from_the_main_loop(self):
        m = self._active("land")
        dest = next(s for s in state.stars if s.name == m.dest_system)
        loc = next(o for o in [*dest.system.planets, *dest.system.stations] if o.name == m.destination)
        state.current_star, state.current_system = dest, dest.system
        state.current_location, state.game_state = loc, "SYSTEM"
        self.assertEqual(missions.check_docked(), [])                       # flying past is not docking
        state.game_state = "LOCATION"
        self.assertEqual(missions.check_docked(), [m])

    def test_site_survey_only_pays_for_a_survey(self):
        m = self._active("scan")
        self.assertEqual(missions.complete_surveys(m.dest_system), [])
        self.assertEqual(missions.complete_landings(m.dest_system, m.destination), [])
        self.assertEqual(state.credits, 100)
        self.assertEqual(missions.complete_object_surveys(m.dest_system, "Wrong Place"), [])
        self.assertEqual(missions.complete_object_surveys(m.dest_system, m.destination), [m])
        self.assertEqual(state.credits, 100 + m.reward_credits)

    def test_arrival_completes_and_pays_once(self):
        star, m = next((s, m) for s, m in self.surveys if m.objective == "arrive")
        m = copy.copy(m)          # the class-wide boards stay untouched
        m.status = "active"
        state.missions = [m]
        done = missions.complete_surveys("Somewhere Else")
        self.assertEqual((done, state.credits), ([], 100))
        done = missions.complete_surveys(m.dest_system)
        self.assertEqual(done, [m])
        self.assertEqual(m.status, "completed")
        self.assertEqual(state.credits, 100 + m.reward_credits)
        self.assertIn(m.key, state.completed_mission_keys)
        from core import galaxy_view
        self.assertIn(m.dest_system, galaxy_view.scanned_systems())
        self.assertEqual(missions.complete_surveys(m.dest_system), [])
        self.assertEqual(state.credits, 100 + m.reward_credits)

    def test_unaccepted_survey_is_not_paid(self):
        _, m = self.surveys[0]
        m = copy.copy(m)
        m.status = "available"
        state.missions = [m]
        self.assertEqual(missions.complete_surveys(m.dest_system), [])
        self.assertEqual(state.credits, 100)

    def test_completed_survey_is_never_reposted(self):
        star, m = self.surveys[0]
        state.completed_mission_keys = {m.key}
        loc = next(l for l in [*star.system.planets, *star.system.stations] if l.name == m.source)
        again = missions.generate_missions(loc, star.system, state.stars, day=m.day,
                                           completed=state.completed_mission_keys)
        self.assertNotIn(m.key, [x.key for x in again])


class TutorialBoardsStayCargoOnly(unittest.TestCase):
    def test_tutorial_has_no_surveys(self):
        from core import tutorial
        newgame.begin_tutorial_run()
        try:
            kinds = {m.mission_type for _, m in boards(days=range(1, 4))}
        finally:
            state.tutorial_run = False
        self.assertEqual(kinds, {"cargo"})


if __name__ == "__main__":
    unittest.main()
