"""Draw the in-game computer (hacking/computer.py) on a whole console.

Works at any console size >= 80x50, so the modern (120x62) and classic
(80x60) windows both use it. Reuses the shared ui toolkit; no new graphics
framework. Characters stay within the CP437 set the game's fonts support.
"""

import math
import textwrap
import time

from render import ui
from hacking.computer import APPS, BOOT_OK, GRID_COLS
from hacking.filesystem import FSError

# Retro-futuristic terminal palette: near-black teal, phosphor accents
T_BG = (4, 10, 13)
T_BORDER = (38, 104, 116)
T_PROMPT = (90, 220, 190)
ALERT_BG = (88, 18, 24)
TRACE_ORANGE = (255, 150, 60)
KIND_COLORS = {
    "out": ui.TEXT, "info": ui.ACCENT, "ok": ui.GOOD, "err": ui.BAD,
    "warn": ui.WARN, "trace": TRACE_ORANGE, "dim": ui.DIM, "head": ui.TITLE,
    "alert": (255, 235, 235), "cmd": ui.SEL_FG,
}
FADE_SECONDS = 0.22


def _logo():
    """'SR-OS' banner from a 5x5 block font (every glyph exactly 5 wide)."""
    g = {
        "S": [" ████", "█    ", " ███ ", "    █", "████ "],
        "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
        "-": ["     ", "     ", " ███ ", "     ", "     "],
        "O": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    }
    return ["  ".join(g[ch][r] for ch in "SR-OS") for r in range(5)]


LOGO = _logo()


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _fade(color, k):
    """Fade a colour in from the background: k 0 -> invisible, 1 -> full."""
    return ui.lerp_color(ui.BG, color, k)


def _typed(text, seconds, rate=45):
    """The part of text typed so far, `rate` characters per second."""
    return text[:max(0, int(seconds * rate))]
SIDE_W = 30


def trace_color(pct):
    return ui.GOOD if pct < 25 else ui.WARN if pct < 50 else TRACE_ORANGE if pct < 75 else ui.BAD


def _wrap(text, w):
    if len(text) <= w:
        return [text]
    lead = len(text) - len(text.lstrip(" "))
    return textwrap.wrap(text, w, subsequent_indent=" " * min(lead + 2, 8),
                         drop_whitespace=False, replace_whitespace=False) or [""]


def _meter(console, x, y, w, pct, fg, bg=None):
    """A gauge with a half-cell leading edge and a bright pip sweeping along
    the filled part (so a live trace looks alive even when it is not moving)."""
    exact = w * max(0.0, min(100.0, pct)) / 100
    filled = int(exact)
    half = exact - filled >= 0.5 and filled < w
    console.print(x, y, "█" * filled, fg=fg, bg=bg)
    if half:
        console.print(x + filled, y, "▌", fg=fg, bg=bg)
    rest = w - filled - (1 if half else 0)
    console.print(x + filled + (1 if half else 0), y, "░" * rest, fg=ui.FAINT, bg=bg)
    if filled > 2:
        pos = int(time.monotonic() * 14) % (filled + 8)
        if pos < filled:
            console.print(x + pos, y, "█", fg=ui.lerp_color(fg, (255, 255, 255), 0.65), bg=bg)


# ------------------------------------------------- animation bookkeeping
# All of it lives on the Computer object (c._...) so the engine is untouched.

NOISE = "#%&@$01?/\\"
REVEAL_CAP = 12            # at most this many fresh lines cascade at once
CASCADE_STEP = 0.035       # seconds between lines of a burst of output
CASCADE_MAX = 1.2          # a long listing never takes longer than this


def _assign_born(c):
    """When each log entry first appeared; new entries cascade one after
    another. Entries already there when the terminal is first drawn (or beyond
    the cap) count as old, so a resumed session does not replay itself."""
    log = c.terminal.log
    born = c.__dict__.setdefault("_born", {})
    now = time.monotonic()
    live = {id(e) for e in log}
    for k in [k for k in born if k not in live]:
        del born[k]
    new = [e for e in log if id(e) not in born]
    if not new:
        return born
    first = not c.__dict__.get("_born_started")
    c._born_started = True
    old_cut = len(new) if first else max(0, len(new) - REVEAL_CAP)
    step = min(CASCADE_STEP, CASCADE_MAX / max(1, len(new) - old_cut))
    for i, e in enumerate(new):
        born[id(e)] = 0.0 if i < old_cut else now + (i - old_cut) * step
    return born


