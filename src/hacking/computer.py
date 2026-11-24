"""The computer interface: desktop launcher + apps, as plain state.

This class holds what is on screen and reacts to abstract input
(`on_text(str)`, `on_key("ENTER")`). It never draws and never imports tcod;
render/computer.py draws it and core/computer_input.py feeds it keys, so
it can be unit-tested and reused for any device.
"""

import time

from hacking import missions
from hacking.filesystem import FSError
from hacking.terminal import Terminal

# id, label, hotkey. Apps a device does not list in device.apps show as
# "not installed": room for the full OS later (mail, browser, archives...).
APPS = [
    ("terminal", "Terminal", "T"),
    ("files", "Files", "F"),
    ("mission", "Mission", "M"),
    ("mail", "Mail", ""),
    ("browser", "Net Browser", ""),
    ("crypto", "Cipher Tools", ""),
]
GRID_COLS = 3

# Boot sequence. Lines appear at BOOT_FIRST + i * BOOT_STEP; "[ OK ]" lands
# BOOT_OK later. A later visit only plays the short "resume" version.
BOOT_LINES = [
    ("SR-BIOS 0.1  ·  cold start", None),
    ("Initialising lattice core", "OK"),
    ("Checking memory banks", "OK"),
    ("Mounting /home/{user}", "OK"),
    ("Loading security sandbox", "OK"),
    ("Bringing up network stack", "OK"),
    ("Starting {os}", "OK"),
]
BOOT_FIRST, BOOT_STEP, BOOT_OK = 0.2, 0.36, 0.22
BOOT_FULL, BOOT_QUICK = 3.4, 0.9
FLASH_SECONDS = 0.5
MAX_INPUT = 160


