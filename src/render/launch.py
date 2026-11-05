"""Render the LAUNCH screen: the startup sequence that plays after the story.

You walk onto the ship and the pre-flight sequence runs on its own:

    0.0s  boot log          ship systems check in one by one
    1.9s  ship schematic    the hull lights up bottom-to-top, reactor spools
    4.0s  countdown         3 .. 2 .. 1
    5.2s  ignition          flames, steam, screen shake, music starts
    5.2s  liftoff           the pad drops away, stars stream past
    7.2s  white-out         into the Sol system

ENTER / SPACE / ESC skips it. Everything is drawn from the clock, so it needs
no state beyond when it started, and it works on any console size (the classic
80x60 UI uses it too).
"""

import math
import random
import time

from core import state, audio
from effects import transitions
from render import ui

# --- timeline (seconds) ------------------------------------------------------
SCAN_START = 1.9       # ship starts to light up
SCAN_TIME = 1.5
REACTOR_START = 2.4
COUNT_START = 4.0
COUNT_STEP = 0.4
IGNITE = 5.2           # == COUNT_START + 3 * COUNT_STEP
LIFT_TIME = 2.0
FLASH_AT = 7.2
DURATION = 8.0
MUSIC_AT = IGNITE

BOOM = "sfx/NenadSimic - Muffled Distant Explosion.ogg"
WHOOSH = "sfx/Reverse-Time-Loop-isaiah658.ogg"

SPACE_BG = (2, 3, 10)
SKY = (30, 52, 96)

SHIP = [
    r"       /\       ",
    r"      /  \      ",
    r"     / ## \     ",
    r"    /  ##  \    ",
    r"   |  ####  |   ",
    r"   | ###### |   ",
    r"  /|########|\  ",
    r" / |########| \ ",
    "/__|###  ###|__\\",
    r"   |__|  |__|   ",
]
SHIP_W = max(len(r) for r in SHIP)
ENGINE_COLS = (4, 5, 10, 11)       # flame columns, relative to the hull

FLAME = [((255, 255, 230), "█"), ((255, 220, 120), "▓"), ((255, 150, 50), "▒"),
         ((220, 80, 30), "░"), ((120, 40, 20), "·")]

DIGITS = {
    "3": ["███", "  █", " ██", "  █", "███"],
    "2": ["███", "  █", "███", "█  ", "███"],
    "1": [" █ ", "██ ", " █ ", " █ ", "███"],
}

_stars = None
_stars_size = None
_cues = set()


# ---------------------------------------------------------------------------
# Clock & flow
# ---------------------------------------------------------------------------

def start():
    state.launch_start = time.time()
    _cues.clear()


def elapsed():
    return time.time() - state.launch_start if state.launch_start else 0.0


def update():
    """Once per frame: fire sound cues and end the sequence on time."""
    if state.game_state != "LAUNCH":
        return
    t = elapsed()
    if t >= IGNITE and "boom" not in _cues:
        _cues.add("boom")
        audio.play_sfx(BOOM, volume=0.9, tag="launch")
    if t >= FLASH_AT - 0.5 and "whoosh" not in _cues:
        _cues.add("whoosh")
        audio.play_sfx(WHOOSH, volume=0.6, tag="launch")
    if t >= DURATION:
        finish()


def finish(skipped=False):
    """Hand the player the controls in the Sol system."""
    if skipped:
        audio.stop_sfx("launch")
    state.launch_start = 0.0
    state.game_state = "SYSTEM"
    state.add_message("Welcome aboard, Captain. All systems nominal.")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _put(console, x, y, ch, fg, bg=None):
    if 0 <= x < console.width and 0 <= y < console.height:
        console.print(x, y, ch, fg=fg, bg=bg)


