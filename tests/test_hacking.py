"""Computer / hacking subsystem: engine, mission and UI-controller tests.

    python -m unittest tests.test_hacking -v
    python -m unittest discover -s tests -v

The engine is tcod-free, so these run without a window. Drawing is checked
with a recording fake console; the tcod key adapter test is skipped when
tcod is not installed.
"""

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hacking import missions
from hacking.computer import Computer
from hacking.filesystem import (ADMIN, GUEST, USER, AccessDenied, Directory,
                                File, FileSystem, FSError)
from hacking.puzzles import caesar, find_shift
from hacking.security import Trace
from hacking.terminal import Terminal

TOKEN = "HX-7F3A-92C1"

FULL_RUN = [
    "connect helix.net", "scan", "open gateway", "cd /public", "cat staff_directory.txt",
    "cat it_notice.txt", "close", "login mail r.vance orbit2291", "open mail",
    "cat /spool/r.vance/archive_sync.log", "close", "probe archive-07",
    f"breach archive-07 token-replay {TOKEN}", "open archive-07", "cd /vault", "ls",
    "cat README.txt", "decrypt lantern_dossier.sealed 11",
    "download lantern_dossier.sealed", "close", "disconnect",
]


def make():
    s = missions.build()
    return s, Terminal(s)


def texts(lines):
    return "\n".join(t for _, t in lines)


def run(term, *cmds):
    out = []
    for c in cmds:
        out += term.execute(c)
    return out


def to_vault(term):
    run(term, "connect helix.net", "scan", f"breach archive-07 ftp-overflow")  # not probed: refused
    run(term, "probe archive-07", f"breach archive-07 token-replay {TOKEN}", "open archive-07")


class FileSystemTests(unittest.TestCase):
    def setUp(self):
        self.fs = FileSystem(Directory("", [
            Directory("a", [File("x.txt", "hi"), Directory("deep", [File("y", "")])]),
            Directory("secret", [File("z", "")], min_access=ADMIN),
            File("top.txt", "t", min_access=USER),
        ]))

    def test_navigation(self):
        self.fs.cd("/a/deep")
        self.assertEqual(self.fs.cwd, "/a/deep")
        self.fs.cd("..")
        self.assertEqual(self.fs.cwd, "/a")
        self.fs.cd("/")
        self.assertEqual(self.fs.cwd, "/")

    def test_missing_and_not_a_directory(self):
        with self.assertRaises(FSError):
            self.fs.resolve("/nope")
        with self.assertRaises(FSError):
            self.fs.cd("/a/x.txt")

    def test_access_levels(self):
        with self.assertRaises(AccessDenied):
            self.fs.resolve("/secret/z", USER)
        with self.assertRaises(AccessDenied):
            self.fs.resolve("/top.txt", GUEST)
        self.assertEqual(self.fs.resolve("/top.txt", USER)[1], "/top.txt")

    def test_listing_orders_dirs_first(self):
        _, nodes = self.fs.listdir("/")
        self.assertEqual([n.name for n in nodes], ["a", "secret", "top.txt"])


class PuzzleTests(unittest.TestCase):
    def test_caesar_roundtrip_and_crib(self):
        self.assertEqual(caesar(caesar("Hello, World!", 11), -11), "Hello, World!")
        self.assertEqual(find_shift("NWLDDTQTPO", "CLASSIFIED"), 11)

    def test_sealed_file(self):
        f = File("f", "CLASSIFIED text", cipher_shift=3)
        self.assertTrue(f.sealed)
        self.assertNotEqual(f.text(), "CLASSIFIED text")
        self.assertFalse(f.unseal(4))
        self.assertTrue(f.unseal(3))
        self.assertEqual(f.text(), "CLASSIFIED text")