class Computer:
    def __init__(self, mission_id=missions.DEFAULT, realtime=True):
        self.mission_id = mission_id
        self.realtime = realtime
        self.on_realtime_change = None      # e.g. save the option to settings
        self.screen = "desktop"
        self.desktop_index = 0
        self.notice = ""
        self.start()

    def start(self):
        """(Re)build the session for the mission: a fresh run."""
        self.session = missions.build(self.mission_id)
        self.session.realtime = self.realtime
        self.session.on_realtime_change = self._realtime_changed
        self.boot_t, self.boot_full = 0.0, True
        self.flash_until, self._seen_trace = 0.0, 0
        self.terminal = Terminal(self.session)
        self.device = self.session.device
        self.input = ""
        self.history_pos = None
        self.scroll = 0                 # wrapped lines scrolled up from the bottom
        self.files_index = 0
        self.files_path = self.device.download_dir.rsplit("/", 1)[0]
        self.set_screen("desktop")

    def _realtime_changed(self, value):
        self.realtime = value
        if self.on_realtime_change:
            self.on_realtime_change(value)

    def begin_boot(self, full=True):
        """Play the startup animation (full), or a short resume (not full)."""
        self.boot_t, self.boot_full = 0.0, full
        self.set_screen("boot")

    @property
    def boot_duration(self):
        return BOOT_FULL if self.boot_full else BOOT_QUICK

    def boot_script(self):
        """[(appear time, text, status or None)] with this device's names filled in."""
        return [(BOOT_FIRST + i * BOOT_STEP,
                 text.format(user=self.device.username, os=self.device.os_name), status)
                for i, (text, status) in enumerate(BOOT_LINES)]

    def trace_flashing(self):
        return time.monotonic() < self.flash_until

    def _note_trace(self):
        """Flash the trace readout whenever the peak trace has gone up."""
        peak = self.session.peak_trace()
        if peak > self._seen_trace:
            self.flash_until = time.monotonic() + FLASH_SECONDS
        self._seen_trace = peak

    def update(self, dt):
        """Advance real time by dt seconds (called every frame by the game)."""
        if self.screen == "boot":
            self.boot_t += dt
            if self.boot_t >= self.boot_duration:
                self.set_screen("desktop")
        lines = self.session.tick(dt)
        if lines:
            self.terminal.print(*lines)
        self._note_trace()
        if self.mission and self.mission.finished and self.screen != "result" \
                and self.session.lockdown:
            self.set_screen("result")

    def set_screen(self, screen):
        self.screen = screen
        self.changed_at = time.monotonic()      # lets the renderer fade the switch in

    @property
    def mission(self):
        return self.session.mission

    @property
    def can_retry(self):
        """Contract jobs are one attempt: no restart from the result screen."""
        return not missions.procedural.is_job(self.mission_id)

    def installed(self, app_id):
        return app_id in self.device.apps

    # ------------------------------------------------------------- input
    def on_text(self, text):
        if self.screen == "boot":
            self.set_screen("desktop")              # any key skips the boot
        elif self.screen == "terminal":
            self.input = (self.input + "".join(c for c in text if c.isprintable()))[:MAX_INPUT]
            self.history_pos = None
            self.scroll = 0
        elif self.screen == "desktop":
            if text.lower() == "r":
                self.session.set_realtime("off" if self.realtime else "on")
                self.notice = f"Real-time trace {'ON' if self.realtime else 'OFF'}."
            for app_id, _, hot in APPS:
                if hot and text.lower() == hot.lower():
                    self.open_app(app_id)
        elif self.screen == "result" and text.lower() == "r" and self.can_retry:
            self.start()
            self.open_app("terminal")

    def on_key(self, key):
        """Returns "exit" when the player leaves the computer entirely."""
        self.notice = ""
        return getattr(self, "_key_" + self.screen)(key)

    def open_app(self, app_id):
        if not self.installed(app_id):
            label = next(l for a, l, _ in APPS if a == app_id)
            self.notice = f"{label} is not installed on this device."
            return
        self.notice = ""
        self.set_screen(app_id)

    def _key_boot(self, key):
        self.set_screen("desktop")
        return None

    def _key_desktop(self, key):
        i, n = self.desktop_index, len(APPS)
        if key == "ESC":
            return "exit"
        if key == "LEFT":
            i -= 1
        elif key == "RIGHT":
            i += 1
        elif key == "UP":
            i -= GRID_COLS
        elif key == "DOWN":
            i += GRID_COLS
        elif key == "ENTER":
            self.open_app(APPS[i][0])
            return None
        self.desktop_index = max(0, min(n - 1, i))
        return None

    def _key_terminal(self, key):
        t = self.terminal
        if key == "ESC":
            self.set_screen("desktop")
        elif key == "ENTER":
            line, self.input, self.history_pos, self.scroll = self.input, "", None, 0
            t.execute(line)
            self._note_trace()
            if t.exit_requested:
                t.exit_requested = False
                self.set_screen("desktop")
            elif self.mission and self.mission.finished:
                self.set_screen("result")
        elif key == "BACKSPACE":
            self.input = self.input[:-1]
        elif key in ("UP", "DOWN") and t.history:
            h = t.history
            if self.history_pos is None:
                self.history_pos = len(h)
            self.history_pos += -1 if key == "UP" else 1
            if self.history_pos >= len(h):
                self.history_pos, self.input = None, ""
            else:
                self.history_pos = max(0, self.history_pos)
                self.input = h[self.history_pos]
        elif key == "TAB":
            self.input = t.complete(self.input)
        elif key == "PAGEUP":
            self.scroll += 10
        elif key == "PAGEDOWN":
            self.scroll = max(0, self.scroll - 10)
        return None

    def files_listing(self):
        """(path, [nodes]) of the device's own files for the Files app."""
        fs = self.device.filesystem
        try:
            return fs.listdir(self.files_path)
        except FSError:
            self.files_path = "/"
            return fs.listdir("/")

    def _key_files(self, key):
        path, nodes = self.files_listing()
        if key == "ESC":
            self.set_screen("desktop")
        elif key == "UP":
            self.files_index = max(0, self.files_index - 1)
        elif key == "DOWN":
            self.files_index = min(max(0, len(nodes) - 1), self.files_index + 1)
        elif key == "BACKSPACE" and path != "/":
            self.files_path = path.rsplit("/", 1)[0] or "/"
            self.files_index = 0
        elif key == "ENTER" and nodes and nodes[min(self.files_index, len(nodes) - 1)].is_dir:
            self.files_path = path.rstrip("/") + "/" + nodes[min(self.files_index, len(nodes) - 1)].name
            self.files_index = 0
        return None

    def _key_mission(self, key):
        if key in ("ESC", "ENTER"):
            self.set_screen("desktop")
        return None

    def _key_result(self, key):
        if key in ("ESC", "ENTER"):
            self.set_screen("desktop")
        return None