def _init_stars(w, h):
    rng = random.Random(5)
    tints = [(255, 255, 255), (170, 200, 255), (255, 230, 180)]
    return [(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.35, 1.0),
             rng.choice(tints), rng.uniform(0, 6.28)) for _ in range(max(60, w * h // 50))]


# ---------------------------------------------------------------------------
# Layers
# ---------------------------------------------------------------------------

def _sky(console, w, h, tt, alt):
    """Space-black background; a dawn-blue glow rises from the ground at
    ignition and fades as the ship climbs out of the atmosphere."""
    k = _clamp(tt / 0.4) * (1.0 - alt) if tt > 0 else 0.0
    for y in range(h):
        bg = ui.lerp_color(SPACE_BG, SKY, k * (y / h) ** 1.4)
        console.draw_rect(0, y, w, 1, ord(" "), bg=bg)


def _starfield(console, w, h, t, tt, alt):
    global _stars, _stars_size
    if _stars is None or _stars_size != (w, h):
        _stars, _stars_size = _init_stars(w, h), (w, h)
    scroll = 0.0 if tt < 0 else 3 * tt + 16 * tt ** 3
    speed = 0.0 if tt < 0 else 3 + 48 * tt ** 2
    trail = min(int(speed / 18), 12)
    for x, y0, spd, col, ph in _stars:
        if tt < 0:
            bright = 0.3 * (0.6 + 0.4 * math.sin(t * 2 + ph))
            _put(console, int(x), int(y0), "·", ui.scale_color(col, bright))
            continue
        y = (y0 + scroll * spd) % h
        bright = 0.25 + 0.75 * alt
        _put(console, int(x), int(y), "│" if trail >= 2 else "·",
             ui.scale_color(col, bright))
        for k in range(1, trail + 1):
            _put(console, int(x), int(y) - k, "│",
                 ui.scale_color(col, bright * (1 - k / (trail + 1))))


def _ground(console, w, h, t, tt, ground_y, cx):
    fade = _clamp((t - 1.6) / 0.8)
    if fade <= 0 or ground_y >= h:
        return
    for y in range(max(0, ground_y), h):
        depth = (y - ground_y) / max(1, h - ground_y)
        c = ui.scale_color(ui.lerp_color((70, 82, 110), (18, 22, 36), depth), fade)
        console.draw_rect(0, y, w, 1, ord("░" if y > ground_y else "▀"), fg=c)
    # landing pad with blinking beacons
    half = 14
    for dx in range(-half, half + 1):
        _put(console, cx + dx, ground_y, "▀", ui.scale_color((130, 150, 190), fade))
    on = int(t * 3) % 2
    for side, colr in ((-half, (255, 80, 80)), (half, (90, 230, 120))):
        lit = on if side < 0 else 1 - on
        _put(console, cx + side, ground_y - 1, "●",
             ui.scale_color(colr, (1.0 if lit else 0.3) * fade))


def _ship(console, w, h, t, tt, sx, sy):
    scan = _clamp((t - SCAN_START) / SCAN_TIME)
    if scan <= 0:
        return
    n = len(SHIP)
    reactor = _clamp((t - REACTOR_START) / (COUNT_START + 0.8 - REACTOR_START))
    pulse = 0.85 + 0.15 * math.sin(t * 6)
    first_row = n - int(math.ceil(n * scan))
    for r, line in enumerate(SHIP):
        if r < first_row:
            continue
        front = (r == first_row and scan < 1.0)
        for c, ch in enumerate(line):
            if ch == " ":
                continue
            if ch == "#":
                glow = ui.lerp_color((40, 60, 100), (90, 175, 255), reactor * pulse)
                if r in (2, 3):                      # cockpit window
                    glow = ui.lerp_color((60, 120, 160), (150, 245, 255), reactor * pulse)
                fg, glyph = glow, "█"
            else:
                fg, glyph = (120, 150, 195), ch
            if front:
                fg = (255, 255, 255)
            _put(console, sx + c, sy + r, glyph, fg)


def _flames(console, sx, sy, tt):
    if tt < 0:
        return
    n = len(SHIP)
    grow = _clamp(tt / 0.6)
    for col in ENGINE_COLS:
        length = 1 + int(5 * grow) + random.randint(0, 2)
        for k in range(length):
            colr, glyph = FLAME[min(len(FLAME) - 1, k * len(FLAME) // max(1, length))]
            _put(console, sx + col, sy + n + k, glyph, colr)


def _steam(console, w, tt, ground_y, cx):
    if not 0 <= tt < 1.4:
        return
    span = int(2 + tt * 26)
    chance = 0.55 * (1 - tt / 1.4)
    for dx in range(-span, span + 1):
        if random.random() < chance:
            lift = random.randint(0, 2 + int(tt * 2))
            _put(console, cx + dx, ground_y - 1 - lift, random.choice("░▒"),
                 ui.scale_color((150, 155, 170), 0.5 + 0.5 * random.random()))


def _boot_log(console, w, h, t):
    alpha = 1.0 - _clamp((t - 3.3) / 0.6)
    if alpha <= 0:
        return
    pw = 52
    x0, y0 = (w - pw) // 2, 4
    name = getattr(state.player_ship, "name", "Rogue").upper()
    ui.text(console, x0, y0, f"{name}  //  SHIP SYSTEMS",
            fg=ui.scale_color(ui.TITLE, alpha))
    ui.text(console, x0, y0 + 1, "═" * pw, fg=ui.scale_color(ui.BORDER, alpha))
    checks = [
        ("COCKPIT BIOMETRIC LOCK", "OK", ui.GOOD),
        ("AUXILIARY POWER", "OK", ui.GOOD),
        ("REACTOR COLD START", "OK", ui.GOOD),
        ("FUEL CELLS", f"{int(state.fuel)}/{int(state.max_fuel)}", ui.GOOD),
        ("LIFE SUPPORT", "OK", ui.GOOD),
        ("NAV COMPUTER", "OK", ui.GOOD),
        ("LONG-RANGE SCANNER", "OK", ui.GOOD),
        ("LOAN TRANSPONDER", "LOCKED", ui.BAD),
        ("HYPERDRIVE", "STANDBY", ui.WARN),
    ]
    spin = "|/-\\"
    for i, (label, status, colr) in enumerate(checks):
        ti = 0.35 + i * 0.26
        if t < ti:
            break
        y = y0 + 2 + i
        dots = "." * max(1, pw - (2 + len(label) + 1) - 10 - 1)
        ui.text(console, x0, y, f"> {label} ", fg=ui.scale_color(ui.TEXT, alpha))
        ui.text(console, x0 + 3 + len(label), y, dots, fg=ui.scale_color(ui.FAINT, alpha))
        if t < ti + 0.22:
            ui.text(console, x0 + pw - 10, y, f"[{spin[int(t * 20) % 4]:^8}]",
                    fg=ui.scale_color(ui.DIM, alpha))
        else:
            ui.text(console, x0 + pw - 10, y, f"[{status:^8}]", fg=ui.scale_color(colr, alpha))


def _reactor_bar(console, w, t, y, cx):
    if not SCAN_START <= t < IGNITE:
        return
    bw = 36
    x = cx - bw // 2
    level = _clamp((t - REACTOR_START) / (COUNT_START + 0.8 - REACTOR_START))
    console.draw_rect(x - 2, y - 1, bw + 4, 4, ord(" "), bg=(8, 12, 22))
    ui.text(console, x, y, "REACTOR OUTPUT", fg=ui.DIM, bg=(8, 12, 22))
    pct = f"{int(level * 100):3d}%"
    ui.text(console, x + bw - len(pct), y, pct, fg=ui.ACCENT, bg=(8, 12, 22))
    ui.bar(console, x, y + 1, bw, level * 100, 100, ui.ACCENT, bg=(8, 12, 22))


def _countdown(console, h, t, cx):
    if not COUNT_START <= t < IGNITE:
        return
    idx = min(2, int((t - COUNT_START) / COUNT_STEP))
    digit = "321"[idx]
    local = (t - COUNT_START) - idx * COUNT_STEP
    k = 1.0 - 0.45 * _clamp(local / COUNT_STEP)          # flashes bright, settles
    colr = ui.lerp_color(ui.KEY, (255, 255, 255), k - 0.55)
    y = 14
    for r, row in enumerate(DIGITS[digit]):
        line = "".join(c * 2 for c in row)
        ui.center(console, cx, y + r, line, fg=colr)


def _caption(console, h, t, tt, cx):
    y = 12
    if REACTOR_START + 0.2 <= t < COUNT_START:
        # just above the ship, clear of the boot log
        ui.center(console, cx, h // 2 - 10, "REACTOR SPOOLING", fg=ui.ACCENT)
    elif COUNT_START <= t < IGNITE:
        if int(t * 6) % 2 == 0:
            ui.center(console, cx, y, "IGNITION SEQUENCE", fg=ui.WARN)
    elif 0 <= tt < 1.1:
        if int(t * 10) % 2 == 0:
            ui.center(console, cx, h - 6, "◄  IGNITION  ►", fg=ui.KEY)
    elif 1.1 <= tt < FLASH_AT - IGNITE:
        ui.center(console, cx, h - 6, "CLEARING THE ATMOSPHERE", fg=ui.TEXT)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def draw(console, w, h):
    t = elapsed()
    cx = w // 2
    tt = t - IGNITE

    lift = _clamp(tt / LIFT_TIME) ** 2.2 if tt > 0 else 0.0
    rise = lift * h * 0.75
    alt = _clamp(rise / (h * 0.5))

    base_y = h // 2 - 7
    ground_y = base_y + len(SHIP) + 2 + int(rise)

    _sky(console, w, h, tt, alt)
    _starfield(console, w, h, t, tt, alt)
    _ground(console, w, h, t, tt, ground_y, cx)
    _steam(console, w, tt, ground_y, cx)

    shake = 0
    if 0 <= tt < 1.0:
        shake = random.choice((-1, 0, 1)) if random.random() < (1 - tt) else 0
    sx = cx - SHIP_W // 2 + shake
    sy = base_y - int(rise)
    _flames(console, sx, sy, tt)
    _ship(console, w, h, t, tt, sx, sy)

    _boot_log(console, w, h, t)
    _reactor_bar(console, w, t, ground_y + 4, cx)
    _countdown(console, h, t, cx)
    _caption(console, h, t, tt, cx)

    # --- frame furniture -----------------------------------------------------
    ui.text(console, 3, 1, "LAUNCH SEQUENCE", fg=ui.DIM)
    clock = f"T{'+' if tt >= 0 else '-'}{abs(tt):04.1f}s"
    ui.right(console, w - 4, 1, clock, fg=ui.KEY if tt >= 0 else ui.DIM)
    ui.key_hint(console, cx - 6, h - 2, "SPACE", "Skip", label_fg=ui.FAINT)

    # --- flashes: ignition bloom, then the white-out into the system ------------
    if 0 <= tt < 0.25:
        transitions.whiten(console, 0.35 * (1 - tt / 0.25))
    if t >= FLASH_AT:
        transitions.whiten(console, _clamp((t - FLASH_AT) / 0.5))