class TraceTests(unittest.TestCase):
    def test_progression_and_warnings(self):
        t = Trace()
        self.assertEqual(t.level, "CLEAR")
        self.assertIn("NOTICED", texts(t.add(25, "x")) + t.level)
        lines = t.add(30, "y")                       # 55: crosses the 50 warning
        self.assertEqual(t.level, "ALERT")
        self.assertIn("heuristics", texts(lines))
        lines = t.add(20, "z")                       # 75
        self.assertIn("ACTIVE TRACE", texts(lines))
        t.add(500, "boom")
        self.assertEqual((t.value, t.locked), (100, True))

    def test_each_threshold_warns_once(self):
        t = Trace()
        t.add(30, "a")
        self.assertNotIn("anomalous", texts(t.add(1, "b")))


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.s, self.t = make()

    def test_unknown_command_suggests(self):
        out = texts(self.t.execute("scna"))
        self.assertIn("Unknown command 'scna'", out)
        self.assertIn("Did you mean 'scan'", out)

    def test_unknown_command_without_suggestion(self):
        self.assertIn("Type 'help'", texts(self.t.execute("zzzzzz")))

    def test_usage_errors(self):
        for cmd, usage in [("inspect", "inspect <host>"), ("login a b", "login <host>"),
                           ("cat", "cat <file>"), ("breach", "breach <host>"),
                           ("scan extra", "Too many arguments")]:
            self.assertIn(usage, texts(self.t.execute(cmd)), cmd)

    def test_quotes_and_aliases(self):
        self.assertIn("unbalanced", texts(self.t.execute('cat "oops')))
        self.assertIn("Commands", texts(self.t.execute("?")))
        self.assertIn("briefing.txt", texts(self.t.execute("dir")))

    def test_blank_line_does_nothing(self):
        n = self.s.commands_run
        self.t.execute("   ")
        self.assertEqual(self.s.commands_run, n)

    def test_history_and_clear(self):
        run(self.t, "status", "status", "pwd")
        self.assertEqual(self.t.history, ["status", "pwd"])        # no consecutive dupes
        self.t.execute("clear")
        self.assertEqual(self.t.log, [])

    def test_log_is_capped(self):
        for _ in range(1100):
            self.t.print(*[("out", "x")])
        self.assertLessEqual(len(self.t.log), 1000)

    def test_help_marks_commands_by_state(self):
        offline = {l.text: l.kind for l in self.t.execute("help") if l.text.startswith("  scan")}
        self.assertEqual(list(offline.values()), ["dim"])
        self.t.execute("connect helix.net")
        online = {l.text: l.kind for l in self.t.execute("help") if l.text.startswith("  scan")}
        self.assertEqual(list(online.values()), ["out"])
        self.assertIn("Needs", texts(self.t.execute("help download")))

    def test_completion(self):
        self.assertEqual(self.t.complete("sca"), "scan")
        self.assertEqual(self.t.complete("connect he"), "connect helix.net")
        self.assertEqual(self.t.complete("cat bri"), "cat briefing.txt")
        run(self.t, "connect helix.net", "scan")
        self.assertEqual(self.t.complete("inspect arch"), "inspect archive-07")

    def test_exit_leaves_terminal_when_not_in_host(self):
        self.t.execute("exit")
        self.assertTrue(self.t.exit_requested)

    def test_no_real_commands_are_run(self):
        out = texts(run(self.t, "rm -rf /", "ping 8.8.8.8", "python -c 1"))
        self.assertEqual(out.count("Unknown command"), 3)

    def test_prompt_tracks_location(self):
        self.assertEqual(self.t.prompt(), "pilot@local:~$")
        run(self.t, "connect helix.net", "scan", "open gateway")
        self.assertEqual(self.t.prompt(), "guest@gateway:/$")


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.s, self.t = make()

    def test_network_commands_need_connection(self):
        for cmd in ("scan", "inspect gateway", "probe mail", "open mail",
                    "login mail a b", "breach mail x", "disconnect"):
            self.assertIn("Not connected", texts(self.t.execute(cmd)) if cmd != "disconnect"
                          else "Not connected" + texts(self.t.execute(cmd)), cmd)

    def test_connect_unknown_and_known(self):
        self.assertIn("no route", texts(self.t.execute("connect evil.net")))
        self.assertIn("helix.net", texts(self.t.execute("connect")))
        self.assertIn("Connected to HelixCorp", texts(self.t.execute("connect HELIX.NET")))
        self.assertIn("Already connected", texts(self.t.execute("connect helix.net")))

    def test_disconnect(self):
        run(self.t, "connect helix.net")
        self.assertIn("Disconnected", texts(self.t.execute("disconnect")))
        self.assertIsNone(self.s.connection)
        self.assertIn("Not connected", texts(self.t.execute("scan")))

    def test_reconnect_keeps_trace(self):
        run(self.t, "connect helix.net", "scan", "disconnect")
        self.assertIn("trace 3%", texts(self.t.execute("connect helix.net")))


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.s, self.t = make()
        run(self.t, "connect helix.net")

    def test_hosts_unknown_until_scanned(self):
        self.assertIn("Unknown host", texts(self.t.execute("inspect archive-07")))
        self.assertIn("Unknown host", texts(self.t.execute("open gateway")))
        out = texts(self.t.execute("scan"))
        for name in ("gateway", "mail", "hr-db", "archive-07"):
            self.assertIn(name, out)

    def test_scan_is_noisy_once_and_repeatable(self):
        first = texts(self.t.execute("scan"))
        second = texts(self.t.execute("scan"))
        self.assertIn("[TRACE +3]", first)
        self.assertNotIn("[TRACE", second)
        self.assertEqual(self.s.trace.value, 3)
        strip = lambda s: "\n".join(l for l in s.splitlines() if "TRACE" not in l and "cached" not in l and "Scanning" not in l and "OBJECTIVE" not in l)
        self.assertEqual(strip(first), strip(second))

    def test_inspect_and_probe(self):
        self.t.execute("scan")
        ins = texts(self.t.execute("inspect archive-07"))
        self.assertIn("not probed yet", ins)
        self.assertIn("auth-daemon", ins)
        probe = texts(self.t.execute("probe archive-07"))
        self.assertIn("token-replay", probe)
        self.assertIn("2 known", texts(self.t.execute("inspect archive-07")))
        self.assertEqual(self.s.trace.value, 3 + 4)
        again = texts(self.t.execute("probe archive-07"))
        self.assertIn("token-replay", again)
        self.assertEqual(self.s.trace.value, 7)              # repeated probe is free

    def test_probe_hardened_host_finds_nothing(self):
        self.t.execute("scan")
        self.assertIn("no exploitable", texts(self.t.execute("probe hr-db")))


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.s, self.t = make()
        run(self.t, "connect helix.net", "scan")

    def test_open_without_access_is_denied_and_traced(self):
        out = texts(self.t.execute("open mail"))
        self.assertIn("ACCESS DENIED", out)
        self.assertEqual(self.s.trace.value, 3 + 10)
        self.t.execute("open mail")
        self.assertEqual(self.s.trace.value, 3 + 20)         # same result, same cost

    def test_public_gateway_is_open_to_guests(self):
        self.assertIn("as guest", texts(self.t.execute("open gateway")))

    def test_guest_cannot_read_staff_files(self):
        run(self.t, "open gateway")
        out = texts(self.t.execute("cat /staff/payroll.dat"))
        self.assertIn("ACCESS DENIED", out)
        self.assertIn("user", out)
        self.assertEqual(self.s.trace.value, 3 + 5)
        self.assertIn("ACCESS DENIED", texts(self.t.execute("cd /staff")))

    def test_restricted_entries_are_marked(self):
        run(self.t, "open gateway")
        rows = {l.text for l in self.t.execute("ls /") if l.kind == "warn"}
        self.assertTrue(any("staff" in r and "[user]" in r for r in rows))

    def test_login_success_and_wrong_password(self):
        bad = texts(self.t.execute("login mail r.vance wrong"))
        self.assertIn("Authentication failed", bad)
        self.assertEqual(self.s.trace.value, 3 + 12)
        bad2 = texts(self.t.execute("login mail nobody x"))
        self.assertIn("Authentication failed", bad2)          # no user enumeration
        good = texts(self.t.execute("login mail r.vance orbit2291"))
        self.assertIn("Authenticated: r.vance@mail", good)
        self.assertIn("already", texts(self.t.execute("login mail r.vance orbit2291")).lower())
        self.assertIn("as r.vance", texts(self.t.execute("open mail")))

    def test_login_on_host_without_service(self):
        self.assertIn("no login service", texts(self.t.execute("login gateway a b")))

    def test_user_cannot_read_admin_area(self):
        run(self.t, "login mail t.okafor biscuit2288", "open mail")
        self.assertIn("ACCESS DENIED", texts(self.t.execute("cat /admin/filters.cfg")))

    def test_must_close_host_before_network_commands(self):
        run(self.t, "open gateway")
        self.assertIn("Use 'close'", texts(self.t.execute("scan")))
        self.assertIn("Use 'close'", texts(self.t.execute("disconnect")) + "Use 'close'")


