"""Render the LAUNCH screen: the startup sequence that plays after the story.

You are in the pilot's seat. The cockpit is the game's own interface - the same
framed panels you will use all game - and it powers up around you:

    0.1s  consoles power on   header, systems panel, forward view, power panel, log
    0.5s  systems check       each ship system reports in (left panel)
    1.8s  reactor spools      power gauges fill (right panel); view brightens
    4.0s  countdown           3 .. 2 .. 1 in the forward view
    5.2s  ignition            thrust, shake, steam; the music starts
    5.2s  liftoff             the pad drops away, stars stream past, altitude climbs
    7.2s  white-out           into the Sol system

ENTER / SPACE / ESC skips it. Everything is drawn from the clock, so it needs
no state beyond when it started, and it adapts to any console size (the classic
80x60 UI uses it too).
"""

import math
import random
import time

import tcod

from core import state
from effects import transitions
from render import ui

# --- timeline (seconds) ------------------------------------------------------
REACTOR_START = 1.8
REACTOR_FULL = 4.6
COUNT_START = 4.0
COUNT_STEP = 0.4
IGNITE = 5.2           # == COUNT_START + 3 * COUNT_STEP
LIFT_TIME = 2.0
FLASH_AT = 7.2
DURATION = 8.0
MUSIC_AT = IGNITE

SPACE_BG = (2, 3, 10)
SKY = (30, 52, 96)
GLOW = (120, 55, 15)           # engine light on the ground at ignition

# When each console powers on
ON_HEADER, ON_LEFT, ON_VIEW, ON_RIGHT, ON_LOG = 0.1, 0.2, 0.45, 0.75, 1.0

DIGITS = {
    "3": ["███", "  █", " ██", "  █", "███"],
    "2": ["███", "  █", "███", "█  ", "███"],
    "1": [" █ ", "██ ", " █ ", " █ ", "███"],
}

# (time, text) lines typed into the flight log
LOG = [
    (0.6, "Cockpit lock engaged. Welcome aboard, Captain."),
    (1.5, "Running pre-flight diagnostics..."),
    (2.9, "All systems nominal. Reactor spooling."),
    (3.9, "Launch window confirmed. Beginning countdown."),
    (5.2, "IGNITION. Main engines at full thrust."),
    (5.8, "Clamps released. We have liftoff."),
    (6.6, "Clearing the atmosphere. Hyperdrive on standby."),
]

_stars = None
_stars_size = None
_skyline = None
_view = None
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
    """Once per frame: end the sequence on time."""
    if state.game_state != "LAUNCH":
        return
    t = elapsed()
    # (sound effects: add them here later, e.g. at t >= IGNITE and near FLASH_AT)
    if t >= DURATION:
        finish()


def finish(skipped=False):
    """Hand the player the controls in the Sol system."""
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


def _online(t, t0):
    """0 before a console powers on, flickering for a moment, then 1."""
    if t < t0:
        return 0.0
    if t < t0 + 0.35:
        return 1.0 if int(t * 40) % 3 else 0.35
    return 1.0


def _layout(w, h):
    """Rectangles (x, y, w, h) of the consoles for any window size."""
    top = 3
    log_h = 9
    main_h = max(14, h - top - log_h - 2)
    log = (1, top + main_h, w - 2, log_h)
    if w >= 100:
        sw = 30
        left = (1, top, sw, main_h)
        right = (w - 1 - sw, top, sw, main_h)
        view = (sw + 2, top, w - 2 * (sw + 2), main_h)
    else:                               # narrow (classic 80x60): panels under the view
        vh = int(main_h * 0.55)
        half = (w - 2) // 2
        view = (1, top, w - 2, vh)
        left = (1, top + vh, half, main_h - vh)
        right = (1 + half, top + vh, w - 2 - half, main_h - vh)
    return {"left": left, "right": right, "view": view, "log": log}


def _panel(console, rect, title, level, right_title=""):
    x, y, pw, ph = rect
    colr = ui.scale_color(ui.BORDER_HI, level)
    ui.frame(console, x, y, pw, ph, title, fg=colr, title_fg=ui.scale_color(ui.TITLE, level),
             right_title=right_title)


