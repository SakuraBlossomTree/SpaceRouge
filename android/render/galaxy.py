"""Render the GALAXY chart: a scrolling, zoomable window onto the galaxy.

Stars live in world coordinates (see core/world.py GALAXY_W x GALAXY_H);
core/galaxy_view.py turns them into screen cells for the current camera
position and zoom level.
"""

import random
import time

import numpy as np

from core import state, galaxy_view as view
from core.world import STAR_TYPES, GALAXY_W, GALAXY_H
from effects.effects import twinkle_color
from render import ui

LINK_FG = (75, 115, 155)
DEBUG_LINK_FG = (45, 45, 60)
NAME_FG = (95, 110, 140)
LINKED_FG = (130, 160, 195)

MINI_W, MINI_H = 26, 20     # minimap frame size (cells, incl. border)
MINIMAP_INSET = 1           # cells from the right edge (mobile: clear of its side panel)

_dust = None


# ---------------------------------------------------------------------------
# Small safe drawing helpers (everything is clipped to the viewport)
# ---------------------------------------------------------------------------

def _put(console, x, y, ch, fg, bg=None):
    if 0 <= x < console.width and 0 <= y < console.height:
        console.print(x, y, ch, fg=fg, bg=bg)


def _text(console, x, y, s, fg, bg=None):
    if not (0 <= y < console.height):
        return
    if x < 0:
        s, x = s[-x:], 0
    s = s[: max(0, console.width - x)]
    if s:
        console.print(x, y, s, fg=fg, bg=bg)


def _line(console, x0, y0, x1, y1, ch, fg):
    """Bresenham between two screen cells, endpoints excluded, clipped."""
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    if dx + dy > 2000:
        return
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        if (x, y) != (x0, y0) and (x, y) != (x1, y1):
            if 0 <= x < console.width and 0 <= y < console.height \
                    and console.rgb["ch"][y, x] in (32, ord("·"), ord(".")):
                console.print(x, y, ch, fg=fg)
        if x == x1 and y == y1:
            break
        e2 = err * 2
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


_FREE = (0, 32, ord("·"), ord("."))


def _free(console, x, y, n):
    """True if n cells starting at x are empty (dust doesn't count)."""
    if not (0 <= y < console.height) or x < 0 or x + n > console.width:
        return False
    return all(int(console.rgb["ch"][y, x + i]) in _FREE for i in range(n))


def _label(console, sx, sy, text, fg, force=False):
    """Name tag beside a star; tries right then left, skips if both overlap."""
    for lx in (sx + 2, sx - 1 - len(text)):
        if _free(console, lx - 1, sy, len(text) + 2):
            _text(console, lx, sy, text, fg)
            return True
    if force:
        lx = sx + 2 if sx + 2 + len(text) < console.width else sx - 1 - len(text)
        _text(console, lx, sy, text, fg)
    return False


# ---------------------------------------------------------------------------
# Layers
# ---------------------------------------------------------------------------

