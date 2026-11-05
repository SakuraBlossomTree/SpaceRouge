"""The right-hand sidebar: ship status, loan, location, contracts, log, keys.

Drawn on the main console every frame for all in-game screens.
"""

from core import state
from core.world import STAR_TYPES
from render import ui

X = ui.SIDE_X
W = ui.SIDE_W
IX = X + 2            # inner x
IW = W - 4            # inner width

# Screens that take over the whole window (no sidebar)
FULLSCREEN = ("TITLE", "STORY", "GAME_OVER", "VICTORY")


# ---------------------------------------------------------------------------
# Key hints per screen
# ---------------------------------------------------------------------------

HINTS = {
    "SYSTEM": [("←↑↓→", "Fly"), ("TAB", "Autopilot"), ("ENTER", "Dock"), ("X", "Scan"),
               ("M", "Galaxy"), ("I", "Cargo"), ("P", "Contracts"),
               ("L", "Log"), ("E", "Exchange"), ("O", "Radio"), ("J", "Notes"), ("K", "Prices"), ("H", "Help"), ("Q", "Menu")],
    "GALAXY": [("←↑↓→", "Scroll"), ("+/-", "Zoom (x2+ = system)"), ("Z", "Cycle zoom"),
               ("C", "Centre on you"), ("X", "Scan"), ("TAB", "Next star"),
               ("N", "Minimap"), ("R", "Routes"), ("M", "Close")],
    "JUMPPOINT": [("ENTER", "Engage jump"), ("ESC", "Cancel")],
    "LOCATION": [("↑↓", "Select"), ("ENTER", "Open"), ("1-6", "Station shortcuts"),
                 ("TAB", "Next screen"), ("M", "Galaxy"), ("I", "Cargo"), ("ESC", "Undock")],
    "MARKET": [("↑↓", "Select"), ("→/B", "Buy"), ("←/S", "Sell"),
               ("TAB", "Next screen"), ("3", "Missions"), ("5", "Refuel"),
               ("ESC", "Station")],
    "MISSIONS": [("↑↓", "Select"), ("ENTER", "Accept/Deliver"),
                 ("V", "Show on map"), ("TAB", "Next screen"), ("1", "Trade"),
                 ("5", "Refuel"), ("ESC", "Station")],
    "SHIPYARD": [("↑↓", "Select"), ("ENTER", "Buy"), ("TAB", "Next screen"), ("ESC", "Station")],
    "INVENTORY": [("I", "Close"), ("ESC", "Close")],
    "MESSAGES": [("↑↓", "Scroll"), ("L", "Close"), ("ESC", "Close")],
    "MISSION_LOG": [("P", "Close"), ("ESC", "Close")],
    "HELP": [("←→", "Page"), ("H", "Close"), ("ESC", "Close")],
    "EXCHANGE": [("←→", "Tab"), ("↑↓", "Select"), ("E", "Close")],
    "NOTEBOOK": [("ENTER", "New note"), ("R", "Note prices (docked)"), ("↑↓", "Select"),
                 ("DEL", "Delete"), ("J", "Close")],
    "PRICELOG": [("↑↓", "Select"), ("C", "Clear"), ("K", "Close")],
    "RADIO": [("↑↓", "Station"), ("ENTER", "Tune in"), ("←→", "Prev/next"),
              ("TAB", "Mode"), ("+/-", "Volume"), ("X", "On/off"), ("O", "Close")],
    "COMBAT": [("↑↓", "Select"), ("ENTER", "Confirm")],
    "HYPERSPACE": [],
}


def _star_color(star):
    if star is None:
        return ui.TEXT
    return ui.vivid(STAR_TYPES.get(star.type, {}).get("color", ui.TEXT))


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