# ---------------------------------------------------------------------------
# Forward view (what you see through the windscreen)
# ---------------------------------------------------------------------------

def _init_stars(w, h):
    rng = random.Random(5)
    tints = [(255, 255, 255), (170, 200, 255), (255, 230, 180)]
    return [(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.35, 1.0),
             rng.choice(tints), rng.uniform(0, 6.28)) for _ in range(max(40, w * h // 40))]


def _sky(view, w, h, t, tt, alt):
    """Space-black; dawn-blue glow near the ground, and the orange light of the
    engines at ignition. Both fade as the ship climbs."""
    k = _clamp(tt / 0.4) * (1.0 - alt) if tt > 0 else 0.0
    glow = _clamp(1.0 - tt / 1.6) if tt > 0 else 0.0
    for y in range(h):
        low = (y / h) ** 1.4
        bg = ui.lerp_color(SPACE_BG, SKY, k * low)
        if glow > 0:
            bg = ui.lerp_color(bg, GLOW, glow * (1 - alt) * (y / h) ** 2.2)
        view.draw_rect(0, y, w, 1, ord(" "), bg=bg)


def _starfield(view, w, h, t, tt, alt):
    global _stars, _stars_size
    if _stars is None or _stars_size != (w, h):
        _stars, _stars_size = _init_stars(w, h), (w, h)
    scroll = 0.0 if tt < 0 else 3 * tt + 16 * tt ** 3
    speed = 0.0 if tt < 0 else 3 + 48 * tt ** 2
    trail = min(int(speed / 18), 10)
    for x, y0, spd, col, ph in _stars:
        if tt < 0:
            _put(view, int(x), int(y0), "·", ui.scale_color(col, 0.3 * (0.6 + 0.4 * math.sin(t * 2 + ph))))
            continue
        y = (y0 + scroll * spd) % h
        bright = 0.25 + 0.75 * alt
        _put(view, int(x), int(y), "│" if trail >= 2 else "·", ui.scale_color(col, bright))
        for k in range(1, trail + 1):
            _put(view, int(x), int(y) - k, "│", ui.scale_color(col, bright * (1 - k / (trail + 1))))


def _init_skyline(w):
    rng = random.Random(9)
    out, x = [], 0
    while x < w:
        bw = 2 + int(rng.random() * 5)
        out.append((x, bw, 1 + int(rng.random() * 3)))
        x += bw + int(rng.random() * 3)
    return out


def _ground(view, w, h, t, tt, horizon):
    """The launch pad ahead: runway lights chasing toward a distant skyline.
    It drops out of the bottom of the view as you climb."""
    global _skyline
    fade = _clamp((t - ON_VIEW) / 1.2)
    if fade <= 0 or horizon >= h:
        return
    if _skyline is None or _skyline[0] != w:
        _skyline = (w, _init_skyline(w))
    for bx, bw, bh in _skyline[1]:                     # silhouettes on the horizon
        for dx in range(bw):
            for dy in range(1, bh + 1):
                _put(view, bx + dx, horizon - dy, "█", ui.scale_color((26, 34, 54), fade))
    for y in range(max(0, horizon), h):
        depth = (y - horizon) / max(1, h - horizon)
        c = ui.scale_color(ui.lerp_color((70, 82, 110), (16, 20, 34), depth), fade)
        view.draw_rect(0, y, w, 1, ord("▀" if y == horizon else "░"), fg=c)
    cx = w // 2
    chase = int(t * 6)
    k = 1
    while horizon + int(k ** 1.55) < h:
        y = horizon + int(k ** 1.55)
        spread = int(k * 2.4) + 1
        lit = (k + chase) % 4 == 0
        c = ui.scale_color((255, 210, 120) if lit else (90, 80, 60), fade)
        for side in (-1, 1):
            _put(view, cx + side * spread, y, "●" if lit else "·", c)
        if k % 2 == 0:
            _put(view, cx, y, "┆", ui.scale_color((120, 130, 150), fade))
        k += 1


def _steam(view, w, h, tt):
    """Exhaust steam billowing across the bottom of the view at ignition."""
    if not 0 <= tt < 1.6:
        return
    chance = 0.5 * (1 - tt / 1.6)
    height = 2 + int(tt * 5)
    for x in range(w):
        if random.random() < chance:
            lift = random.randint(0, height)
            _put(view, x, h - 1 - lift, random.choice("░▒"),
                 ui.scale_color((170, 160, 150), 0.4 + 0.6 * random.random()))


def _view_scene(view, w, h, t, tt):
    lift = _clamp(tt / LIFT_TIME) ** 2.2 if tt > 0 else 0.0
    rise = lift * h * 0.9
    alt = _clamp(rise / (h * 0.55))
    horizon = int(h * 0.66) + int(rise * 1.25)
    if 0 <= tt < 1.0 and random.random() < (1 - tt):
        horizon += random.choice((-1, 0, 1))          # the pad shudders
    _sky(view, w, h, t, tt, alt)
    _starfield(view, w, h, t, tt, alt)
    _ground(view, w, h, t, tt, horizon)
    _steam(view, w, h, tt)
    return alt


def _viewport(console, rect, t, tt):
    global _view
    x, y, vw, vh = rect
    iw, ih = vw - 2, vh - 2
    if _view is None or (_view.width, _view.height) != (iw, ih):
        _view = tcod.console.Console(iw, ih)
    _view_scene(_view, iw, ih, t, tt)

    # power-up: the camera feed brightens as the consoles come alive
    transitions.fade_in(_view, 0.2 + 0.8 * _clamp((t - ON_VIEW) / 1.2))
    if 0 <= tt < 1.0:                                  # engine shake
        shift = random.choice((-1, 0, 1)) if random.random() < (1 - tt) else 0
        if shift:
            import numpy as np
            _view.rgb[:] = np.roll(_view.rgb, shift, axis=1)
    _view.blit(console, x + 1, y + 1)

    cx = x + vw // 2
    # windscreen struts in the corners
    strut = ui.scale_color(ui.BORDER, 1.0)
    n = max(3, min(8, vh // 6))
    for i in range(n):
        _put(console, x + 1 + i, y + 1 + i, "╲", strut)
        _put(console, x + vw - 2 - i, y + 1 + i, "╱", strut)
        _put(console, x + 1 + i, y + vh - 2 - i, "╱", strut)
        _put(console, x + vw - 2 - i, y + vh - 2 - i, "╲", strut)

    # heading tape and reticle (HUD drawn on the glass)
    hud = ui.scale_color(ui.ACCENT, _clamp((t - 2.6) / 0.6))
    if hud != (0, 0, 0):
        heading = f"· · ·  HDG 270  · · ·"
        ui.center(console, cx, y + 2, heading, fg=hud)
        cy = y + int(vh * 0.45)
        ui.center(console, cx, cy, "─ ┼ ─", fg=hud)

    # banners and the big countdown
    if COUNT_START <= t < IGNITE:
        idx = min(2, int((t - COUNT_START) / COUNT_STEP))
        local = (t - COUNT_START) - idx * COUNT_STEP
        colr = ui.lerp_color(ui.KEY, (255, 255, 255), 0.45 * (1 - _clamp(local / COUNT_STEP)))
        ui.center(console, cx, y + 5, "T-MINUS", fg=ui.WARN)
        for r, row in enumerate(DIGITS["321"[idx]]):
            ui.center(console, cx, y + 7 + r, "".join(c * 2 for c in row), fg=colr)
    elif 0 <= tt < 1.1:
        if int(t * 10) % 2 == 0:
            ui.center(console, cx, y + 7, "◄  IGNITION  ►", fg=ui.KEY)
    elif 1.1 <= tt < FLASH_AT - IGNITE:
        ui.center(console, cx, y + 7, "CLEARING THE ATMOSPHERE", fg=ui.TEXT)


# ---------------------------------------------------------------------------
# Instrument panels
# ---------------------------------------------------------------------------

def _systems_panel(console, rect, t, tt):
    x, y, pw, ph = rect
    ix, iw = x + 2, pw - 4
    checks = [
        ("COCKPIT LOCK", "OK", ui.GOOD),
        ("AUX POWER", "OK", ui.GOOD),
        ("REACTOR", "OK", ui.GOOD),
        ("FUEL CELLS", f"{int(state.fuel)}/{int(state.max_fuel)}", ui.GOOD),
        ("LIFE SUPPORT", "OK", ui.GOOD),
        ("NAV COMPUTER", "OK", ui.GOOD),
        ("SCANNER", "OK", ui.GOOD),
        ("LOAN LINK", "LOCKED", ui.BAD),
        ("HYPERDRIVE", "STANDBY", ui.WARN),
    ]
    flight = [
        (IGNITE, "MAIN ENGINES", "BURN", ui.GOOD),
        (IGNITE + 0.9, "LANDING GEAR", "UP", ui.GOOD),
        (IGNITE + 1.6, "ATMOSPHERE", "CLEAR", ui.ACCENT),
    ]
    spin = "|/-\\"
    row = y + 2
    for i, (label, status, colr) in enumerate(checks):
        ti = 0.5 + i * 0.26
        if t < ti:
            break
        _status_row(console, ix, row, iw, label, status, colr, t, ti, spin)
        row += 1
    if row + 1 < y + ph - 1 and t >= IGNITE:
        row += 1
        ui.text(console, ix, row, "FLIGHT", fg=ui.KEY)
        row += 1
        for ti, label, status, colr in flight:
            if t < ti or row >= y + ph - 1:
                break
            _status_row(console, ix, row, iw, label, status, colr, t, ti, spin)
            row += 1


def _status_row(console, ix, row, iw, label, status, colr, t, ti, spin):
    width = 8
    ui.text(console, ix, row, ui.clip(label, iw - width - 3), fg=ui.TEXT)
    dots_from = ix + len(label) + 1
    dots = max(0, iw - width - 2 - len(label) - 1)
    ui.text(console, dots_from, row, "." * dots, fg=ui.FAINT)
    if t < ti + 0.22:
        ui.text(console, ix + iw - width - 2, row, f"[{spin[int(t * 20) % 4]:^{width}}]", fg=ui.DIM)
    else:
        ui.text(console, ix + iw - width - 2, row, f"[{status:^{width}}]", fg=colr)


def _fmt_alt(m):
    return f"{m:,} m" if m < 10000 else f"{m / 1000:.1f} km"


def _power_panel(console, rect, t, tt):
    x, y, pw, ph = rect
    ix, iw = x + 2, pw - 4
    reactor = _clamp((t - REACTOR_START) / (REACTOR_FULL - REACTOR_START))
    fuel = reactor * (state.fuel / max(1, state.max_fuel))
    thrust = _clamp(tt / 0.6) if tt > 0 else _clamp((t - COUNT_START) / 1.2) * 0.12

    def gauge(row, label, frac, colr, text=None):
        ui.text(console, ix, row, label, fg=ui.DIM)
        shown = text if text is not None else f"{int(frac * 100):3d}%"
        ui.right(console, ix + iw - 1, row, shown, fg=colr)
        ui.bar(console, ix, row + 1, iw, frac * 100, 100, colr)

    gauge(y + 2, "REACTOR OUTPUT", reactor, ui.ACCENT)
    gauge(y + 5, "FUEL CELLS", fuel, ui.GOOD,
          f"{int(fuel * state.max_fuel)}/{int(state.max_fuel)}")
    gauge(y + 8, "HULL INTEGRITY", 1.0 if t >= REACTOR_START else 0.0, ui.GOOD)
    gauge(y + 11, "MAIN ENGINE THRUST", thrust, ui.WARN if thrust < 0.99 else ui.KEY)

    ui.hline(console, x, y + 14, pw, fg=ui.BORDER)
    if ph < 24:
        return
    lift = _clamp(tt / LIFT_TIME) if tt > 0 else 0.0
    alt = int((max(0.0, tt) ** 2) * 900)
    vel = int(max(0.0, tt) * 430)
    g = 1.0 + (2.4 * _clamp(tt / 0.8) if tt > 0 else 0.0) * (0.9 + 0.1 * math.sin(t * 17))
    ui.kv(console, ix, y + 16, iw, "ALTITUDE", _fmt_alt(alt), value_fg=ui.KEY if tt > 0 else ui.FAINT)
    ui.kv(console, ix, y + 18, iw, "VELOCITY", f"{vel} m/s", value_fg=ui.KEY if tt > 0 else ui.FAINT)
    ui.kv(console, ix, y + 20, iw, "G-LOAD", f"{g:.1f} G", value_fg=ui.WARN if g > 2 else ui.TEXT)
    state_text = ("LAUNCH PAD" if tt < 0 else "ASCENT" if lift < 1.0 else "ORBIT BURN")
    ui.kv(console, ix, y + 22, iw, "STATUS", state_text, value_fg=ui.ACCENT)
    if ph >= 30 and t >= COUNT_START:
        ui.hline(console, x, y + 24, pw, fg=ui.BORDER)
        blink = int(t * 4) % 2 == 0
        text = "IGNITION ARMED" if tt < 0 else "ENGINES FIRING"
        ui.center(console, x + pw // 2, y + 26, text,
                  fg=ui.WARN if (tt >= 0 or blink) else ui.FAINT)


def _log_panel(console, rect, t):
    x, y, pw, ph = rect
    ix, iw = x + 2, pw - 4
    lines = []
    for ti, text in LOG:
        if t < ti:
            break
        shown = int((t - ti) * 70)
        lines.append((ti, text[:shown], shown < len(text)))
    rows = ph - 2
    for i, (ti, text, typing) in enumerate(lines[-rows:]):
        yy = y + 1 + i
        stamp = f"T{'+' if ti >= IGNITE else '-'}{abs(ti - IGNITE):04.1f}"
        ui.text(console, ix, yy, stamp, fg=ui.FAINT)
        ui.text(console, ix + 8, yy, ui.clip(text, iw - 9), fg=ui.TEXT)
        if typing and int(t * 8) % 2 == 0:
            _put(console, ix + 8 + len(text), yy, "█", ui.TEXT)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def draw(console, w, h):
    t = elapsed()
    tt = t - IGNITE
    console.draw_rect(0, 0, w, h, ord(" "), bg=ui.BG)
    lay = _layout(w, h)

    # --- header ----------------------------------------------------------------
    head = _online(t, ON_HEADER)
    if head:
        name = getattr(state.player_ship, "name", "Rogue").upper()
        ui.text(console, 3, 1, f"{name}  //  FLIGHT CONSOLE", fg=ui.scale_color(ui.TITLE, head))
        clock = f"T{'+' if tt >= 0 else '-'}{abs(tt):04.1f}s"
        ui.right(console, w - 4, 1, clock, fg=ui.KEY if tt >= 0 else ui.DIM)

    # --- consoles power on one by one ---------------------------------------------
    lv = _online(t, ON_LEFT)
    if lv:
        _panel(console, lay["left"], "Systems", lv)
        if lv >= 1.0:
            _systems_panel(console, lay["left"], t, tt)
    vv = _online(t, ON_VIEW)
    if vv:
        _panel(console, lay["view"], "Forward view", vv, "CAM 01")
        if vv >= 1.0:
            _viewport(console, lay["view"], t, tt)
    rv = _online(t, ON_RIGHT)
    if rv:
        _panel(console, lay["right"], "Power", rv)
        if rv >= 1.0:
            _power_panel(console, lay["right"], t, tt)
    gv = _online(t, ON_LOG)
    if gv:
        _panel(console, lay["log"], "Flight log", gv)
        if gv >= 1.0:
            _log_panel(console, lay["log"], t)

    ui.key_hint(console, w // 2 - 6, h - 2, "SPACE", "Skip", label_fg=ui.FAINT)

    # --- flashes: ignition bloom, then the white-out into the system ------------
    if 0 <= tt < 0.25:
        transitions.whiten(console, 0.3 * (1 - tt / 0.25))
    if t >= FLASH_AT:
        transitions.whiten(console, _clamp((t - FLASH_AT) / 0.5))