def _draw_dust(console):
    """~2,000 background dots, projected and drawn with numpy in one go."""
    global _dust
    if _dust is None:
        rng = random.Random(7)
        pts = [(rng.uniform(0, GALAXY_W), rng.uniform(0, GALAXY_H),
                rng.choice("·.."), rng.randint(20, 45))
               for _ in range(GALAXY_W * GALAXY_H // 14)]
        _dust = (np.array([p[0] for p in pts]), np.array([p[1] for p in pts]),
                 np.array([ord(p[2]) for p in pts], dtype=np.int32),
                 np.array([(p[3], p[3], int(p[3] * 1.4)) for p in pts], dtype=np.uint8))
    dx, dy, codes, cols = _dust
    # thin the dust out when zoomed out so it doesn't turn into fog
    step = max(1, int(round(view.scale() ** 2)))
    s = view.scale()
    sx = np.rint((dx[::step] - state.galaxy_cam_x) / s + view.VIEW_W / 2).astype(np.intp)
    sy = np.rint((dy[::step] - state.galaxy_cam_y) / s + view.VIEW_H / 2).astype(np.intp)
    m = (sx >= 0) & (sx < console.width) & (sy >= 0) & (sy < console.height)
    rgb = console.rgb
    rgb["ch"][sy[m], sx[m]] = codes[::step][m]
    rgb["fg"][sy[m], sx[m]] = cols[::step][m]


def _draw_edges(console):
    """Faint border showing where the galaxy ends."""
    x0, y0 = view.project(0, 0)
    x1, y1 = view.project(GALAXY_W, GALAXY_H)
    fg = (40, 50, 75)
    for x in range(max(0, x0), min(console.width, x1 + 1)):
        _put(console, x, y0, "─", fg)
        _put(console, x, y1, "─", fg)
    for y in range(max(0, y0), min(console.height, y1 + 1)):
        _put(console, x0, y, "│", fg)
        _put(console, x1, y, "│", fg)


def _draw_minimap(console, stars, targets):
    """Overview in the top-right corner with the visible area outlined."""
    w, h = MINI_W, MINI_H
    x, y = console.width - w - MINIMAP_INSET, 1
    iw, ih = w - 2, h - 2
    ui.frame(console, x, y, w, h, "Map", fg=ui.BORDER, bg=(8, 11, 20),
             double=False, title_fg=ui.DIM)

    def mini(wx, wy):
        return (x + 1 + min(iw - 1, int(wx / GALAXY_W * iw)),
                y + 1 + min(ih - 1, int(wy / GALAXY_H * ih)))

    for star in stars:
        mx, my = mini(star.x, star.y)
        fg = ui.KEY if star.name in targets else ui.scale_color(
            ui.vivid(STAR_TYPES[star.type]["color"]), 0.7)
        console.print(mx, my, "·", fg=fg, bg=(8, 11, 20))

    # visible area rectangle
    vx0, vy0, vx1, vy1 = view.visible_rect()
    ax, ay = mini(max(0, vx0), max(0, vy0))
    bx, by = mini(min(GALAXY_W - 0.01, vx1), min(GALAXY_H - 0.01, vy1))
    rect_fg = (150, 170, 210)
    for cx in range(ax, bx + 1):
        for cy in (ay, by):
            console.print(cx, cy, "─", fg=rect_fg)
    for cy in range(ay, by + 1):
        for cx in (ax, bx):
            console.print(cx, cy, "│", fg=rect_fg)
    for cx, cy, ch in ((ax, ay, "┌"), (bx, ay, "┐"), (ax, by, "└"), (bx, by, "┘")):
        console.print(cx, cy, ch, fg=rect_fg)

    if state.current_star:
        mx, my = mini(state.current_star.x, state.current_star.y)
        console.print(mx, my, "@", fg=ui.PLAYER, bg=(8, 11, 20))
    return (x, y, w, h)


def _draw_zoom_bar(console, routes=True):
    """Bottom-left: zoom level indicator."""
    y = console.height - 1
    _text(console, 1, y, "ZOOM", ui.DIM)
    x = 6
    levels = [(name, i == state.galaxy_zoom and not state.galaxy_preview)
              for i, name in reversed(list(enumerate(view.ZOOM_NAMES)))]
    levels.append(("system", bool(state.galaxy_preview)))
    for name, on in levels:
        _text(console, x, y, f" {name} ", (0, 0, 0) if on else ui.FAINT,
              ui.ACCENT if on else None)
        x += len(name) + 2
    _text(console, x + 1, y, "[+/-]", ui.FAINT)
    if not routes:
        return
    x += 7
    on = state.galaxy_routes
    _text(console, x, y, " routes ", (0, 0, 0) if on else ui.FAINT,
          (255, 165, 60) if on else None)
    _text(console, x + 9, y, "[R]", ui.FAINT)


# ---------------------------------------------------------------------------
# Main draw
# ---------------------------------------------------------------------------

def draw(console, width, height, stars):
    if state.galaxy_preview:
        star = next((s for s in stars if s.name == state.galaxy_preview), None)
        if star is not None:
            draw_preview(console, width, height, star, stars)
            return
        state.galaxy_preview = None
    t = time.time()
    key = _static_key(console, stars)
    if key != _static["key"]:
        _draw_static(console, width, height, stars)
        _static["key"] = key
        _static["rgb"] = console.rgb.copy()
    else:
        console.rgb[:] = _static["rgb"]       # one numpy copy instead of ~300 prints

    # --- animated bits on top of the cached chart -------------------------------
    fg_a, bg_a = console.rgb["fg"], console.rgb["bg"]
    for sx, sy, base, i in _static["stars"]:
        fg_a[sy, sx] = twinkle_color(base, t, speed=5.0, phase=i * 1.3)
    if _static["you"] is not None:
        sx, sy, under = _static["you"]
        blink = int(t * 2) % 2 == 0
        fg_a[sy, sx] = (0, 0, 0) if blink else ui.PLAYER
        bg_a[sy, sx] = ui.PLAYER if blink else under

    # --- scan cursor (always live) -------------------------------------------------------------
    state.look_object = None
    if state.look_mode:
        cx, cy = view.project(state.look_x, state.look_y)
        state.look_object = view.star_at_cell(stars, cx, cy)
        if view.on_screen(cx, cy):
            blink = int(t * 3) % 2 == 0
            ch = int(console.rgb["ch"][cy, cx])
            glyph = "+" if ch in (0, 32) else chr(ch)
            console.print(cx, cy, glyph, fg=(0, 0, 0),
                          bg=ui.KEY if blink else (150, 110, 30))


# The chart is cached: everything except the twinkling stars, the blinking
# "@" and the scan cursor only changes when the camera moves, you travel, a
# contract changes or a day passes. Rebuilding it costs ~300 single-cell
# prints of Python - on a phone that was most of each frame's time.
_static = {"key": None, "rgb": None, "stars": [], "you": None}


def _static_key(console, stars):
    return (console.width, console.height, len(stars),
            round(state.galaxy_cam_x, 3), round(state.galaxy_cam_y, 3), state.galaxy_zoom,
            view.VIEW_W, view.VIEW_H, MINIMAP_INSET,
            state.galaxy_routes, state.galaxy_minimap, state.DEBUG, state.day,
            getattr(state.current_star, "name", None),
            getattr(state.current_system, "name", None),
            state.mission_nav_target,
            tuple((m.dest_system, m.status) for m in state.missions))


def _draw_static(console, width, height, stars):
    """Draw the whole chart with stars in their base colours, then note which
    star cells (and the "@") are still visible so draw() can animate them."""
    t = 0.0
    s = view.scale()
    star_map = {star.name: star for star in stars}
    proj = {star.name: view.project(star.x, star.y) for star in stars}

    _draw_dust(console)
    _draw_edges(console)

    # --- trade-route heat (R) -------------------------------------------------
    if state.galaxy_routes and state.economy is not None:
        routes = state.economy.top_routes(30)
        top = routes[0][0] if routes else 1
        for vol, (a, b), _good in reversed(routes):
            if a in proj and b in proj:
                heat = vol / top
                col = ui.lerp_color((70, 60, 110), (255, 165, 60), heat)
                _line(console, *proj[a], *proj[b], "•" if heat > 0.45 else "·", col)

    # --- jump links ---------------------------------------------------------
    if state.DEBUG:
        drawn = set()
        for star in stars:
            for jp in star.system.jump_points:
                pair = tuple(sorted([star.name, jp.destination]))
                if pair in drawn or jp.destination not in proj:
                    continue
                drawn.add(pair)
                _line(console, *proj[star.name], *proj[jp.destination], "·", DEBUG_LINK_FG)

    linked = set()
    if state.current_system and state.current_star:
        for jp in state.current_system.jump_points:
            if jp.destination not in proj:
                continue
            linked.add(jp.destination)
            _line(console, *proj[state.current_star.name], *proj[jp.destination],
                  "·", LINK_FG)

    # --- contract targets ------------------------------------------------------
    targets = {m.dest_system for m in state.missions if m.status == "active"}
    if state.mission_nav_target:
        targets.add(state.mission_nav_target)

    # --- labels. Important ones first so they win any overlap. -----------------
    # Star glyphs are reserved first so labels never cover a star.
    for star in stars:
        sx, sy = proj[star.name]
        if view.on_screen(sx, sy):
            console.print(sx, sy, "*", fg=(0, 0, 0))
    if state.current_star:
        sx, sy = proj[state.current_star.name]
        if view.on_screen(sx, sy):
            _label(console, sx, sy, f"{state.current_star.name} (you)", ui.PLAYER, force=True)

    def label_rank(star):
        return 0 if star.name in targets else 1 if star.name in linked else 2

    for star in sorted(stars, key=label_rank):
        if star is state.current_star:
            continue
        sx, sy = proj[star.name]
        if not view.on_screen(sx, sy):
            continue
        if star.name in targets:
            _label(console, sx, sy, star.name, ui.KEY, force=True)
        elif star.name in linked:
            _label(console, sx, sy, star.name, LINKED_FG)
        elif s <= 1.0:
            _label(console, sx, sy, star.name, NAME_FG)

    # --- stars (priority ones drawn last so they win shared cells) -------------
    def priority(item):
        i, star = item
        return (star.name in targets) + (star.name in linked)

    drawn = []
    for i, star in sorted(enumerate(stars), key=priority):
        sx, sy = proj[star.name]
        if not view.on_screen(sx, sy):
            continue
        base = ui.vivid(STAR_TYPES[star.type]["color"])
        glyph = "☼" if star.name in targets else ("*" if s >= 1.0 else "☼")
        _put(console, sx, sy, glyph, base)
        drawn.append((sx, sy, glyph, base, i))

    # --- current position ----------------------------------------------------
    you = None
    if state.current_star:
        cs = state.current_star
        sx, sy = proj[cs.name]
        if view.on_screen(sx, sy):
            you = (sx, sy, tuple(int(v) for v in console.rgb["bg"][sy, sx]))
            _put(console, sx, sy, "@", ui.PLAYER)
        else:
            # off-screen: arrow on the edge pointing toward home
            cx, cy = max(0, min(width - 1, sx)), max(0, min(height - 2, sy))
            arrow = "◄" if sx < 0 else "►" if sx >= width else "▲" if sy < 0 else "▼"
            _put(console, cx, cy, arrow, ui.PLAYER)

    # --- overlays ----------------------------------------------------------------
    if state.galaxy_minimap and state.galaxy_zoom != len(view.ZOOMS) - 1:
        _draw_minimap(console, stars, targets)
    _draw_zoom_bar(console)


    # keep only the animated cells that the overlays didn't cover
    ch_a, fg_a = console.rgb["ch"], console.rgb["fg"]
    _static["stars"] = [(sx, sy, base, i) for sx, sy, glyph, base, i in drawn
                        if int(ch_a[sy, sx]) == ord(glyph)
                        and tuple(int(v) for v in fg_a[sy, sx]) == tuple(base)
                        and (you is None or (sx, sy) != you[:2])]
    _static["you"] = you if you is not None and int(ch_a[you[1], you[0]]) == ord("@") else None


# ---------------------------------------------------------------------------
# System preview: zoom in past x2 onto a star to see its system map
# ---------------------------------------------------------------------------

PREVIEW_OX, PREVIEW_OY = 5, 6       # system map (0..70 x 0..50) inside the viewport
GATE_FG = (90, 210, 220)


def jumps_between(stars, a, b):
    """Fewest jump-gate hops from system a to system b (None if unreachable)."""
    if a == b:
        return 0
    by_name = {s.name: s for s in stars}
    seen, frontier, hops = {a}, [a], 0
    while frontier:
        hops += 1
        nxt = []
        for name in frontier:
            for jp in by_name[name].system.jump_points:
                d = jp.destination
                if d == b:
                    return hops
                if d not in seen and d in by_name:
                    seen.add(d)
                    nxt.append(d)
        frontier = nxt
    return None


def preview_target(stars):
    """Which star zooming in should open: the scanned one, else the nearest
    to the middle of the screen."""
    if state.look_mode:
        cx, cy = view.project(state.look_x, state.look_y)
        hit = view.star_at_cell(stars, cx, cy)
        if hit is not None:
            return hit
        wx, wy = state.look_x, state.look_y
    else:
        wx, wy = state.galaxy_cam_x, state.galaxy_cam_y
    return min(stars, key=lambda s: (s.x - wx) ** 2 + (s.y - wy) ** 2) if stars else None


def preview_rows(star, stars):
    """(label, value, colour) facts about a previewed system (sidebar / card)."""
    from core.world import FUEL_PRICES
    system = star.system
    here_name = state.current_system.name if state.current_system else None
    here = here_name == star.name
    hops = None if here or not here_name else jumps_between(stars, here_name, star.name)
    markets = sum(1 for loc in [*system.planets, *system.stations] if loc.market)
    fuel = FUEL_PRICES.get(system.archetype)
    contracts = sum(1 for m in state.missions
                    if m.status == "active" and m.dest_system == star.name)
    rows = [
        ("Planets / stations", f"{len(system.planets)} / {len(system.stations)}", ui.TEXT),
        ("Jump gates", str(len(system.jump_points)), ui.TEXT),
        ("Markets", str(markets) if markets else "none", ui.GOOD if markets else ui.FAINT),
        ("Refuel", f"{fuel} cr/unit" if fuel else "unavailable", ui.TEXT if fuel else ui.FAINT),
        ("From you", "you are here" if here else
         (f"{hops} jump{'s' if hops != 1 else ''}" if hops else "no route"),
         ui.PLAYER if here else (ui.ACCENT if hops else ui.BAD)),
    ]
    if contracts:
        rows.append(("Contracts here", str(contracts), ui.KEY))
    return rows


def _draw_preview_card(console, height, star, stars):
    """Info box in the corner - used by the classic UI, which has no sidebar."""
    w = 40
    lines = ui.wrap(star.system.description, w - 4)[:2]
    rows = preview_rows(star, stars)
    h = len(lines) + len(rows) + 4
    x0, y0 = 1, height - h - 2
    bg = (10, 14, 28)
    console.draw_rect(x0 + 1, y0 + 1, w, h, ord(" "), bg=(0, 0, 0))
    ui.frame(console, x0, y0, w, h, star.name, fg=ui.BORDER_HI, bg=bg)
    for i, line in enumerate(lines):
        _text(console, x0 + 2, y0 + 1 + i, line, ui.TEXT, bg)
    for i, (k, v, fg) in enumerate(rows):
        ui.kv(console, x0 + 2, y0 + 2 + len(lines) + i, w - 4, k, v, value_fg=fg, bg=bg)


def draw_preview(console, width, height, star, stars, card=False):
    from render.system import _background
    from effects.effects import get_spin_frame

    t = time.time()
    system = star.system
    ox, oy = PREVIEW_OX, PREVIEW_OY
    here = state.current_system is not None and state.current_system.name == star.name
    here_name = state.current_system.name if state.current_system else None
    if width > 80:                                  # wide (mobile) screens: centre it
        ox = (width - 70) // 2
    ys = [o.y for o in [*system.planets, *system.stations, *system.jump_points]] or [0]
    if here:
        ys.append(state.system_player_y)
    room = height - oy - 2
    ysc = min(1.0, room / max(1, max(ys)))         # squeeze if the screen is short

    def Y(y):
        return int(round(y * ysc))

    from render.system import draw_background
    draw_background(console, system.name, width, height, t)

    # contracts that end in this system
    targets = {m.destination for m in state.missions
               if m.status == "active" and m.dest_system == star.name}

    def label(x, y, text, fg):
        _label(console, x + ox, Y(y) + oy, text, fg, force=True)

    for p in system.planets:
        tag = "  ! contract" if p.name in targets else ""
        label(p.x, p.y, p.name + tag, ui.KEY if tag else (95, 105, 135))
    for st in system.stations:
        tag = "  ! contract" if st.name in targets else ""
        label(st.x, st.y, st.name + tag, ui.KEY if tag else (95, 105, 135))
    for jp in system.jump_points:
        if jp.destination == here_name and not here:
            label(jp.x, jp.y, f"→ {jp.destination} (you arrive here)", ui.PLAYER)
        else:
            label(jp.x, jp.y, f"→ {jp.destination}", (70, 130, 140))

    for p in system.planets:
        _put(console, p.x + ox, Y(p.y) + oy, "○", ui.vivid(p.color))
    for i, st in enumerate(system.stations):
        _put(console, st.x + ox, Y(st.y) + oy, get_spin_frame(t, speed=8.0, phase=3 + i),
             (235, 235, 245))
    for i, jp in enumerate(system.jump_points):
        arrive = jp.destination == here_name and not here
        fg = ui.PLAYER if arrive else twinkle_color(GATE_FG, t, speed=3.0, phase=i)
        _put(console, jp.x + ox, Y(jp.y) + oy, "Θ", fg)
    if here:
        blink = int(t * 2) % 2 == 0
        px, py = state.system_player_x + ox, Y(state.system_player_y) + oy
        _put(console, px, py, "@", (0, 0, 0) if blink else ui.PLAYER, ui.PLAYER if blink else None)

    # --- title banner ------------------------------------------------------
    star_fg = ui.vivid(STAR_TYPES[star.type]["color"])
    console.draw_rect(0, 0, width, 3, ord(" "), bg=(10, 14, 28))
    _text(console, 2, 1, "SYSTEM PREVIEW", ui.DIM, (10, 14, 28))
    _text(console, 18, 1, f"☼ {star.name}", star_fg, (10, 14, 28))
    sub = f"{system.archetype} · {star.type}"
    _text(console, width - 2 - len(sub), 1, sub, ui.DIM, (10, 14, 28))

    if card:
        _draw_preview_card(console, height, star, stars)

    _draw_zoom_bar(console, routes=False)
    hint = "[-] Back  [TAB] Next  [M] Close"
    _text(console, width - len(hint) - 1, height - 1, hint, ui.FAINT)

    state.look_object = star