def _scramble(text, age, span):
    """Text that resolves out of noise as age goes 0 -> span (the "decode" effect)."""
    frac = max(0.0, min(1.0, age / span))
    tick = int(time.monotonic() * 30)
    out = []
    for i, ch in enumerate(text):
        if ch == " " or (i * 7919 + tick * 31) % 100 < frac * 100:
            out.append(ch)
        else:
            out.append(NOISE[(i * 31 + tick) % len(NOISE)])
    return "".join(out)


def _fresh_line(kind, text, color, age):
    """(text, colour) of a log line `age` seconds after it appeared: it types
    in quickly, glows white, and alerts decode out of noise."""
    if age >= 0.4:
        return text, color
    if kind == "alert":
        text = _scramble(text, age, 0.35)
    else:
        text = text[:max(1, int(age * 600))]
    return text, ui.lerp_color((255, 255, 255), color, age / 0.4)


def _trace_pct(c):
    tr = c.session.trace or (max(c.session.traces.values(), key=lambda t: t.value)
                             if c.session.traces else None)
    return tr.pct if tr else 0


def _shown_pct(c, pct):
    """The trace as drawn: eases toward the real value instead of jumping."""
    now = time.monotonic()
    st = c.__dict__.get("_tshow")
    if st is None:
        c._tshow = [float(pct), now]
        return float(pct)
    v, last = st
    v += (pct - v) * (1 - math.exp(-min(0.25, now - last) / 0.18))
    if abs(pct - v) < 0.3:
        v = float(pct)
    c._tshow = [v, now]
    return v


def _objective_age(c, o):
    """Seconds since an objective was completed (None if it is not done).
    Objectives already done when first drawn do not flash."""
    seen = c.__dict__.setdefault("_objdone", {})
    if not o.done:
        seen.pop(id(o), None)
        return None
    if id(o) not in seen:
        seen[id(o)] = -999.0 if c.__dict__.get("_obj_started") else time.monotonic()
    return time.monotonic() - seen[id(o)]


def _rain(console, W, H, t):
    """Faint hex digits falling down the desktop wallpaper."""
    for col in range(3, W - 2, 5):
        seed = col * 7919
        speed = 4 + seed % 5
        length = 5 + seed % 6
        period = H + length + 10
        head = int(t * speed + seed % period) % period
        for k in range(length):
            y = head - k
            if 1 <= y < H - 1:
                g = "0123456789ABCDEF"[(seed + y * 13 + (int(t * 6) if k == 0 else 0)) % 16]
                glow = 0.9 if k == 0 else 0.5 * (1 - k / length)
                console.print(col, y, g, fg=ui.lerp_color(ui.BG, (40, 150, 120), glow), bg=ui.BG)


def draw(console, c):
    """Draw the whole computer for one frame."""
    W, H = console.width, console.height
    console.clear(bg=ui.BG)
    if c.screen == "boot":                     # bare screen: no wallpaper or bars
        _boot(console, c, W, H)
        _bottombar(console, c, W, H)
        return
    _wallpaper(console, W, H)
    if c.screen == "desktop":
        _rain(console, W, H, time.monotonic())
    _topbar(console, c, W)
    {"desktop": _desktop, "terminal": _terminal, "files": _files,
     "mission": _mission, "result": _result}[c.screen](console, c, W, H)
    _bottombar(console, c, W, H)
    # screen change: the new screen opens from the middle with bright edges
    t = (time.monotonic() - c.changed_at) / FADE_SECONDS
    if t < 1:
        band = max(2, int(H * _ease(t)))
        top = (H - band) // 2
        console.draw_rect(0, 0, W, top, ord(" "), bg=ui.BG)
        console.draw_rect(0, top + band, W, H - top - band, ord(" "), bg=ui.BG)
        console.draw_rect(0, top, W, 1, ord("─"), fg=ui.ACCENT, bg=ui.BG)
        console.draw_rect(0, top + band - 1, W, 1, ord("─"), fg=ui.ACCENT, bg=ui.BG)


