"""The Unsent Message: the hacking mission content and its game-side glue.

    python -m unittest tests.test_unsent_message -v

Needs no window and no tcod (the glue module only touches game state).
"""

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hacking import missions
from hacking.computer import Computer
from hacking.terminal import Terminal

ID = "unsent_message"

ROUTE = [
    "connect halcyon.relay", "scan", "open beacon", "cd /public", "cat status.txt",
    "cat maintenance.log", "close", "login nav-core tmarsh halcyon2091", "open nav-core",
    "cd /archive", "cat README.txt", "decrypt unsent_transmission.sealed 7",
    "cat unsent_transmission.sealed", "download unsent_transmission.sealed",
    "close", "disconnect",
]


def run(commands, session=None):
    s = session or missions.build(ID)
    s.realtime = False
    t = Terminal(s)
    for c in commands:
        t.execute(c)
    return s, t


class MissionContent(unittest.TestCase):
    def test_registered(self):
        self.assertIn(ID, missions.MISSIONS)

    def test_intended_route_wins_quietly(self):
        s, _ = run(ROUTE)
        self.assertEqual(s.mission.status, "success")
        self.assertEqual(s.mission.progress(), (7, 7))
        self.assertEqual(s.peak_trace(), 13)            # scan +3, download +10
        self.assertTrue(s.mission.result["rating"].startswith("S"))

    def test_transmission_is_sealed_until_decrypted(self):
        s, t = run(["connect halcyon.relay", "scan", "login nav-core tmarsh halcyon2091",
                    "open nav-core", "cat /archive/unsent_transmission.sealed"])
        text = "\n".join(l.text for l in t.log)
        self.assertIn("YLJSHZZPMPLK", text)             # RECLASSIFIED, shifted by 7
        self.assertNotIn("Marguerite", text)

    def test_core_needs_the_login(self):
        s, t = run(["connect halcyon.relay", "scan", "open nav-core"])
        self.assertIsNone(s.open_host)
        self.assertGreater(s.peak_trace(), 3)           # denied opens are traced

    def test_wrong_cipher_key_costs_trace(self):
        s, _ = run(["connect halcyon.relay", "scan", "login nav-core tmarsh halcyon2091",
                    "open nav-core", "decrypt /archive/unsent_transmission.sealed 3"])
        self.assertEqual(s.peak_trace(), 3 + 8)

    def test_must_disconnect_to_finish(self):
        s, _ = run(ROUTE[:-1])
        self.assertEqual(s.mission.status, "active")

    def test_lockdown_fails_the_mission(self):
        spam = ["connect halcyon.relay", "scan"] + ["login nav-core tmarsh wrong"] * 9
        s, _ = run(spam)
        self.assertTrue(s.lockdown)
        self.assertEqual(s.mission.status, "failed")

    def test_retry_after_failure_is_a_fresh_run(self):
        c = Computer(ID, realtime=False)
        run(["connect halcyon.relay", "scan"] + ["login nav-core tmarsh wrong"] * 9, c.session)
        self.assertEqual(c.mission.status, "failed")
        c.start()                                       # what R on the result screen does
        self.assertEqual(c.mission.status, "active")
        self.assertFalse(c.session.lockdown)
        run(ROUTE, c.session)
        self.assertEqual(c.mission.status, "success")


try:
    from core import state, story_relay
    from core.world import generate_stars
    from hacking import missions as _m  # noqa: F401
    GAME = True
except Exception:       # pragma: no cover - game modules unavailable
    GAME = False


