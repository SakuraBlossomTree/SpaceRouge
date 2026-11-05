"""Movement-time tests: the 50-step day clock and jump resets."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import tcod

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core import events, state, travel
from core.entities import JumpPoint, Star


class MovementTimeTests(unittest.TestCase):
    def setUp(self):
        self.origin = Star(0, 0, "A", "Red Dwarf")
        self.target = Star(10, 0, "B", "Red Dwarf")
        self.gate = JumpPoint(0, 0, "A -> B", "A", "B", 0)
        self.origin.system.jump_points.append(self.gate)
        self.target.system.jump_points.append(
            JumpPoint(0, 0, "B -> A", "B", "A", 0))

        state.stars = [self.origin, self.target]
        state.current_star = self.origin
        state.current_system = self.origin.system
        state.current_object = self.gate
        state.current_location = None
        state.fuel = 100
        state.move_counter = 37
        state.day = 10
        state.game_state = "JUMPPOINT"
        state.pending_destination = None
        state.pending_origin = None
        state.hyperspace_stage = 0
        state.hyperspace_complete = False

    def tearDown(self):
        state.current_object = None
        state.current_system = None
        state.current_star = None
        state.move_counter = 0

    def test_fifty_steps_advance_one_day_and_reset_counter(self):
        state.move_counter = 49
        state.system_player_x = 20
        state.system_player_y = 20

        with mock.patch("core.debt.advance_day") as advance, \
                mock.patch("core.debt.check_deadline"):
            travel.step(1, 0)

        advance.assert_called_once_with()
        self.assertEqual(state.move_counter, 0)
        self.assertEqual((state.system_player_x, state.system_player_y), (21, 20))

    def test_jump_advances_a_day_and_resets_move_counter(self):
        def fake_advance():
            state.day += 1

        with mock.patch.object(events, "advance_day",
                               side_effect=fake_advance) as advance, \
                mock.patch.object(events.audio, "play_sfx"):
            events._jumppoint(
                SimpleNamespace(sym=tcod.event.KeySym.RETURN), "")

        advance.assert_called_once_with()
        self.assertEqual(state.day, 11)
        self.assertEqual(state.move_counter, 0)
        self.assertEqual(state.pending_destination, "B")
        self.assertEqual(state.game_state, "HYPERSPACE")


if __name__ == "__main__":
    unittest.main()