class BreachTests(unittest.TestCase):
    def setUp(self):
        self.s, self.t = make()
        run(self.t, "connect helix.net", "scan")

    def test_breach_requires_probe(self):
        self.assertIn("Run 'probe", texts(self.t.execute("breach archive-07 token-replay x")))

    def test_breach_argument_rules(self):
        self.t.execute("probe archive-07")
        v = self.s.trace.value
        self.assertIn("Usage: breach", texts(self.t.execute("breach archive-07")))
        self.assertIn("not a known vulnerability", texts(self.t.execute("breach archive-07 nope")))
        self.assertIn("needs an argument", texts(self.t.execute("breach archive-07 token-replay")))
        self.assertEqual(self.s.trace.value, v)               # mistakes in syntax are free

    def test_wrong_token_costs_trace(self):
        self.t.execute("probe archive-07")
        v = self.s.trace.value
        out = texts(self.t.execute("breach archive-07 token-replay HX-0000"))
        self.assertIn("rejected", out)
        self.assertEqual(self.s.trace.value, v + 15)
        self.assertIn("ACCESS DENIED", texts(self.t.execute("open archive-07")))

    def test_token_replay_grants_access(self):
        self.t.execute("probe archive-07")
        out = texts(self.t.execute(f"breach archive-07 token-replay {TOKEN.lower()}"))
        self.assertIn("Access granted: svc-archiver", out)
        self.assertIn("[TRACE +10]", out)
        self.assertIn("already hold", texts(self.t.execute(f"breach archive-07 token-replay {TOKEN}")))

    def test_loud_shortcut_costs_more(self):
        self.t.execute("probe archive-07")
        out = texts(self.t.execute("breach archive-07 ftp-overflow"))
        self.assertIn("[TRACE +40]", out)
        self.assertEqual(self.s.trace.value, 3 + 4 + 40)
        self.assertIn("as ftp-shell", texts(self.t.execute("open archive-07")))


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.s, self.t = make()
        to_vault(self.t)
        self.t.execute("cd /vault")

    def test_navigation_and_listing(self):
        self.assertEqual(self.t.prompt(), "svc-archiver@archive-07:/vault$")
        out = texts(self.t.execute("ls"))
        self.assertIn("lantern_dossier.sealed", out)
        self.assertIn("SEALED", out)
        self.assertIn("ACCESS DENIED", texts(self.t.execute("cd /admin")))
        self.assertIn("no such file", texts(self.t.execute("cat ghost.txt")))
        self.assertIn("is a directory", texts(self.t.execute("cat /vault")))

    def test_cat_sealed_shows_ciphertext(self):
        out = texts(self.t.execute("cat lantern_dossier.sealed"))
        self.assertIn("[SEALED]", out)
        self.assertIn("NWLDDTQTPO", out)
        self.assertNotIn("PROJECT LANTERN - DOSSIER 7", out)

    def test_decrypt_info_wrong_key_right_key(self):
        info = texts(self.t.execute("decrypt lantern_dossier.sealed"))
        self.assertIn("NWLDDTQTPO", info)
        v = self.s.trace.value
        for bad in ("abc", "0", "26"):
            self.assertIn("whole number", texts(self.t.execute(f"decrypt lantern_dossier.sealed {bad}")))
        self.assertEqual(self.s.trace.value, v)               # invalid syntax is free
        wrong = texts(self.t.execute("decrypt lantern_dossier.sealed 3"))
        self.assertIn("Checksum mismatch", wrong)
        self.assertEqual(self.s.trace.value, v + 8)
        right = texts(self.t.execute("decrypt lantern_dossier.sealed 11"))
        self.assertIn("unsealed", right)
        self.assertIn("PROJECT LANTERN", texts(self.t.execute("cat lantern_dossier.sealed")))
        self.assertIn("not encrypted", texts(self.t.execute("decrypt lantern_dossier.sealed 11")))

    def test_cannot_download_sealed(self):
        out = texts(self.t.execute("download lantern_dossier.sealed"))
        self.assertIn("sealed", out)
        self.assertEqual(self.s.downloads, [])

    def test_download_extracts_to_device_once(self):
        run(self.t, "decrypt lantern_dossier.sealed 11")
        v = self.s.trace.value
        out = texts(self.t.execute("download lantern_dossier.sealed"))
        self.assertIn("Extracted", out)
        self.assertEqual(self.s.trace.value, v + 10)
        self.assertEqual(self.s.downloads, [("archive-07", "/vault/lantern_dossier.sealed")])
        self.assertIn("already", texts(self.t.execute("download lantern_dossier.sealed")))
        self.assertEqual(self.s.trace.value, v + 10)
        run(self.t, "close")
        self.assertIn("lantern_dossier.sealed", texts(self.t.execute("ls ~/downloads")))
        self.assertIn("PROJECT LANTERN", texts(self.t.execute("cat ~/downloads/lantern_dossier.sealed")))

    def test_download_needs_host_session_and_file(self):
        run(self.t, "close")
        self.assertIn("Open a host session", texts(self.t.execute("download x")))


