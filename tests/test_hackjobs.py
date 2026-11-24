"""Procedural hacking jobs: generator, data nodes, boards, deck, rewards, heat.
Run:  python -m unittest tests.test_hackjobs -v
"""

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
except ImportError:
    for _name in ("tcod", "tcod.event", "tcod.console", "tcod.context",
                  "tcod.tileset", "miniaudio", "numpy"):
        sys.modules[_name] = MagicMock()

from core import hackjobs, listmenu, newgame, shipyard, state
from hacking import missions
from hacking.computer import Computer
from hacking.missions import procedural
from hacking.terminal import Terminal


def play(mid, cmds=None):
    s = missions.build(mid)
    t = Terminal(s)
    for c in cmds if cmds is not None else procedural.solution(mid):
        t.execute(c)
    return s


class Generator(unittest.TestCase):
    def test_every_seed_is_solvable_and_deterministic(self):
        for tier in (1, 2):
            for seed in range(120):
                mid = procedural.make_id(tier, seed)
                self.assertEqual(play(mid).mission.status, "success", mid)
                a, b = missions.build(mid), missions.build(mid)
                self.assertEqual(a.mission.title, b.mission.title)
                self.assertEqual(procedural.solution(mid), procedural.solution(mid))

    def test_jobs_differ_and_have_both_tiers(self):
        titles = {procedural.describe(1, s)[0] for s in range(60)}
        self.assertGreater(len(titles), 20)
        self.assertEqual(len(missions.build(procedural.make_id(1, 5)).networks[
            missions.build(procedural.make_id(1, 5)).device.contacts[0][1]].hosts), 2)
        s2 = missions.build(procedural.make_id(2, 5))
        self.assertEqual(len(next(iter(s2.networks.values())).hosts), 3)

    def test_the_loud_shortcut_works_but_burns_trace(self):
        mid = procedural.make_id(1, 3)
        sol = procedural.solution(mid)
        vault = next(c for c in sol if c.startswith("probe ")).split()[1]
        s = play(mid, ["connect " + sol[0].split()[1], "scan", f"probe {vault}",
                       f"breach {vault} ftp-overflow"])
        self.assertGreaterEqual(s.peak_trace(), 40)

    def test_no_retry_for_jobs_but_prototype_keeps_it(self):
        self.assertFalse(Computer(procedural.make_id(1, 1)).can_retry)
        self.assertTrue(Computer(missions.DEFAULT).can_retry)

    def test_the_story_missions_are_untouched(self):
        self.assertIn("unsent_message", missions.MISSIONS)
        self.assertEqual(missions.build("corporate_archive").mission.id, "corporate_archive")