def _wallpaper(console, W, H):
    for y in range(2, H - 2, 4):
        for x in range(3, W - 2, 8):
            console.print(x + (y // 4 % 2) * 4, y, "·", fg=ui.FAINT, bg=ui.BG)


def _topbar(console, c, W):
    console.draw_rect(0, 0, W, 1, ord(" "), bg=ui.PANEL_BG)
    ui.text(console, 1, 0, f"{c.device.os_name}", fg=T_PROMPT, bg=ui.PANEL_BG)
    ui.text(console, 12, 0, f"{c.device.name} · {c.device.username}", fg=ui.DIM, bg=ui.PANEL_BG)
    s = c.session
    if s.connection:
        link, col = f"LINK {s.connection.address}", ui.GOOD
    else:
        link, col = ("LINK CUT" if s.lockdown else "OFFLINE"), (ui.BAD if s.lockdown else ui.DIM)
    ui.right(console, W - 2, 0, link, fg=col, bg=ui.PANEL_BG)


def _bottombar(console, c, W, H):
    console.draw_rect(0, H - 1, W, 1, ord(" "), bg=ui.PANEL_BG)
    if c.notice:
        ui.text(console, 2, H - 1, c.notice, fg=ui.WARN, bg=ui.PANEL_BG)
        return
    hints = {
        "boot": [("any key", "Skip")],
        "desktop": [("←↑↓→", "Select"), ("ENTER", "Open"), ("T/F/M", "Quick open"), ("R", "Real-time trace"), ("ESC", "Leave computer")],
        "terminal": [("ENTER", "Run"), ("TAB", "Complete"), ("↑↓", "History"),
                     ("PGUP/PGDN", "Scroll"), ("ESC", "Desktop")],
        "files": [("↑↓", "Select"), ("ENTER", "Open folder"), ("BKSP", "Up"), ("ESC", "Desktop")],
        "mission": [("ESC", "Desktop")],
        "result": [("ENTER", "Desktop")] + ([("R", "Retry mission")] if c.can_retry else []),
    }[c.screen]
    ui.hint_row(console, 2, H - 1, hints, bg=ui.PANEL_BG)


# ------------------------------------------------------------------ boot
def _boot(console, c, W, H):
    t, full = c.boot_t, c.boot_full
    dur = c.boot_duration
    logo_at = 2.5 if full else 0.05
    if full:
        x, y = max(3, W // 2 - 30), 3
        for i, (at, text, status) in enumerate(c.boot_script()):
            if t < at:
                break
            shown = _typed(text, t - at, 60)
            console.print(x, y + i, shown, fg=ui.TEXT if status else ui.TITLE, bg=ui.BG)
            if status:
                dots = "." * max(2, 44 - len(text))
                if t >= at + BOOT_OK:
                    console.print(x + len(text) + 1, y + i, dots, fg=ui.FAINT, bg=ui.BG)
                    console.print(x + 46, y + i, f"[ {status} ]", fg=ui.GOOD, bg=ui.BG)
                else:
                    console.print(x + len(text) + 1, y + i, "." * int((t - at) * 60 % 6),
                                  fg=ui.FAINT, bg=ui.BG)
    k = _ease((t - logo_at) / 0.5)
    ly = H // 2 + (2 if full else -3)
    if k > 0:
        flick = 1.0 if int(t * 24) % 7 else 0.8        # a slight phosphor flicker
        for i, row in enumerate(LOGO):
            reveal = _typed(row, (t - logo_at) - i * 0.06, 90)
            console.print(W // 2 - len(row) // 2, ly + i, reveal,
                          fg=_fade(T_PROMPT, k * flick), bg=ui.BG)
        ui.center(console, W // 2, ly + 6, c.device.os_name if full else "resuming session",
                  fg=_fade(ui.DIM, k), bg=ui.BG)
    # progress bar
    bw = min(50, W - 16)
    bx, by = W // 2 - bw // 2, H - 8
    frac = max(0.0, min(1.0, (t - 0.1) / max(0.1, dur - 0.5)))
    console.print(bx, by, "█" * int(bw * frac), fg=T_PROMPT, bg=ui.BG)
    console.print(bx + int(bw * frac), by, "░" * (bw - int(bw * frac)), fg=ui.FAINT, bg=ui.BG)
    ui.center(console, W // 2, by + 1, f"{int(frac * 100):3d}%", fg=ui.DIM, bg=ui.BG)


# --------------------------------------------------------------- desktop
def _desktop(console, c, W, H):
    now = time.monotonic()
    el = now - c.changed_at
    cell_w, cell_h = 24, 9
    rows = (len(APPS) + GRID_COLS - 1) // GRID_COLS
    gx = (W - GRID_COLS * cell_w) // 2
    gy = max(3, (H - rows * cell_h) // 2 - 3)
    title = f"{c.device.name.upper()}  ·  {c.device.os_name}"
    ui.center(console, W // 2, gy - 2, _typed(title, el, 50).ljust(len(title)) if el < 1 else title,
              fg=ui.TITLE)
    glyphs = {"terminal": ">_", "files": "[=]", "mission": "(!)", "mail": "[@]",
              "browser": "(~)", "crypto": "{#}"}
    pulse = (math.sin(now * 4) + 1) / 2
    for i, (app_id, label, hot) in enumerate(APPS):
        k = _ease((el - 0.05 - 0.07 * i) / 0.2)         # icons fade in one after another
        if k <= 0:
            continue
        x, y = gx + (i % GRID_COLS) * cell_w, gy + (i // GRID_COLS) * cell_h
        y += int(round((1 - k) * 2))                    # ... sliding up into place
        sel = i == c.desktop_index
        on = c.installed(app_id)
        edge = ui.lerp_color(ui.BORDER_HI, ui.ACCENT, pulse) if sel else T_BORDER
        fg = _fade(edge if on else ui.FAINT, k)
        bg = ui.SEL_BG if sel else ui.PANEL_BG
        ui.frame(console, x, y, cell_w - 2, cell_h - 1, "", fg=fg, bg=bg, double=sel)
        cx = x + (cell_w - 2) // 2
        ui.center(console, cx, y + 2, glyphs[app_id],
                  fg=_fade(T_PROMPT if on else ui.FAINT, k), bg=bg)
        ui.center(console, cx, y + 4, label,
                  fg=_fade((ui.SEL_FG if sel else ui.TEXT) if on else ui.FAINT, k), bg=bg)
        sub = (f"[{hot}]" if hot else "") if on else "not installed"
        ui.center(console, cx, y + 5, sub, fg=_fade(ui.DIM if on else ui.FAINT, k), bg=bg)
    m = c.mission
    if m and el > 0.5:
        k = _ease((el - 0.5) / 0.3)
        d, n = m.progress()
        y = gy + rows * cell_h + 1
        state = {"active": f"{d}/{n} objectives", "success": "COMPLETE", "failed": "FAILED"}[m.status]
        col = {"active": ui.TEXT, "success": ui.GOOD, "failed": ui.BAD}[m.status]
        ui.center(console, W // 2, y, f"Active job: {m.title}  ·  {state}", fg=_fade(col, k))
        ui.center(console, W // 2, y + 2, "Real-time trace: " + ("ON" if c.realtime else "OFF")
                  + "   (press R to switch)", fg=_fade(ui.WARN if c.realtime else ui.DIM, k))


# -------------------------------------------------------------- terminal
def _wrapped_log(c, width):
    """[(kind, text, born)] for the whole log; `born` is when the line appears."""
    log = c.terminal.log
    born = _assign_born(c)
    key = (id(log), len(log), id(log[-1]) if log else 0, width)
    cache = getattr(c, "_wrap_cache", None)
    if cache and cache[0] == key:
        return cache[1]
    lines = []
    for entry in log:
        b = born.get(id(entry), 0.0)
        for part in _wrap(entry.text, width):
            lines.append((entry.kind, part, b))
    c._wrap_cache = (key, lines)
    return lines


def _terminal(console, c, W, H):
    s, t = c.session, c.terminal
    x, y, w, h = 1, 1, W - 2, H - 3
    right = f"{s.connection.address}" if s.connection else "offline"
    shown_pct = _shown_pct(c, _trace_pct(c))
    border = T_BORDER
    if shown_pct >= 75:                   # the frame throbs red when the trace is critical
        border = ui.lerp_color(T_BORDER, ui.BAD, (math.sin(time.monotonic() * 6) + 1) / 2)
    ui.frame(console, x, y, w, h, f"Terminal · {t.prompt().rstrip('$')}", fg=border,
             bg=T_BG, right_title=right)
    wide = W >= 100
    side = SIDE_W if wide else 0
    ix, iw = x + 2, w - 4 - (side + 1 if wide else 0)
    top = y + 1
    if not wide:                       # narrow console: trace strip instead of the side panel
        _trace_strip(console, c, ix, top, w - 4)
        top += 2
    out_h = y + h - 3 - top
    lines = _wrapped_log(c, iw)
    now = time.monotonic()
    count = len(lines)                    # lines of a fresh burst are not "there" yet
    while count and lines[count - 1][2] > now:
        count -= 1
    c.scroll = max(0, min(c.scroll, max(0, count - out_h)))
    end = count - c.scroll
    for row, (kind, text, born) in enumerate(lines[max(0, end - out_h):end]):
        yy = top + out_h - min(out_h, end) + row
        age = now - born
        if kind == "alert":
            shown, fg = _fresh_line(kind, text, KIND_COLORS["alert"], age)
            flash = ALERT_BG if age > 0.3 or int(age * 20) % 2 else (150, 30, 40)
            console.draw_rect(ix - 1, yy, iw + 2, 1, ord(" "), bg=flash)
            console.print(ix, yy, shown, fg=fg, bg=flash)
        elif kind == "cmd":
            p, sep, rest = text.partition("$ ")
            console.print(ix, yy, p + sep, fg=T_PROMPT, bg=T_BG)
            console.print(ix + len(p + sep), yy, rest, fg=KIND_COLORS["cmd"], bg=T_BG)
        else:
            shown, fg = _fresh_line(kind, text, KIND_COLORS[kind], age)
            console.print(ix, yy, shown, fg=fg, bg=T_BG)
    if c.scroll:
        ui.right(console, ix + iw - 1, top, f"▲ scrolled {c.scroll}", fg=ui.WARN, bg=T_BG)
    ui.scrollbar(console, ix + iw, top, out_h, count - out_h - c.scroll if count > out_h else 0,
                 out_h, max(count, out_h), fg=T_BORDER, bg=T_BG)
    # prompt line
    py = y + h - 2
    console.draw_rect(x + 1, py - 1, iw + 2, 1, ord("─"), fg=T_BORDER, bg=T_BG)
    prompt = t.prompt() + " "
    room = iw - len(prompt) - 1
    shown = c.input[-room:] if room > 0 else ""
    cursor = "█" if int(time.monotonic() * 2) % 2 == 0 else " "
    console.print(ix, py, prompt, fg=T_PROMPT, bg=T_BG)
    console.print(ix + len(prompt), py, shown + cursor, fg=ui.SEL_FG, bg=T_BG)
    if wide:
        _side_panel(console, c, x + w - side - 2, y + 1, side, h - 2)


def _trace_strip(console, c, x, y, w):
    tr = c.session.trace or (max(c.session.traces.values(), key=lambda t: t.value)
                             if c.session.traces else None)
    pct = tr.pct if tr else 0
    label = f"TRACE {pct:>3}% {tr.level if tr else 'CLEAR'}"
    col = ui.SEL_FG if c.trace_flashing() else trace_color(pct)
    console.print(x, y, label, fg=col, bg=T_BG)
    _meter(console, x + len(label) + 1, y, w - len(label) - 1, _shown_pct(c, pct), col, bg=T_BG)
    d, n = c.mission.progress() if c.mission else (0, 0)
    nxt = c.session.next_tick_in()
    clock = f"   +1% in {nxt:.0f}s" if nxt is not None else ""
    ui.text(console, x, y + 1, f"Objectives {d}/{n}   Extracted {len(c.session.downloads)}{clock}",
            fg=ui.DIM, bg=T_BG)


def _side_panel(console, c, x, y, w, h):
    s = c.session
    console.draw_rect(x - 1, y, 1, h, ord("│"), fg=T_BORDER, bg=T_BG)
    ix, iw = x + 1, w - 2
    ui.text(console, ix, y, "CONNECTION", fg=ui.TITLE, bg=T_BG)
    if s.connection:
        host = s.open_host
        ui.text(console, ix, y + 1, ui.clip(f"net  {s.connection.address}", iw), fg=ui.GOOD, bg=T_BG)
        ui.text(console, ix, y + 2, ui.clip(f"host {host.name if host else '-'}", iw),
                fg=ui.TEXT if host else ui.DIM, bg=T_BG)
        ui.text(console, ix, y + 3, ui.clip(
            f"as   {s.user_of(host)}" if host else "as   -", iw), fg=ui.DIM, bg=T_BG)
    else:
        ui.text(console, ix, y + 1, "LINK CUT" if s.lockdown else "offline",
                fg=ui.BAD if s.lockdown else ui.DIM, bg=T_BG)
    tr = s.trace or (max(s.traces.values(), key=lambda t: t.value) if s.traces else None)
    pct = tr.pct if tr else 0
    col = ui.SEL_FG if c.trace_flashing() else trace_color(pct)
    ui.text(console, ix, y + 5, "SECURITY TRACE", fg=ui.TITLE, bg=T_BG)
    _meter(console, ix, y + 6, iw, _shown_pct(c, pct), col, bg=T_BG)
    ui.text(console, ix, y + 7, f"{pct}%  {tr.level if tr else 'CLEAR'}", fg=col, bg=T_BG)
    if pct >= 75 and int(time.monotonic() * 3) % 2 == 0:
        ui.text(console, ix, y + 8, "!! DISCONNECT NOW !!", fg=ui.BAD, bg=T_BG)
    nxt = s.next_tick_in()
    if nxt is not None:
        ui.text(console, ix, y + 8 if pct < 75 else y + 9,
                f"clock: +1% in {nxt:3.0f}s", fg=ui.DIM, bg=T_BG)
    elif not s.realtime:
        ui.text(console, ix, y + 9, "real-time trace off", fg=ui.FAINT, bg=T_BG)
    ui.text(console, ix, y + 11, "OBJECTIVES", fg=ui.TITLE, bg=T_BG)
    row = y + 12
    for o in (c.mission.objectives if c.mission else []):
        mark = "[x] " if o.done else "[ ] "
        age = _objective_age(c, o)
        glow = max(0.0, 1.0 - age / 1.2) if age is not None else 0.0   # fresh completion
        for i, part in enumerate(ui.wrap(o.text, iw - 4)):
            if row >= y + h - 2:
                break
            line_bg = ui.lerp_color(T_BG, (24, 84, 52), glow)
            if glow:
                console.draw_rect(ix - 1, row, iw + 1, 1, ord(" "), bg=line_bg)
            console.print(ix, row, mark if i == 0 else "    ",
                          fg=ui.lerp_color(ui.GOOD, (255, 255, 255), glow) if o.done else ui.DIM, bg=line_bg)
            console.print(ix + 4, row, part,
                          fg=ui.lerp_color(ui.DIM, (255, 255, 255), glow) if o.done else ui.TEXT, bg=line_bg)
            row += 1
    c._obj_started = True
    ui.text(console, ix, y + h - 1, f"extracted files: {len(s.downloads)}", fg=ui.DIM, bg=T_BG)


# ----------------------------------------------------------------- files
def _files(console, c, W, H):
    x, y, w, h = 3, 2, W - 6, H - 5
    path, nodes = c.files_listing()
    ui.frame(console, x, y, w, h, f"Files · {path}", fg=T_BORDER, bg=T_BG,
             right_title=f"{len(nodes)} items")
    c.files_index = max(0, min(c.files_index, len(nodes) - 1))
    lw = max(28, w // 3)
    for i, n in enumerate(nodes):
        yy = y + 2 + i
        if yy >= y + h - 1:
            break
        sel = i == c.files_index
        if sel:
            console.draw_rect(x + 1, yy, lw, 1, ord(" "), bg=ui.SEL_BG)
        name = n.name + ("/" if n.is_dir else "")
        console.print(x + 2, yy, ui.clip(name, lw - 2), fg=(ui.SEL_FG if sel else (ui.ACCENT if n.is_dir else ui.TEXT)),
                      bg=ui.SEL_BG if sel else None)
    if not nodes:
        ui.text(console, x + 2, y + 2, "(empty folder)", fg=ui.DIM, bg=T_BG)
    console.draw_rect(x + lw + 1, y + 1, 1, h - 2, ord("│"), fg=T_BORDER, bg=T_BG)
    if nodes:
        n = nodes[c.files_index]
        px, pw = x + lw + 3, w - lw - 5
        if n.is_dir:
            ui.text(console, px, y + 2, f"Folder · {len(n.children)} items", fg=ui.DIM, bg=T_BG)
        else:
            ui.text(console, px, y + 2, f"{n.name} · {n.size} bytes", fg=ui.TITLE, bg=T_BG)
            sel_key = (path, c.files_index, n.name)
            st = c.__dict__.get("_fsel")
            if st is None or st[0] != sel_key:
                st = c._fsel = (sel_key, time.monotonic())
            budget = int((time.monotonic() - st[1]) * 900)      # the preview types itself in
            for i, line in enumerate([p for raw in n.text().split("\n") for p in _wrap(raw, pw)][:h - 6]):
                console.print(px, y + 4 + i, line[:max(0, budget)], fg=ui.TEXT, bg=T_BG)
                budget -= len(line)
                if budget <= 0:
                    break


# --------------------------------------------------------------- mission
def _mission(console, c, W, H):
    s, m = c.session, c.mission
    w, h = min(86, W - 6), min(30, H - 5)
    x, y = (W - w) // 2, 3
    ui.frame(console, x, y, w, h, "Mission", fg=T_BORDER, bg=T_BG,
             right_title={"active": "in progress", "success": "complete", "failed": "failed"}[m.status])
    ui.text(console, x + 3, y + 2, m.title, fg=ui.TITLE, bg=T_BG)
    row = y + 4
    for b in m.briefing:
        row += ui.paragraph(console, x + 3, row, w - 6, b, fg=ui.TEXT, bg=T_BG)
    row += 1
    ui.text(console, x + 3, row, "OBJECTIVES", fg=ui.TITLE, bg=T_BG)
    for o in m.objectives:
        row += 1
        console.print(x + 3, row, "[x]" if o.done else "[ ]", fg=ui.GOOD if o.done else ui.DIM, bg=T_BG)
        console.print(x + 7, row, ui.clip(o.text, w - 10), fg=ui.DIM if o.done else ui.TEXT, bg=T_BG)
    row += 2
    ui.paragraph(console, x + 3, row, w - 6,
                 "Security trace rises when you scan, probe, exploit, fail a login, "
                 "touch restricted files or extract data. At 100% the remote system "
                 "locks you out and the job fails.", fg=ui.DIM, bg=T_BG)


# ---------------------------------------------------------------- result
def _result(console, c, W, H):
    m = c.mission
    r = m.result
    won = r.get("won")
    w, h = 62, 19
    x, y = (W - w) // 2, (H - h) // 2
    col = ui.GOOD if won else ui.BAD
    console.draw_rect(x + 1, y + 1, w, h, ord(" "), bg=(0, 0, 0))
    ui.frame(console, x, y, w, h, "Mission result", fg=col, bg=T_BG)
    el = time.monotonic() - c.changed_at
    headline = "MISSION COMPLETE" if won else "MISSION FAILED"
    if not won and int(el * 8) % 2 == 0 and el < 1.2:
        headline = headline.replace("A", "#")           # brief glitch on failure
    ui.center(console, x + w // 2, y + 2, _typed(headline, el, 30).ljust(len(headline)).strip()
              if el < 1 else headline, fg=col, bg=T_BG)
    ui.center(console, x + w // 2, y + 3, m.title, fg=ui.DIM, bg=T_BG)
    if el > 0.4:
        ui.paragraph(console, x + 4, y + 5, w - 8, m.success_text if won else m.failure_text,
                     fg=ui.TEXT, bg=T_BG)
    d, n = r["objectives"]
    for i, (k, v) in enumerate([("Rating", r["rating"]), ("Peak trace", f"{r['trace']}%"),
                                ("Commands used", r["commands"]), ("Objectives", f"{d}/{n}")]):
        if el > 0.8 + 0.25 * i:
            ui.kv(console, x + 6, y + 9 + i, w - 12, k, v, value_fg=col, bg=T_BG)
    ui.hint_row_centered(console, x + w // 2, y + h - 3,
                         [("ENTER", "Desktop")] + ([("R", "Retry mission")] if c.can_retry else []),
                         bg=T_BG)