class MissionTests(unittest.TestCase):
    def test_full_mission_success(self):
        s, t = make()
        for cmd in FULL_RUN:
            t.execute(cmd)
            self.assertEqual(s.mission.status == "success", cmd == "disconnect", cmd)
        self.assertEqual(s.mission.progress(), (8, 8))
        self.assertEqual(s.mission.result["trace"], 27)
        self.assertIn("S", s.mission.result["rating"])
        self.assertTrue(s.mission.result["won"])

    def test_objectives_complete_in_order_of_play(self):
        s, t = make()
        run(t, "connect helix.net")
        self.assertEqual(s.mission.progress()[0], 1)
        run(t, "scan", "probe archive-07")
        self.assertEqual([o.done for o in s.mission.objectives[:3]], [True] * 3)

    def test_disconnect_early_is_not_a_win(self):
        s, t = make()
        run(t, "connect helix.net", "scan", "disconnect")
        self.assertEqual(s.mission.status, "active")

    def test_loud_route_still_wins_with_lower_rating(self):
        s, t = make()
        run(t, "connect helix.net", "scan", "probe archive-07", "breach archive-07 ftp-overflow",
            "open archive-07", "decrypt /vault/lantern_dossier.sealed 11",
            "download /vault/lantern_dossier.sealed", "close", "disconnect")
        self.assertEqual(s.mission.status, "success")
        self.assertEqual(s.mission.result["trace"], 3 + 4 + 40 + 10)
        self.assertIn("A", s.mission.result["rating"])

    def test_failure_by_failed_logins(self):
        s, t = make()
        run(t, "connect helix.net", "scan")
        for _ in range(7):
            t.execute("login mail r.vance nope")
        self.assertEqual(s.trace.value, 3 + 84)
        self.assertEqual(s.mission.status, "active")
        out = texts(t.execute("login mail r.vance nope"))          # 99
        self.assertEqual(s.mission.status, "active")
        out = texts(t.execute("login mail r.vance nope"))          # lockdown
        self.assertIn("CONNECTION SEVERED", out)
        self.assertIn("MISSION FAILED", out)
        self.assertEqual(s.mission.status, "failed")
        self.assertFalse(s.mission.result["won"])
        self.assertIn("F", s.mission.result["rating"])
        self.assertIsNone(s.connection)
        self.assertIn("No connection", texts(t.execute("scan")))
        self.assertIn("blacklisted", texts(t.execute("connect helix.net")))
        self.assertIn("briefing.txt", texts(t.execute("ls")))       # device still usable

    def test_trace_warnings_appear_in_order(self):
        s, t = make()
        run(t, "connect helix.net", "scan")
        seen = []
        for _ in range(9):
            out = texts(t.execute("login mail r.vance nope"))
            seen += [w for w in ("anomalous", "heuristics", "ACTIVE TRACE", "SEVERED") if w in out]
        self.assertEqual(seen, ["anomalous", "heuristics", "ACTIVE TRACE", "SEVERED"])

    def test_brute_forcing_the_cipher_is_not_viable(self):
        s, t = make()
        to_vault(t)
        for shift in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
            t.execute(f"decrypt /vault/lantern_dossier.sealed {shift}")
        self.assertGreaterEqual(s.trace.value, 80)

    def test_mission_is_deterministic(self):
        a, ta = make()
        b, tb = make()
        outs = [[texts(x.execute(c)) for c in FULL_RUN] for x in (ta, tb)]
        self.assertEqual(outs[0], outs[1])

    def test_status_and_mission_commands(self):
        s, t = make()
        self.assertIn("OFFLINE", texts(t.execute("status")))
        run(t, "connect helix.net", "scan")
        out = texts(t.execute("status"))
        self.assertIn("CONNECTED to helix.net", out)
        self.assertIn("3% CLEAR", out)
        m = texts(t.execute("mission"))
        self.assertIn("CORPORATE ARCHIVE BREACH (2/8)", m)
        self.assertIn("[x] Scan the network", m)