class World(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        state.tutorial_run = False
        newgame.build_galaxy(777, persist=False)

    def setUp(self):
        newgame.reset_run()
        state.hack_done, state.hack_lock = {}, {}
        state.heat = state.heat_day = 0
        state.upgrades = {}
        state.day = 10
        hackjobs._running.clear()
        hackjobs._handled = None
        from core import computer_input
        computer_input.computer = None
        self.nodes = [s for s in state.stars if hackjobs.is_node(s)]
        self.node = self.nodes[0]
        self.station = next(x for x in self.node.system.stations if hackjobs._has_terminal(x))
        self.plain = next(s for s in state.stars if not hackjobs.is_node(s) and s.system.stations)

    def dock(self, star, loc):
        state.current_star, state.current_system = star, star.system
        state.current_location, state.game_state = loc, "LOCATION"

    def finish(self, job, solve=True):
        hackjobs.start(job)
        from core import computer_input
        comp = computer_input.computer
        t = comp.terminal
        cmds = procedural.solution(job.mission_id) if solve else \
            ["connect " + procedural.solution(job.mission_id)[0].split()[1], "scan", "scan"]
        if not solve:                      # burn the trace out loudly
            vault = next(c for c in procedural.solution(job.mission_id) if c.startswith("probe ")).split()[1]
            cmds += [f"probe {vault}", f"breach {vault} token-replay WRONG"] * 8
        for c in cmds:
            t.execute(c)
        computer_input.update()
        return comp


class Nodes(World):
    def test_nodes_are_a_minority_and_seeded(self):
        total = len(state.stars)
        self.assertGreater(len(self.nodes), 0)
        self.assertLess(len(self.nodes), total * 0.5)
        self.assertEqual(self.nodes, [s for s in state.stars if hackjobs.is_node(s)])

    def test_relay_system_and_stationless_systems_are_never_nodes(self):
        relay = next(s for s in state.stars if s.name == state.relay["system"])
        self.assertFalse(hackjobs.is_node(relay))
        for s in state.stars:
            if not s.system.stations:
                self.assertFalse(hackjobs.is_node(s))

    def test_board_rules(self):
        self.dock(self.node, self.station)
        self.assertEqual(hackjobs.board(), (self.node, "terminal"))
        self.dock(self.plain, self.plain.system.stations[0])
        self.assertIsNone(hackjobs.board())                 # no terminal, no deck

    def test_planets_have_no_terminal_without_a_deck(self):
        if not self.node.system.planets:
            self.skipTest("no planet")
        self.dock(self.node, self.node.system.planets[0])
        self.assertIsNone(hackjobs.board())

    def test_deck_reaches_nearby_nodes_from_any_dock(self):
        state.upgrades["hackdeck"] = 1
        for s in state.stars:
            near = hackjobs._nearby_nodes(s.name)
            if near and not hackjobs.is_node(s):
                loc = next((o for o in [*s.system.planets, *s.system.stations]
                            if not o.name.startswith("Earth")), None)
                if loc is None:
                    continue
                self.dock(s, loc)
                star, via = hackjobs.board()
                self.assertEqual(via, "deck")
                self.assertIs(star, near[0][1])
                return
        self.skipTest("no non-node system near a node")

    def test_deck_is_bought_at_the_shipyard(self):
        state.credits = 5000
        ok, _ = shipyard.buy("hackdeck")
        self.assertTrue(ok)
        self.assertTrue(hackjobs.has_deck())
        self.assertEqual(shipyard.current_text("hackdeck"), "installed")
        self.assertFalse(shipyard.buy("hackdeck")[0])


class Jobs(World):
    def test_boards_are_stable_per_day_and_change_daily(self):
        a = hackjobs.jobs(self.node, 10)
        self.assertEqual([j.key for j in a], [j.key for j in hackjobs.jobs(self.node, 10)])
        self.assertTrue(4 <= len(a) <= 6)
        self.assertNotEqual([j.seed for j in a], [j.seed for j in hackjobs.jobs(self.node, 11)])

    def test_success_pays_once_and_marks_done(self):
        self.dock(self.node, self.station)
        job = hackjobs.jobs(self.node)[0]
        before = state.credits
        self.finish(job)
        self.assertEqual(state.credits, before + job.reward)
        self.assertEqual(hackjobs.status(job), "done")
        from core import computer_input
        hackjobs.on_computer_update(computer_input.computer)   # a second pass pays nothing
        self.assertEqual(state.credits, before + job.reward)
        self.assertFalse(hackjobs.available(job))

    def test_failure_locks_the_node_until_tomorrow_and_adds_heat(self):
        self.dock(self.node, self.station)
        job = hackjobs.jobs(self.node)[0]
        before = state.credits
        self.finish(job, solve=False)
        self.assertEqual(hackjobs.status(job), "failed")
        self.assertEqual(state.credits, before)
        self.assertEqual(hackjobs.locked_until(self.node.name), 10)
        self.assertFalse(any(hackjobs.available(j) for j in hackjobs.jobs(self.node)))
        self.assertEqual(hackjobs.heat(), hackjobs.HEAT_FAIL)
        state.day = 11                                         # next day: fresh board
        self.assertIsNone(hackjobs.locked_until(self.node.name))
        self.assertTrue(all(hackjobs.available(j) for j in hackjobs.jobs(self.node)))

    def test_heat_cools_and_is_capped(self):
        hackjobs.add_heat(15)
        self.assertEqual(hackjobs.heat(), 15)
        state.day += 4
        self.assertEqual(hackjobs.heat(), 13)
        hackjobs.add_heat(500)
        self.assertEqual(hackjobs.heat(), 100)


class MissionsBoard(World):
    def open_board(self, tab=0):
        from core import events
        self.dock(self.node, self.station)
        state.missions = []
        events._open_missions(tab=tab)

    def test_computer_row_opens_the_hacking_tab(self):
        from core import events
        from render import location
        self.dock(self.node, self.station)
        self.assertTrue(location.has_computer())
        enabled, text, _ = location.item_status("computer")
        self.assertTrue(enabled)
        self.assertIn("job", text)
        events._open_computer()
        self.assertEqual(state.game_state, "MISSIONS")
        self.assertEqual(state.mission_tab, 3)
        self.assertEqual(len(state.visible_missions), len(hackjobs.jobs(self.node)))
        self.assertTrue(all(m.mission_type == "hackjob" for m in state.visible_missions))

    def test_categories_filter_the_board(self):
        from core import events
        self.open_board()
        everything = list(state.visible_missions)
        hacks = [m for m in everything if m.mission_type == "hackjob"]
        self.assertTrue(hacks)
        self.assertEqual(len(everything), len(state.board_missions))
        events.set_mission_tab(3)
        self.assertEqual(state.visible_missions, hacks)
        events.set_mission_tab(1)
        self.assertTrue(all(m.mission_type == "cargo" for m in state.visible_missions))
        events.set_mission_tab(0)
        self.assertEqual(len(state.visible_missions), len(everything))
        events.set_mission_tab(-1)                      # wraps around
        self.assertEqual(state.mission_tab, 3)

    def test_left_right_change_the_category(self):
        from core import events
        self.open_board()
        Ev = lambda sym: type("E", (), {"sym": sym, "mod": 0})()
        events._missions(Ev(events.tcod.event.KeySym.RIGHT), "")
        self.assertEqual(state.mission_tab, 1)
        events._missions(Ev(events.tcod.event.KeySym.LEFT), "")
        events._missions(Ev(events.tcod.event.KeySym.LEFT), "")
        self.assertEqual(state.mission_tab, 3)

    def test_job_rows_are_display_only(self):
        self.open_board(tab=3)
        self.assertFalse(any(m.mission_type == "hackjob" for m in state.missions))
        m = state.visible_missions[0]
        self.assertEqual((m.status, m.reward_credits), ("available", m.job.reward))

    def test_enter_starts_the_hack(self):
        from core import computer_input, events
        self.open_board(tab=3)
        events._missions(type("E", (), {"sym": events.tcod.event.KeySym.RETURN, "mod": 0})(), "")
        self.assertEqual(state.game_state, "COMPUTER")
        self.assertTrue(procedural.is_job(computer_input.computer.mission_id))
        state.game_state = "LOCATION"

    def test_done_failed_and_locked_rows_do_not_start(self):
        from core import events
        Enter = type("E", (), {"sym": events.tcod.event.KeySym.RETURN, "mod": 0})()
        self.open_board(tab=3)
        jobs = hackjobs.jobs(self.node)
        state.hack_done[jobs[0].key] = "done"
        state.hack_done[jobs[1].key] = "failed"
        events._open_missions(tab=3)
        self.assertEqual([m.status for m in state.visible_missions[:3]],
                         ["completed", "failed", "available"])
        events._missions(Enter, "")
        self.assertEqual(state.game_state, "MISSIONS")
        state.hack_lock[self.node.name] = state.day
        events._open_missions(tab=3)
        self.assertTrue(all(m.status in ("locked", "completed", "failed")
                            for m in state.visible_missions))
        events._missions(Enter, "")
        self.assertEqual(state.game_state, "MISSIONS")

    def test_no_terminal_means_an_empty_hacking_tab(self):
        from core import events
        self.dock(self.plain, self.plain.system.stations[0])
        events._open_missions(tab=3)
        self.assertEqual(state.visible_missions, [])


class SaveRoundTrip(World):
    def test_jobs_lock_and_heat_survive_a_save(self):
        from core import save as savegame
        old = savegame.SAVE_PATH
        savegame.SAVE_PATH = Path(tempfile.mkdtemp()) / "save.json"
        try:
            self.dock(self.node, self.station)
            state.hack_done = {"a|10|0": "done"}
            state.hack_lock = {self.node.name: 10}
            state.heat, state.heat_day = 21, 10
            newgame.begin_run()
            savegame.save_progress()
            newgame.build_galaxy(1, persist=False)
            newgame.reset_run()
            self.assertTrue(newgame.continue_run())
            self.assertEqual(state.hack_done, {"a|10|0": "done"})
            self.assertEqual(state.hack_lock, {self.node.name: 10})
            self.assertEqual((state.heat, state.heat_day), (21, 10))
        finally:
            savegame.SAVE_PATH = old
            state.run_active = False


if __name__ == "__main__":
    unittest.main()