def _ship_panel(console, y, h):
    ship = state.player_ship
    ui.frame(console, X, y, W, h, "Ship")
    ui.text(console, IX, y + 1, f"{ship.name}", fg=ui.TEXT)
    ui.text(console, IX + len(ship.name) + 1, y + 1, "· light hauler", fg=ui.DIM)
    ui.right(console, IX + IW - 1, y + 1, f"DAY {state.day}", fg=ui.ACCENT)

    from core import audio
    if audio.music_muted():
        ui.right(console, IX + IW - 1, y + 2, "♪ muted", fg=ui.FAINT)
    ui.kv(console, IX, y + 3, IW, "Credits", f"{ui.fmt_int(state.credits)} cr",
          value_fg=ui.KEY)

    ui.meter(console, IX, y + 5, "Hull", ship.hull, ship.max_hull, IW)
    ui.meter(console, IX, y + 8, "Fuel", state.fuel, state.max_fuel, IW,
             fmt="{:.0f}/{:.0f}")
    used = state.inventory.used_space()
    ui.meter(console, IX, y + 11, "Cargo", used, state.inventory.space, IW,
             fg=ui.ACCENT if used < state.inventory.space else ui.WARN)


def _loan_panel(console, y, h):
    ui.frame(console, X, y, W, h, "Loan")
    debt_fg = ui.GOOD if state.debt == 0 else ui.TEXT
    ui.kv(console, IX, y + 1, IW, "Debt", f"{ui.fmt_int(state.debt)} cr",
          value_fg=debt_fg)

    paid = max(0, state.starting_debt - state.debt)
    pct = 100 * paid / state.starting_debt if state.starting_debt else 100
    ui.bar(console, IX, y + 2, IW - 6, paid, state.starting_debt, ui.GOOD)
    ui.right(console, IX + IW - 1, y + 2, f"{pct:4.1f}%", fg=ui.DIM)

    ui.kv(console, IX, y + 3, IW, "Repaid", f"{ui.fmt_int(paid)} cr",
          value_fg=ui.GOOD if paid else ui.DIM)
    if state.debt > 0:
        left = state.loan_deadline_day - state.day
        dfg = ui.BAD if left <= 7 else (ui.WARN if left <= 30 else ui.TEXT)
        ui.kv(console, IX, y + 4, IW, "Deadline",
              f"Day {state.loan_deadline_day} ({max(0, left)}d)", value_fg=dfg)
        ui.text(console, IX, y + 5, ui.clip("Pay at any station (6)", IW), fg=ui.FAINT)
    else:
        ui.text(console, IX, y + 4, "Loan paid off!", fg=ui.GOOD)


def _describe(obj):
    """Short lines describing a planet / station / jump point / star."""
    if obj is None:
        return [("Empty space", ui.DIM)]
    if hasattr(obj, "govement"):        # Planet
        return [
            (f"○ {obj.name}", ui.vivid(getattr(obj, "color", ui.TEXT))),
            (f"Planet · {obj.govement}", ui.DIM),
            ("Market open" if obj.market else "No market",
             ui.GOOD if obj.market else ui.FAINT),
        ]
    if hasattr(obj, "faction"):         # Station
        return [
            (f"■ {obj.name}", ui.TEXT),
            (f"Station · {obj.faction}", ui.DIM),
            ("Market open" if obj.market else "No market",
             ui.GOOD if obj.market else ui.FAINT),
        ]
    if hasattr(obj, "destination"):     # Jump point
        from core import travel
        need = travel.jump_fuel(obj)
        fg = ui.GOOD if state.fuel >= need else ui.BAD
        return [
            (f"Θ Jump gate → {obj.destination}", ui.ACCENT),
            (f"Jump fuel {need}", fg),
        ]
    if hasattr(obj, "system"):          # Star (galaxy)
        lines = [
            (f"☼ {obj.name}", _star_color(obj)),
            (f"{obj.type} · {obj.system.archetype}", ui.DIM),
        ]
        if state.current_system and obj.name in {
            jp.destination for jp in state.current_system.jump_points
        }:
            lines.append(("Direct jump link from here", ui.GOOD))
        if obj is state.current_star:
            lines.append(("You are here", ui.PLAYER))
        if state.mission_nav_target == obj.name:
            lines.append(("Contract destination", ui.KEY))
        return lines
    return [(getattr(obj, "name", "?"), ui.TEXT)]