class ComputerUITests(unittest.TestCase):
    def type(self, c, text):
        for ch in text:
            c.on_text(ch)

    def test_desktop_navigation_and_apps(self):
        c = Computer()
        self.assertEqual(c.screen, "desktop")
        c.on_key("RIGHT")
        c.on_key("ENTER")
        self.assertEqual(c.screen, "files")
        c.on_key("ESC")
        c.on_text("m")
        self.assertEqual(c.screen, "mission")
        c.on_key("ESC")
        c.on_key("DOWN")                                  # a not-installed app
        c.on_key("ENTER")
        self.assertEqual(c.screen, "desktop")
        self.assertIn("not installed", c.notice)
        self.assertEqual(c.on_key("ESC"), "exit")

    def test_terminal_typing_history_scroll(self):
        c = Computer()
        c.on_text("t")
        self.type(c, "status")
        c.on_key("BACKSPACE")
        self.assertEqual(c.input, "statu")
        c.on_key("TAB")
        self.assertEqual(c.input, "status")               # unique completion
        c.input = "zzq"
        c.on_key("TAB")
        self.assertEqual(c.input, "zzq")                  # no match: unchanged
        c.input = ""
        self.type(c, "pwd")
        c.on_key("ENTER")
        self.assertEqual(c.input, "")
        c.on_key("UP")
        self.assertEqual(c.input, "pwd")
        c.on_key("DOWN")
        self.assertEqual(c.input, "")
        c.on_key("PAGEUP")
        self.assertEqual(c.scroll, 10)
        self.type(c, "x")
        self.assertEqual(c.scroll, 0)                     # typing snaps back to the prompt

    def test_exit_command_returns_to_desktop(self):
        c = Computer()
        c.on_text("t")
        self.type(c, "exit")
        c.on_key("ENTER")
        self.assertEqual(c.screen, "desktop")

    def test_mission_end_shows_result_and_retry_resets(self):
        c = Computer()
        c.on_text("t")
        for cmd in FULL_RUN:
            self.type(c, cmd)
            c.on_key("ENTER")
        self.assertEqual(c.screen, "result")
        self.assertEqual(c.mission.status, "success")
        c.on_text("r")
        self.assertEqual((c.screen, c.mission.status), ("terminal", "active"))
        self.assertEqual(c.session.downloads, [])

    def test_failure_shows_result_screen(self):
        c = Computer()
        c.on_text("t")
        for cmd in ["connect helix.net", "scan"] + ["login mail a b"] * 9:
            self.type(c, cmd)
            c.on_key("ENTER")
        self.assertEqual((c.screen, c.mission.status), ("result", "failed"))

    def test_files_app_shows_downloads_folder(self):
        c = Computer()
        c.on_text("f")
        path, nodes = c.files_listing()
        self.assertEqual(path, "/home/pilot")
        c.on_key("ENTER")                                 # first entry: downloads/
        self.assertEqual(c.files_path, "/home/pilot/downloads")
        c.on_key("BACKSPACE")
        self.assertEqual(c.files_path, "/home/pilot")


