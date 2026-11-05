"""Focused tests for the Long-Range System Scanner and Exchange intelligence.

Run from the repository root:
    python -m unittest discover -s tests -v
"""

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

from core import economy, fonts, market_intel, newgame, save, scanner, shipyard, state
from core.entities import JumpPoint, Planet, Star
from core.world import BASE_PRICES, COMMODITIES


def _market(offset=0):
    return {good: BASE_PRICES[good] + offset for good in COMMODITIES}


def _star(name, x, y):
    star = Star(x, y, name, "Red Dwarf")
    star.system.archetype = "Trade Hub"
    star.system.planets.append(
        Planet(10, 10, f"{name} Prime", "United Nations", 1,
               (0, 0, 255), _market(len(name) % 3))
    )
    return star


def _connect(a, b):
    a.system.jump_points.append(
        JumpPoint(0, 0, f"{a.name} -> {b.name}", a.name, b.name, 0))
    b.system.jump_points.append(
        JumpPoint(0, 0, f"{b.name} -> {a.name}", b.name, a.name, 0))


def _chain():
    """A-B-C-D-E are connected by gates; Z is physically close but isolated."""
    names = ["A", "B", "C", "D", "E"]
    stars = [_star(name, 10 + i * 10, 10) for i, name in enumerate(names)]
    for a, b in zip(stars, stars[1:]):
        _connect(a, b)
    stars.append(_star("Z", 11, 11))       # deliberately near A, no gate
    return stars


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.stars = _chain()
        state.stars = self.stars
        state.economy = economy.Economy(self.stars, seed=11)
        state.current_star = self.stars[0]
        state.current_system = self.stars[0].system
        state.current_location = None
        state.day = 10
        state.credits = 100000
        state.upgrades = {}
        state.market_intel = {}
        state.galaxy_scanned_systems = set()
        state.market_scanner = True

    def tearDown(self):
        state.upgrades = {}
        state.market_intel = {}
        state.galaxy_scanned_systems = set()

    def test_default_radius_uses_gate_network(self):
        self.assertEqual(scanner.radius(), 1)
        self.assertEqual(set(market_intel.coverage()), {"A", "B"})
        self.assertNotIn("C", market_intel.coverage())
        # Z is within a few galaxy units of A but has no jump-gate connection.
        self.assertNotIn("Z", market_intel.coverage())

    def test_scanner_levels_expand_coverage(self):
        scanner.restore_level(1)
        self.assertEqual(scanner.radius(), 2)
        self.assertEqual(set(market_intel.coverage()), {"A", "B", "C"})
        scanner.restore_level(2)
        self.assertEqual(scanner.radius(), 3)
        self.assertIn("D", market_intel.coverage())
        scanner.restore_level(3)
        self.assertEqual(scanner.radius(), 4)
        self.assertIn("E", market_intel.coverage())
        self.assertNotIn("Z", market_intel.coverage())

    def test_shipyard_purchase_extends_scanner(self):
        state.credits = 2000
        ok, message = shipyard.buy("scanrange")
        self.assertTrue(ok, message)
        self.assertEqual(state.upgrades["scanrange"], 1)
        self.assertEqual(scanner.radius(), 2)
        self.assertEqual(state.credits, 200)
        self.assertIn("2 jumps", shipyard.current_text("scanrange"))
        self.assertEqual(state.market_intel, {})  # purchase itself records no data

    def test_preview_range_follows_scanner_not_distance(self):
        from render.galaxy import _preview_tier
        by_name = {star.name: star for star in self.stars}
        self.assertEqual(_preview_tier(by_name["A"], self.stars), "full")
        self.assertEqual(_preview_tier(by_name["B"], self.stars), "full")
        self.assertEqual(_preview_tier(by_name["C"], self.stars), "observed")
        self.assertEqual(_preview_tier(by_name["D"], self.stars), "none")
        self.assertEqual(_preview_tier(by_name["Z"], self.stars), "none")

        scanner.restore_level(1)
        self.assertEqual(_preview_tier(by_name["C"], self.stars), "full")
        self.assertEqual(_preview_tier(by_name["D"], self.stars), "observed")
        self.assertEqual(_preview_tier(by_name["E"], self.stars), "none")

    def test_observed_radius_is_one_jump_beyond_scanner(self):
        self.assertEqual(scanner.observed_radius(), scanner.radius() + 1)
        scanner.restore_level(3)
        self.assertEqual(scanner.observed_radius(), 5)

    def test_observed_map_draws_shapes_without_labels(self):
        import tcod
        from render import galaxy as galaxy_render

        by_name = {star.name: star for star in self.stars}
        for name, tier in (("B", "full"), ("C", "observed"), ("D", "none")):
            console = tcod.console.Console(90, 36)
            galaxy_render.draw_preview(console, 90, 36, by_name[name], self.stars)
            screen = "\n".join(
                "".join(chr(int(console.rgb["ch"][y, x])) for x in range(90))
                for y in range(36)
            )
            self.assertEqual(galaxy_render._preview_tier(by_name[name], self.stars),
                             tier)
            self.assertEqual(f"{name} Prime" in screen, tier == "full")
            self.assertEqual("NO DATA AVAILABLE" in screen, tier == "none")
            if tier == "observed":
                self.assertIn("DISTANT OBSERVATION", screen)


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.stars = _chain()
        state.stars = self.stars
        state.economy = economy.Economy(self.stars, seed=11)
        state.current_star = self.stars[0]
        state.current_system = self.stars[0].system
        state.current_location = None
        state.day = 10
        state.upgrades = {}
        state.market_intel = {}
        state.galaxy_scanned_systems = set()
        state.market_scanner = True

    def tearDown(self):
        state.upgrades = {}
        state.market_intel = {}
        state.galaxy_scanned_systems = set()

    def _select(self, name):
        star = next(s for s in self.stars if s.name == name)
        state.current_star = star
        state.current_system = star.system

    def test_unknown_then_live_then_stale_then_live(self):
        self.assertEqual(market_intel.status("A"), market_intel.UNKNOWN)
        self.assertEqual(market_intel.system_markets("A"), [])

        market_intel.refresh()
        self.assertEqual(market_intel.status("A"), market_intel.LIVE)
        self.assertEqual(market_intel.status("B"), market_intel.LIVE)
        self.assertEqual(market_intel.status("C"), market_intel.UNKNOWN)
        self.assertIn("A", state.market_intel)
        self.assertNotIn("C", state.market_intel)

        self._select("D")
        self.assertEqual(market_intel.status("A"), market_intel.STALE)
        self.assertEqual(market_intel.system_markets("C"), [])

        self._select("A")
        market_intel.refresh()
        self.assertEqual(market_intel.status("A"), market_intel.LIVE)

    def test_stale_prices_never_become_actual_prices(self):
        market_intel.refresh()
        ms = state.economy.markets_in["A"][0]
        recorded_before = state.market_intel["A"]["markets"][ms.id]["buy"]["Food"]

        # The underlying market keeps moving even though the player leaves.
        ms.trade("Food", 100)
        actual_after = ms.market["Food"]
        self.assertNotEqual(recorded_before, actual_after)

        self._select("D")
        self.assertEqual(market_intel.status("A"), market_intel.STALE)
        shown = market_intel.system_markets("A")[0]["buy"]["Food"]
        self.assertEqual(shown, recorded_before)
        self.assertNotEqual(shown, actual_after)
        self.assertEqual(state.market_intel["A"]["markets"][ms.id]["buy"]["Food"],
                         recorded_before)

        # Returning refreshes the record from the actual market.
        self._select("A")
        market_intel.refresh()
        self.assertEqual(market_intel.status("A"), market_intel.LIVE)
        shown = market_intel.system_markets("A")[0]["buy"]["Food"]
        self.assertEqual(shown, actual_after)
        self.assertEqual(state.market_intel["A"]["markets"][ms.id]["buy"]["Food"],
                         actual_after)

    def test_live_system_is_remote_not_only_docked(self):
        state.current_location = None       # flying, not docked
        market_intel.refresh()
        self.assertEqual(market_intel.status("B"), market_intel.LIVE)
        self.assertTrue(market_intel.system_markets("B"))

    def test_economy_updates_away_from_player(self):
        ms = state.economy.markets_in["E"][0]
        ms.supply["Food"] = 30
        before = ms.market["Food"]
        self._select("A")                   # player is four jumps away
        economy.tick(5)
        self.assertNotEqual(before, ms.market["Food"])

    def test_commodity_comparison_and_opportunities(self):
        market_intel.refresh()
        # Make A the obvious cheap Food market and B the dear one.
        ms_a = state.economy.markets_in["A"][0]
        ms_b = state.economy.markets_in["B"][0]
        ms_a.market["Food"] = 4
        ms_b.market["Food"] = 40
        market_intel.refresh()

        quotes = market_intel.commodity_quotes("Food")
        self.assertGreaterEqual(len(quotes), 2)
        self.assertEqual(quotes[0]["buy"], 4)
        cheapest, dearest, best_sell = market_intel.best_quotes("Food")
        self.assertEqual(cheapest["system"], "A")
        self.assertEqual(dearest["system"], "B")
        self.assertEqual(best_sell["sell"], 36)
        self.assertAlmostEqual(market_intel.known_average("Food"), 22.0)

        rows = market_intel.opportunities()
        food = next(row for row in rows if row["good"] == "Food")
        self.assertEqual(food["buy"]["system"], "A")
        self.assertEqual(food["sell"]["system"], "B")
        self.assertGreater(food["spread"], 0)
        self.assertEqual(food["status"], market_intel.LIVE)

    def test_directory_includes_unknown_systems(self):
        market_intel.refresh()
        rows = {row["system"]: row for row in market_intel.directory()}
        self.assertEqual(rows["A"]["status"], market_intel.LIVE)
        self.assertEqual(rows["C"]["status"], market_intel.UNKNOWN)
        self.assertEqual(rows["C"]["market_count"], 0)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = save.SAVE_PATH
        save.SAVE_PATH = Path(self.tmp.name) / "save.json"
        self.addCleanup(self._cleanup)

        self.stars = _chain()
        state.stars = self.stars
        state.economy = economy.Economy(self.stars, seed=11)
        state.current_star = self.stars[0]
        state.current_system = self.stars[0].system
        state.current_location = None
        state.day = 10
        state.credits = 100000
        state.upgrades = {}
        state.market_intel = {}
        state.galaxy_scanned_systems = set()
        state.galaxy_seed = 777

    def _cleanup(self):
        save.SAVE_PATH = self.old_path
        state.upgrades = {}
        state.market_intel = {}
        state.galaxy_scanned_systems = set()
        self.tmp.cleanup()

    def test_old_seed_only_save_still_loads(self):
        save.SAVE_PATH.write_text(json.dumps({"seed": 42}), encoding="utf-8")
        self.assertEqual(save.load(), 42)
        progress = save.load_progress(42)
        self.assertEqual(progress["scanner_level"], 0)
        self.assertEqual(progress["market_intel"], {})
        self.assertEqual(save.load_progress(99), {})

    def test_scanner_and_intel_survive_save_load_as_stale(self):
        market_intel.refresh()              # record A, B
        ms = state.economy.markets_in["A"][0]
        recorded = state.market_intel["A"]["markets"][ms.id]["buy"]["Food"]
        scanner.restore_level(1)
        state.upgrades["scanrange"] = 1

        # Leave A before saving so its saved record is historical.
        star_d = next(s for s in self.stars if s.name == "D")
        state.current_star = star_d
        state.current_system = star_d.system
        save.save_progress()

        raw = json.loads(save.SAVE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(raw["seed"], 777)
        self.assertEqual(raw["scanner_level"], 1)
        self.assertIn("systems", raw["market_intel"])

        # Simulate loading into a fresh process, still away from A.  The
        # economy is rebuilt from the seed, so the saved market id must
        # still identify the same market.
        state.upgrades = {}
        state.market_intel = {}
        state.economy = economy.Economy(self.stars, seed=11)
        progress = save.load_progress(777)
        scanner.restore_level(progress["scanner_level"])
        state.market_intel = market_intel.from_dict(progress["market_intel"])

        rebuilt_ids = [m.id for m in state.economy.markets_in["A"]]
        self.assertIn(ms.id, rebuilt_ids)
        self.assertEqual(scanner.radius(), 2)
        self.assertEqual(market_intel.status("A"), market_intel.STALE)
        shown = market_intel.system_markets("A")[0]["buy"]["Food"]
        self.assertEqual(shown, recorded)
        self.assertNotIn("status",
                         state.market_intel["A"])

    def test_title_return_persists_galaxy_progress(self):
        from types import SimpleNamespace
        import tcod
        from core import events

        state.galaxy_seed = 777
        state.upgrades["scanrange"] = 1
        # with the tutorial ON, ENTER loads the practice galaxy instead
        # (see test_tutorial_flow.py); this test is the normal start
        with mock.patch.object(fonts, "settings", return_value={"tutorial": False}):
            events._title(SimpleNamespace(sym=tcod.event.KeySym.RETURN), "")

        raw = json.loads(save.SAVE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(raw["seed"], 777)
        self.assertEqual(raw["scanner_level"], 1)
        self.assertEqual(state.game_state, "STORY")

    def test_newgame_restore_applies_saved_scanner_and_intel(self):
        state.upgrades["scanrange"] = 2
        state.market_intel = {
            "Sol": {
                "system_id": "Sol",
                "name": "Sol",
                "discovered": True,
                "updated_day": 12,
                "markets": {},
            }
        }
        save.save_progress(12345)

        newgame.build_galaxy(12345, restore=True, persist=False)

        self.assertEqual(state.upgrades.get("scanrange"), 2)
        self.assertEqual(scanner.radius(), 3)
        self.assertIn("Sol", state.market_intel)
        self.assertEqual(state.market_intel["Sol"]["updated_day"], 12)


if __name__ == "__main__":
    unittest.main()