@unittest.skipUnless(GAME, "game modules not importable")
class GameGlue(unittest.TestCase):
    def setUp(self):
        self.stars, _ = generate_stars(2468)
        state.galaxy_seed = 2468
        state.tutorial_run = False
        state.missions = []
        state.completed_mission_keys = set()
        state.messages = []
        state.day = 1
        state.credits = 0
        self.info = story_relay.install(self.stars)

    def _star(self, name):
        return next(s for s in self.stars if s.name == name)

    def test_relay_is_a_dead_station_near_sol(self):
        from core import travel
        self.assertIsNotNone(self.info)
        stations = self._star(self.info["system"]).system.stations
        relay = next(s for s in stations if s.name == self.info["station"])
        self.assertEqual(relay.market, {})
        self.assertIn(travel.route_estimate(self.stars, "Sol", self.info["system"])[0], (1, 2))
        self.assertTrue(story_relay.is_relay(relay))

    def test_install_is_deterministic_and_leaves_the_galaxy_alone(self):
        before = {s.name: [st.name for st in s.system.stations] for s in self.stars}
        again, _ = generate_stars(2468)
        state.galaxy_seed = 2468
        info2 = story_relay.install(again)
        self.assertEqual(info2, self.info)
        for s in again:
            names = [st.name for st in s.system.stations if st.name != story_relay.RELAY_NAME]
            self.assertEqual(names, [n for n in before[s.name] if n != story_relay.RELAY_NAME])

    def test_install_works_for_many_seeds(self):
        from core import travel
        for seed in range(1, 41):
            stars, _ = generate_stars(seed)
            state.galaxy_seed = seed
            state.tutorial_run = False
            info = story_relay.install(stars)
            self.assertIsNotNone(info, seed)
            star = next(s for s in stars if s.name == info["system"])
            self.assertEqual([s.name for s in star.system.stations].count(story_relay.RELAY_NAME), 1)
            self.assertIn(travel.route_estimate(stars, "Sol", info["system"])[0], (1, 2))
        state.galaxy_seed = 2468

    def test_no_relay_in_the_tutorial_galaxy(self):
        state.tutorial_run = True
        self.assertIsNone(story_relay.install(self.stars))
        self.assertIsNone(state.relay)
        state.tutorial_run = False

    def _earth(self):
        return next(p for p in self._star("Sol").system.planets if p.name == "Earth")

    def test_contract_posts_on_earth_only_once(self):
        mars = next(p for p in self._star("Sol").system.planets if p.name == "Mars")
        story_relay.post(mars)
        self.assertEqual(state.missions, [])
        story_relay.post(self._earth())
        story_relay.post(self._earth())
        self.assertEqual([m.key for m in state.missions], [story_relay.MISSION_KEY])
        m = state.missions[0]
        self.assertEqual((m.mission_type, m.status, m.destination), ("hack", "available", "Earth"))
        self.assertEqual(m.dest_system, self.info["system"])

    def test_completed_contract_is_not_reposted(self):
        state.completed_mission_keys.add(story_relay.MISSION_KEY)
        story_relay.post(self._earth())
        self.assertEqual(state.missions, [])

    def test_turn_in_needs_the_records_and_retry_works(self):
        story_relay.post(self._earth())
        mission = state.missions[0]
        self.assertFalse(story_relay.turn_in_ready(mission))

        c = Computer(ID, realtime=False)
        run(["connect halcyon.relay", "scan"] + ["login nav-core tmarsh wrong"] * 9, c.session)
        story_relay.on_computer_update(c)                # failed run
        self.assertFalse(story_relay.turn_in_ready(mission))
        self.assertTrue(any("cut your link" in m for m in state.messages))

        c.start()                                         # retry
        run(ROUTE, c.session)
        story_relay.on_computer_update(c)
        story_relay.on_computer_update(c)                 # applied only once
        self.assertTrue(story_relay.turn_in_ready(mission))
        self.assertEqual(sum("transmission recovered" in m for m in state.messages), 1)

    def test_other_computers_are_ignored(self):
        c = Computer(realtime=False)                      # the Corporate Archive demo
        c.session.mission.status = "success"
        story_relay.on_computer_update(c)
        self.assertFalse(state.relay_records)


if __name__ == "__main__":
    unittest.main()