class RealtimeTests(unittest.TestCase):
    def setUp(self):
        self.s, self.t = make()
        run(self.t, "connect helix.net")

    def test_trace_creeps_at_a_fixed_rate(self):
        self.s.tick(9.9)
        self.assertEqual(self.s.trace.value, 0)
        self.s.tick(0.1)
        self.assertEqual(self.s.trace.value, 1)
        self.s.tick(25)                                   # 2 more, 5s carried over
        self.assertEqual(self.s.trace.value, 3)
        self.assertAlmostEqual(self.s.next_tick_in(), 5.0)

    def test_only_while_connected_and_enabled(self):
        self.s.set_realtime("off")
        self.s.tick(100)
        self.assertEqual(self.s.trace.value, 0)
        self.assertIsNone(self.s.next_tick_in())
        self.s.set_realtime("on")
        run(self.t, "disconnect")
        self.assertEqual(self.s.tick(100), [])

    def test_clock_shows_in_toggle_command(self):
        self.assertIn("ON", texts(self.t.execute("realtime")))
        self.assertIn("OFF", texts(self.t.execute("realtime off")))
        self.assertIn("Usage", texts(self.t.execute("realtime maybe")))
        self.assertIn("off", texts(self.t.execute("status")))

    def test_warnings_and_lockdown_in_real_time(self):
        self.s.connection.trace_interval = 1
        seen = []
        for _ in range(100):
            lines = self.s.tick(1)
            seen += [l.text for l in lines]
        self.assertTrue(any("anomalous" in x for x in seen))
        self.assertTrue(any("SEVERED" in x for x in seen))
        self.assertEqual(self.s.mission.status, "failed")
        self.assertEqual(self.s.tick(50), [])             # nothing after lockdown

    def test_computer_update_prints_and_shows_result(self):
        c = Computer()
        c.on_text("t")
        for cmd in ("connect helix.net",):
            for ch in cmd:
                c.on_text(ch)
            c.on_key("ENTER")
        c.session.connection.trace_interval = 1
        n = len(c.terminal.log)
        for _ in range(100):
            c.update(1)
        self.assertGreater(len(c.terminal.log), n)
        self.assertEqual(c.screen, "result")

    def test_option_toggle_from_desktop_persists_through_retry(self):
        saved = []
        c = Computer()
        c.on_realtime_change = saved.append
        c.on_text("r")
        self.assertEqual((c.realtime, saved, c.session.realtime), (False, [False], False))
        c.start()
        self.assertFalse(c.session.realtime)
        self.assertEqual(Computer(realtime=False).session.realtime, False)