def _nearest_object():
    system = state.current_system
    if system is None:
        return None, 0
    best, best_d = None, None
    px, py = state.system_player_x, state.system_player_y
    for obj in [*system.planets, *system.stations, *system.jump_points]:
        d = abs(obj.x - px) + abs(obj.y - py)
        if best_d is None or d < best_d:
            best, best_d = obj, d
    return best, best_d or 0


def _location_panel(console, y, h):
    star = state.current_star
    system = state.current_system
    ui.frame(console, X, y, W, h, "Location")
    if system is None:
        ui.text(console, IX, y + 1, "Unknown space", fg=ui.DIM)
        return

    ui.text(console, IX, y + 1, f"☼ {system.name}", fg=_star_color(star))
    sub = f"{system.archetype}"
    if star is not None:
        sub += f" · {star.type}"
    ui.text(console, IX, y + 2, ui.clip(sub, IW), fg=ui.DIM)
    ui.paragraph(console, IX, y + 3, IW, system.description, fg=ui.TEXT,
                 max_lines=2)

    ui.hline(console, X, y + 6, W, fg=ui.BORDER)
    cy = y + 7

    gs = state.game_state
    if gs == "GALAXY" and state.galaxy_preview:
        from render.galaxy import preview_rows
        star = next((s for s in state.stars if s.name == state.galaxy_preview), None)
        if star is not None:
            ui.text(console, IX, cy, "SYSTEM PREVIEW", ui.KEY)
            ui.text(console, IX + 15, cy, ui.clip(star.name, IW - 15), _star_color(star))
            for i, (k, v, fg) in enumerate(preview_rows(star, state.stars)[:6]):
                ui.kv(console, IX, cy + 1 + i, IW, k, v, value_fg=fg)
            return

    if state.look_mode and gs in ("SYSTEM", "GALAXY"):
        ui.text(console, IX, cy, "SCANNER", fg=ui.KEY)
        cy += 1
        for line, fg in _describe(state.look_object):
            ui.text(console, IX, cy, ui.clip(line, IW), fg=fg)
            cy += 1
        if gs == "SYSTEM" and state.look_object is not None and hasattr(state.look_object, "x"):
            from core import travel
            ui.text(console, IX, cy, ui.clip(travel.system_autopilot_line(state.look_object), IW), fg=ui.KEY)
            cy += 1
        return

    if gs in ("LOCATION", "MARKET", "MISSIONS", "SHIPYARD") and state.current_location:
        ui.text(console, IX, cy, "DOCKED AT", fg=ui.GOOD)
        cy += 1
        for line, fg in _describe(state.current_location):
            ui.text(console, IX, cy, ui.clip(line, IW), fg=fg)
            cy += 1
        return

    if gs == "SYSTEM":
        if state.current_object is not None:
            ui.text(console, IX, cy, "IN RANGE", fg=ui.GOOD)
            cy += 1
            for line, fg in _describe(state.current_object):
                ui.text(console, IX, cy, ui.clip(line, IW), fg=fg)
                cy += 1
            ui.key_hint(console, IX, y + h - 2, "ENTER",
                        "Jump menu" if hasattr(state.current_object, "destination") else "Dock")
        else:
            near, dist = _nearest_object()
            ui.text(console, IX, cy, "OPEN SPACE", fg=ui.DIM)
            cy += 1
            if near is not None:
                ui.kv(console, IX, cy, IW, "Nearest",
                      ui.clip(near.name, IW - 10), value_fg=ui.TEXT)
                ui.kv(console, IX, cy + 1, IW, "Distance", f"{dist} units",
                      value_fg=ui.DIM)
        return

    # anything else: show the current star in galaxy terms
    for line, fg in _describe(star)[1:]:
        ui.text(console, IX, cy, ui.clip(line, IW), fg=fg)
        cy += 1

    if gs == "GALAXY":
        ly = y + h - 2
        lx = IX
        for glyph, fg, label in (("@", ui.PLAYER, "you"), ("·", (75, 115, 155), "link"),
                                 ("☼", ui.KEY, "contract")):
            console.print(lx, ly, glyph, fg=fg)
            console.print(lx + 2, ly, label, fg=ui.DIM)
            lx += len(label) + 5