class BootAnimationTests(unittest.TestCase):
    def test_full_boot_then_desktop(self):
        c = Computer()
        c.begin_boot(full=True)
        self.assertEqual(c.screen, "boot")
        c.update(1.0)
        self.assertEqual(c.screen, "boot")
        c.update(10)
        self.assertEqual(c.screen, "desktop")

    def test_resume_is_shorter_and_any_key_skips(self):
        c = Computer()
        c.begin_boot(full=False)
        self.assertLess(c.boot_duration, 1.5)
        c.update(0.95)
        self.assertEqual(c.screen, "desktop")
        c.begin_boot()
        c.on_text("x")
        self.assertEqual(c.screen, "desktop")
        c.begin_boot()
        c.on_key("ENTER")
        self.assertEqual(c.screen, "desktop")

    def test_boot_script_uses_device_names(self):
        text = " ".join(t for _, t, _ in Computer().boot_script())
        self.assertIn("/home/pilot", text)
        self.assertIn("SR-OS 0.1", text)

    def test_trace_flash_on_increase_only(self):
        c = Computer()
        c.on_text("t")
        for cmd in ("connect helix.net", "scan"):
            for ch in cmd:
                c.on_text(ch)
            c.on_key("ENTER")
        self.assertTrue(c.trace_flashing())
        c.flash_until = 0
        c.update(0.1)
        self.assertFalse(c.trace_flashing())            # no new trace, no flash

    def test_boot_and_animated_screens_draw_at_all_times(self):
        from render import computer as r
        for size in ((120, 62), (80, 60)):
            con = FakeConsole(*size)
            for full in (True, False):
                c = Computer()
                c.begin_boot(full)
                for _ in range(40):
                    r.draw(con, c)
                    c.update(0.1)
            c.set_screen("desktop")
            for back in (0.0, 0.1, 0.3, 0.8, 3.0):       # icons fading in, then settled
                c.changed_at = time.monotonic() - back
                r.draw(con, c)
            self.assertIn("Terminal", con.text())
            c.set_screen("terminal")
            r.draw(con, c)                               # mid-transition frame