def _missions_panel(console, y, h):
    active = [m for m in state.missions if m.status == "active"]
    ui.frame(console, X, y, W, h, "Contracts",
             right_title=f"{len(active)} active" if active else "")
    if not active:
        ui.text(console, IX, y + 1, "No active contracts.", fg=ui.DIM)
        ui.text(console, IX, y + 2, "Check a Missions Board.", fg=ui.FAINT)
        return
    rows = h - 2
    for i, m in enumerate(active[: rows // 2]):
        here = state.current_system and m.dest_system == state.current_system.name
        ui.text(console, IX, y + 1 + i * 2, ui.clip(f"• {m.title}", IW),
                fg=ui.KEY if here else ui.TEXT)
        ui.text(console, IX + 2, y + 2 + i * 2,
                ui.clip(f"→ {m.destination} ({m.dest_system})", IW - 2),
                fg=ui.GOOD if here else ui.DIM)


def _log_panel(console, y, h):
    ui.frame(console, X, y, W, h, "Comms log")
    rows = h - 2
    lines = []
    for msg in state.messages[-rows:]:
        wrapped = ui.wrap(msg, IW - 2) or [""]
        for j, line in enumerate(wrapped):
            lines.append((("» " if j == 0 else "  ") + line, ui.message_color(msg)))
    lines = lines[-rows:]
    n = len(lines)
    for i, (line, fg) in enumerate(lines):
        # older lines fade out
        age = n - 1 - i
        k = 1.0 if age < 2 else max(0.45, 1.0 - age * 0.08)
        ui.text(console, IX, y + 1 + i, line, fg=ui.scale_color(fg, k))
    if not lines:
        ui.text(console, IX, y + 1, "Silence on all channels.", fg=ui.FAINT)


def _keys_panel(console, y, h):
    ui.frame(console, X, y, W, h, "Controls")
    hints = HINTS.get(state.game_state, [("ESC", "Back")])
    if state.quick_menu:
        hints = [("↑↓", "Select"), ("ENTER", "Go"), ("SPACE", "Close")]
    elif state.game_state not in ("HYPERSPACE", "COMBAT"):
        hints = [("SPACE", "Quick menu")] + list(hints)
    if state.game_state == "GALAXY" and state.galaxy_preview:
        hints = [("-", "Back to chart"), ("TAB", "Next system"), ("←→", "Prev/next"),
                 ("C", "Centre on you"), ("M", "Close")]
    elif state.look_mode and state.game_state in ("SYSTEM", "GALAXY"):
        hints = [("←↑↓→", "Move scanner"), ("ENTER", "Fly there"), ("X", "Stop scan"),
                 ("ESC", "Stop scan")]
        if state.game_state == "GALAXY":
            hints = [("←↑↓→", "Move scanner"), ("TAB", "Next star"), ("+/-", "Zoom"),
                     ("C", "Centre"), ("X/ESC", "Stop scan")]
    if state.game_state == "HYPERSPACE":
        ui.text(console, IX, y + 1, "Jump drive engaged...", fg=ui.ACCENT)
        return
    ui.hint_row(console, IX, y + 1, hints, max_w=IW)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def draw(console, width=None, height=None):
    if state.game_state in FULLSCREEN:
        return
    H = ui.SCREEN_H
    _ship_panel(console, 0, 14)
    _loan_panel(console, 14, 8)
    _location_panel(console, 22, 14)
    _missions_panel(console, 36, 7)
    _keys_panel(console, H - 6, 6)
    _log_panel(console, 43, H - 6 - 43)