class FakeConsole:
    """Records print calls; just enough of tcod.console.Console for drawing."""

    def __init__(self, w, h):
        self.width, self.height = w, h
        self.prints = []

    def clear(self, **kw): self.prints = []
    def print(self, x, y, s, fg=None, bg=None, **kw): self.prints.append((x, y, s))
    def draw_rect(self, *a, **kw): pass
    def draw_frame(self, *a, **kw): pass

    def text(self):
        return "\n".join(s for _, _, s in self.prints)


class RenderSmokeTests(unittest.TestCase):
    def test_every_screen_draws_at_both_sizes(self):
        from render import computer as r
        for size in ((120, 62), (80, 60)):
            c = Computer()
            con = FakeConsole(*size)
            c.changed_at = time.monotonic() - 10          # animations finished
            r.draw(con, c)
            self.assertIn("Terminal", con.text())
            c.on_text("t")
            c.changed_at = time.monotonic() - 5
            for cmd in FULL_RUN[:12]:
                for ch in cmd:
                    c.on_text(ch)
                c.on_key("ENTER")
                r.draw(con, c)
            self.assertIn("TRACE", con.text().upper())
            for ch in "help":
                c.on_text(ch)
            c.on_key("ENTER")
            r.draw(con, c)
            for screen in ("files", "mission", "desktop"):
                c.set_screen(screen)
                r.draw(con, c)
            for cmd in FULL_RUN[12:]:
                c.set_screen("terminal")
                for ch in cmd:
                    c.on_text(ch)
                c.on_key("ENTER")
            self.assertEqual(c.screen, "result")
            c.changed_at = time.monotonic() - 10
            r.draw(con, c)
            self.assertIn("MISSION COMPLETE", con.text())

    def test_failed_result_and_scroll_clamp(self):
        from render import computer as r
        c = Computer()
        c.on_text("t")
        c.scroll = 9999
        con = FakeConsole(120, 62)
        r.draw(con, c)
        self.assertLess(c.scroll, 9999)
        for cmd in ["connect helix.net", "scan"] + ["login mail a b"] * 9:
            for ch in cmd:
                c.on_text(ch)
            c.on_key("ENTER")
        c.changed_at = time.monotonic() - 10
        r.draw(con, c)
        self.assertIn("MISSION FAILED", con.text())


class TcodAdapterTests(unittest.TestCase):
    def test_key_mapping_and_state_switch(self):
        try:
            import tcod
        except ImportError:
            self.skipTest("tcod not installed")
        from core import computer_input, state
        old = state.game_state
        try:
            state.game_state = "TITLE"
            computer_input.computer = None
            computer_input.open_computer(back_to="TITLE")
            self.assertEqual(state.game_state, "COMPUTER")
            computer_input.handle(tcod.event.TextInput(text="t"))
            self.assertEqual(computer_input.computer.screen, "terminal")
            computer_input.handle(tcod.event.KeyDown(scancode=tcod.event.Scancode.ESCAPE, sym=tcod.event.KeySym.ESCAPE, mod=tcod.event.Modifier.NONE))
            computer_input.handle(tcod.event.KeyDown(scancode=tcod.event.Scancode.ESCAPE, sym=tcod.event.KeySym.ESCAPE, mod=tcod.event.Modifier.NONE))
            self.assertEqual(state.game_state, "TITLE")
        finally:
            state.game_state = old
            computer_input.computer = None


if __name__ == "__main__":
    unittest.main()
