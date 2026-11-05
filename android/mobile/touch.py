"""On-screen touch controls, drawn see-through on top of the game.

    left side    D-pad (hold to repeat, for flying) with OK / Back above it
    right side   icon bar  - Galaxy, Contracts, Cargo, Exchange, Log, Help
                 status    - hull & fuel bars, credits, cargo, day, loan deadline,
                             where you are / what's in range
                 buttons   - whatever the current screen needs (Dock, Buy, ...)
    bottom       new messages pop up briefly

The game itself fills the whole screen underneath. Every button just posts
the key the desktop game expects, so the game logic is unchanged.
Opacity is adjustable on the title screen ("Buttons" button) and saved.
"""

import os
import time

import pygame

import tcod
from core import state, tutorial, fonts
from mobile import icons
from render import ui

K = tcod.event.KeySym

BTN = (22, 32, 56)
BTN_HI = (70, 105, 160)
BTN_BORDER = (80, 110, 160)
PANEL = (8, 12, 24)
TEXT = (225, 232, 245)
DIM = (150, 160, 185)
KEY = (255, 205, 90)
GOOD = (95, 220, 125)
WARN = (240, 195, 70)
BAD = (240, 85, 85)
ACCENT = (90, 210, 220)

REPEAT_DELAY = 0.32
REPEAT_RATE = 0.09
TOAST_SECONDS = 3.5
OPACITY_STEPS = [0.35, 0.55, 0.75, 0.95]

# icon id, label, key, game_state that counts as "open"
ICON_BAR = [
    ("galaxy", "Galaxy", "M", "GALAXY"),
    ("contracts", "Contracts", "P", "MISSION_LOG"),
    ("cargo", "Cargo", "I", "INVENTORY"),
    ("exchange", "Exchange", "E", "EXCHANGE"),
    ("log", "Log", "L", "MESSAGES"),
    ("help", "Help", "H", "HELP"),
]
NO_ICONS = ("TITLE", "STORY", "GAME_OVER", "VICTORY", "HYPERSPACE", "COMBAT")


def _context_buttons():
    """(label, KeySym name) pairs for the current screen."""
    gs = state.game_state
    if gs == "TITLE":
        if state.seed_input is not None:
            return [(str(d), f"N{d}") for d in (1, 2, 3, 4, 5, 6, 7, 8, 9, 0)] + \
                   [("Del", "BACKSPACE"), ("Load", "RETURN"), ("Cancel", "ESCAPE")]
        b = [("Start", "RETURN"), ("Seed", "S")]
        if state.last_seed is not None and state.last_seed != state.galaxy_seed:
            b.append(("Last galaxy", "L"))
        b += [("Tutorial", "T"), ("Music", "F4"), ("Font", "F10"),
              (f"Buttons {round(opacity() * 100)}%", "@OPACITY")]
        return b
    if gs == "STORY":
        return [("Scroll ↑", "UP"), ("Scroll ↓", "DOWN"),
                ("Skip", "SPACE"), ("Next", "RETURN")]
    if gs == "GAME_OVER":
        return [("Quit", "Q")]
    if gs == "VICTORY":
        return [("Keep playing", "RETURN"), ("Quit", "Q")]
    if gs == "LOCATION" and state.debt_input is not None:
        return [(str(d), f"N{d}") for d in (1, 2, 3, 4, 5, 6, 7, 8, 9, 0)] + \
               [("Del", "BACKSPACE"), ("Max", "M"), ("Pay", "RETURN"), ("Cancel", "ESCAPE")]

    tips = []
    if state.tutorial_active and gs not in tutorial.HIDDEN_STATES:
        step = tutorial.current()
        if step and step[2] == "info":
            tips.append(("Next tip", "SPACE"))
        tips.append(("Hide tips", "T"))

    look = state.look_mode and gs in ("SYSTEM", "GALAXY")
    table = {
        "SYSTEM": ([("Stop scan", "X")] if look else [("Dock", "RETURN"), ("Scan", "X")]),
        "GALAXY": [("Back to chart", "MINUS"), ("Next system", "TAB"),
                   ("Prev system", "LEFT"), ("My system", "C")]
                  if state.galaxy_preview else
                  [("Zoom +", "PLUS"), ("Zoom -", "MINUS"), ("Centre", "C"),
                   ("Stop scan" if look else "Scan", "X"), ("Next star", "TAB"),
                   ("Routes", "R"), ("Minimap", "N")],
        "JUMPPOINT": [("Jump", "RETURN"), ("Cancel", "ESCAPE")],
        "LOCATION": [("Open", "RETURN"), ("1 Trade", "N1"), ("2 Shipyard", "N2"),
                     ("3 Missions", "N3"), ("5 Refuel", "N5"), ("6 Pay Debt", "N6"),
                     ("Undock", "ESCAPE")],
        "SHIPYARD": [("Up", "UP"), ("Down", "DOWN"), ("Buy", "RETURN"), ("Back", "ESCAPE")],
        "MARKET": [("Buy", "B"), ("Sell", "S"), ("Back", "ESCAPE")],
        "MISSIONS": [("Accept / Deliver", "RETURN"), ("Show on map", "V"), ("Back", "ESCAPE")],
        "COMBAT": [("Confirm", "RETURN")],
        "EXCHANGE": [("Overview", "N1"), ("Markets", "N2"), ("Goods", "N3"),
                     ("Routes", "N4")],
        "HYPERSPACE": [],
    }
    return table.get(gs, []) + tips


def opacity():
    try:
        v = float(fonts.settings().get("touch_opacity", 0.55))
    except (TypeError, ValueError):
        v = 0.55
    return max(0.2, min(1.0, v))


def _cycle_opacity():
    cur = opacity()
    nxt = next((o for o in OPACITY_STEPS if o > cur + 0.01), OPACITY_STEPS[0])
    fonts.settings()["touch_opacity"] = nxt
    fonts.save_settings()


def _merge(rects):
    """Join overlapping rects, so no screen pixel gets the see-through
    controls blended onto it twice (that would make them look brighter)."""
    out = [pygame.Rect(r) for r in rects if r.width > 0 and r.height > 0]
    merged = True
    while merged:
        merged = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                if out[i].colliderect(out[j]):
                    out[i] = out[i].union(out[j])
                    del out[j]
                    merged = True
                    break
            if merged:
                break
    return out


class Button:
    def __init__(self, rect, label, key, repeat=False, big=False, icon=None, active=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.key = key
        self.repeat = repeat
        self.big = big
        self.icon = icon
        self.active = active


class TouchControls:
    def __init__(self, font_path):
        self.font_path = os.path.abspath(font_path)
        self.enabled = True
        self.dpad = []
        self.icons = []
        self.ctx = []
        self._ctx_key = None
        self.held = {}          # pointer id -> (button, next repeat time)
        self.fonts = {}
        self.overlay = None
        self.right = pygame.Rect(0, 0, 0, 0)
        self.status_rect = pygame.Rect(0, 0, 0, 0)
        self.ctx_area = pygame.Rect(0, 0, 0, 0)
        self._seen_messages = 0
        self._toast = None      # (text, until)
        self._toast_box = None
        self._text_cache = {}
        self._last_sig = None
        self._last_regions = []

    # ---- layout -----------------------------------------------------------

    def _font(self, size):
        size = max(10, int(size))
        if size not in self.fonts:
            try:
                self.fonts[size] = pygame.font.Font(self.font_path, size)
            except Exception:
                self.fonts[size] = pygame.font.Font(None, size)
        return self.fonts[size]

    def layout(self, screen_rect):
        """The game always fills the screen; controls are laid out on top."""
        W, H = screen_rect.size
        self.overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        self._last_sig = None
        self._last_regions = []
        self._text_cache = {}
        self.dpad, self.icons = [], []
        self._ctx_key = None
        if not self.enabled:
            return screen_rect.copy()

        portrait = H > W
        side_l = int(W * (0.36 if portrait else 0.17))
        side_r = int(W * (0.5 if portrait else 0.21))
        pad = max(6, H // 90)

        # --- left: D-pad + OK / Back ---------------------------------------
        if portrait:
            pad_area = pygame.Rect(0, int(H * 0.62), side_l, int(H * 0.38))
        else:
            pad_area = pygame.Rect(0, 0, side_l, H)
        s = int(min(pad_area.width / 3.25, pad_area.height / 5.4))
        cx = pad_area.centerx
        cy = pad_area.bottom - int(s * 1.9)
        g = int(s * 0.08)
        self.dpad = [
            Button((cx - s // 2, cy - s - s // 2 - g, s, s), "▲", "UP", repeat=True),
            Button((cx - s // 2, cy + s // 2 + g, s, s), "▼", "DOWN", repeat=True),
            Button((cx - s - s // 2 - g, cy - s // 2, s, s), "◄", "LEFT", repeat=True),
            Button((cx + s // 2 + g, cy - s // 2, s, s), "►", "RIGHT", repeat=True),
        ]
        bw = int(min(pad_area.width * 0.42, s * 1.5))
        by = cy - s * 2 - int(s * 0.9)
        self.dpad += [
            Button((cx - bw - g, by, bw, int(s * 0.8)), "OK", "RETURN", big=True),
            Button((cx + g, by, bw, int(s * 0.8)), "Back", "ESCAPE", big=True),
        ]

        # --- right: icons, status card, context buttons ----------------------
        if portrait:
            self.right = pygame.Rect(W - side_r, int(H * 0.55), side_r, int(H * 0.45))
        else:
            self.right = pygame.Rect(W - side_r, 0, side_r, H)
        r = self.right
        n = len(ICON_BAR)
        cols = 3                                   # 2 rows of 3: big enough to tap
        rows = (n + cols - 1) // cols
        isz = min((r.width - pad * (cols + 1)) // cols, int(H * 0.115))
        x0 = r.x + (r.width - (cols * isz + (cols - 1) * pad)) // 2
        for i, (icon, label, key, st) in enumerate(ICON_BAR):
            row, col = divmod(i, cols)
            self.icons.append(Button((x0 + col * (isz + pad), r.y + pad + row * (isz + pad), isz, isz),
                                     label, key, icon=icon))
        top = r.y + pad + rows * (isz + pad)
        self.status_rect = pygame.Rect(r.x + pad, top, r.width - 2 * pad, int(H * 0.25))
        self.ctx_area = pygame.Rect(r.x, self.status_rect.bottom + pad, r.width,
                                    r.bottom - self.status_rect.bottom - pad)
        self._pad = pad
        return screen_rect.copy()

    def _layout_context(self):
        labels = _context_buttons()
        in_game = state.game_state not in NO_ICONS
        key = (tuple(labels), in_game)
        if key == self._ctx_key:
            return
        self._ctx_key = key
        # outside the game (title, story...) use the whole right side for buttons
        a = self.ctx_area if in_game else self.right
        self.ctx = []
        if not labels or a.width == 0:
            return
        pad = self._pad
        cols = 1 if len(labels) <= 4 else 2
        if len(labels) > 10:
            cols = 3
        rows = (len(labels) + cols - 1) // cols
        H = self.overlay.get_height() if self.overlay else a.height
        bh = min(int(H * 0.105), (a.height - pad * (rows + 1)) // max(1, rows))
        bw = (a.width - pad * (cols + 1)) // cols
        top = a.y + pad
        for i, (label, k) in enumerate(labels):
            r, c = divmod(i, cols)
            self.ctx.append(Button((a.x + pad + c * (bw + pad), top + r * (bh + pad), bw, bh),
                                   label, k, repeat=k in ("UP", "DOWN")))

    # ---- input --------------------------------------------------------------

    def _buttons(self):
        icons = self.icons if state.game_state not in NO_ICONS else []
        return self.dpad + icons + self.ctx

    def _post(self, button):
        if button.key == "@OPACITY":
            _cycle_opacity()
            self._ctx_key = None
            return
        sym = getattr(K, button.key, None)
        if sym is not None:
            tcod.event.post(tcod.event.KeyDown(sym))

    def press(self, pointer, pos):
        """Returns True if a button took the touch."""
        if not self.enabled:
            return False
        self._layout_context()
        for b in self._buttons():
            if b.rect.collidepoint(pos):
                self._post(b)
                self.held[pointer] = (b, time.monotonic() + REPEAT_DELAY if b.repeat else None)
                return True
        return False

    def release(self, pointer):
        self.held.pop(pointer, None)

    def update(self):
        """Auto-repeat held D-pad buttons; pick up new messages for the pop-up."""
        now = time.monotonic()
        for pid, (b, t) in list(self.held.items()):
            if t is not None and now >= t:
                self._post(b)
                self.held[pid] = (b, now + REPEAT_RATE)
        if len(state.messages) != self._seen_messages:
            if state.messages and len(state.messages) > self._seen_messages:
                self._toast = (state.messages[-1], now + TOAST_SECONDS)
            self._seen_messages = len(state.messages)

    # ---- drawing ------------------------------------------------------------

    def _alpha(self, k=1.0):
        return int(255 * max(0.0, min(1.0, opacity() * k)))

    def _render(self, text, size, colour, alpha=255):
        """font.render is slow on phones: cache every rendered label."""
        key = (text, int(size), tuple(colour), int(alpha))
        img = self._text_cache.get(key)
        if img is None:
            if len(self._text_cache) > 600:
                self._text_cache.clear()
            img = self._font(size).render(text, True, colour)
            if alpha < 255:
                img.set_alpha(alpha)
            self._text_cache[key] = img
        return img

    def _text(self, surf, text, size, colour, center=None, topleft=None, max_w=None, alpha=255):
        size = int(size)
        font = self._font(size)
        while max_w and font.size(text)[0] > max_w and size > 11:
            size -= 1
            font = self._font(size)
        img = self._render(text, size, colour, alpha)
        rect = img.get_rect(center=center) if center else img.get_rect(topleft=topleft)
        surf.blit(img, rect)
        return rect

    def _draw_button(self, surf, b):
        pressed = any(h[0] is b for h in self.held.values())
        fill = BTN_HI if (pressed or b.active) else BTN
        pygame.draw.rect(surf, fill + (self._alpha(0.85),), b.rect, border_radius=12)
        border = KEY if (b.big or b.active) else BTN_BORDER
        pygame.draw.rect(surf, border + (self._alpha(1.2),), b.rect, width=2, border_radius=12)
        ta = self._alpha(1.6)
        if b.icon:
            ic = pygame.Rect(b.rect.x, b.rect.y, b.rect.width, int(b.rect.height * 0.72))
            colour = (KEY if b.active else TEXT) + (ta,)
            if b.icon == "help":
                icons.help(surf, ic, colour, self._font(ic.height * 0.42))
            else:
                icons.ICONS[b.icon](surf, ic, colour)
            self._text(surf, b.label, b.rect.height * 0.17, TEXT,
                       center=(b.rect.centerx, b.rect.bottom - b.rect.height * 0.15),
                       max_w=b.rect.width - 6, alpha=ta)
            return
        H = surf.get_height()
        size = min(b.rect.height * (0.45 if len(b.label) <= 2 else 0.34), H * 0.034)
        if len(b.label) <= 2:
            size = b.rect.height * 0.45            # arrows / digits stay big
        self._text(surf, b.label, size, KEY if b.big else TEXT, center=b.rect.center,
                   max_w=b.rect.width - 12, alpha=ta)

    def _bar(self, surf, rect, value, maximum, colour):
        a = self._alpha(1.3)
        pygame.draw.rect(surf, (40, 48, 70, a), rect, border_radius=4)
        frac = 0 if not maximum else max(0.0, min(1.0, value / maximum))
        if frac > 0:
            fr = pygame.Rect(rect.x, rect.y, max(4, int(rect.width * frac)), rect.height)
            pygame.draw.rect(surf, colour + (min(255, a + 40),), fr, border_radius=4)

    def _status(self, surf):
        """The single status display: hull, fuel, credits, cargo, day / due."""
        r = self.status_rect
        a = self._alpha(1.4)
        pygame.draw.rect(surf, PANEL + (self._alpha(1.1),), r, border_radius=12)
        pygame.draw.rect(surf, BTN_BORDER + (self._alpha(1.2),), r, width=2, border_radius=12)
        x, w = r.x + r.width * 0.06, r.width * 0.88
        line = r.height / 7.2
        fs = line * 0.62
        ship = state.player_ship

        def bar_row(i, label, value, maximum, colour, text):
            y = r.y + line * (0.45 + i * 1.55)
            self._text(surf, label, fs, DIM, topleft=(x, y), alpha=a)
            t = self._render(text, fs, colour, a)
            surf.blit(t, (x + w - t.get_width(), y))
            self._bar(surf, pygame.Rect(int(x), int(y + line * 0.8), int(w), max(5, int(line * 0.42))),
                      value, maximum, colour)

        def ratio_colour(v, m):
            f = 0 if not m else v / m
            return GOOD if f > 0.5 else WARN if f > 0.25 else BAD

        bar_row(0, "HULL", ship.hull, ship.max_hull, ratio_colour(ship.hull, ship.max_hull),
                f"{ship.hull}/{ship.max_hull}")
        bar_row(1, "FUEL", state.fuel, state.max_fuel, ratio_colour(state.fuel, state.max_fuel),
                f"{state.fuel:.0f}/{state.max_fuel:.0f}")

        y = r.y + line * 3.7
        self._text(surf, f"{state.credits:,} cr", fs * 1.1, KEY, topleft=(x, y), alpha=a)
        used, cap = state.inventory.used_space(), state.inventory.space
        t = self._render(f"Cargo {used}/{cap}", fs, ACCENT if used < cap else WARN, a)
        surf.blit(t, (x + w - t.get_width(), y))

        y = r.y + line * 4.85
        days = state.loan_deadline_day - state.day
        due_c = BAD if days <= 7 else WARN if days <= 30 else DIM
        self._text(surf, f"Day {state.day}", fs, DIM, topleft=(x, y), alpha=a)
        t = self._render(f"Debt {state.debt:,} · {max(0, days)}d left", fs, due_c, a)
        surf.blit(t, (x + w - t.get_width(), y))

        y = r.y + line * 6.0
        where = state.current_system.name if state.current_system else ""
        if state.game_state in ("LOCATION", "MARKET", "MISSIONS") and state.current_location:
            where += f" · docked: {state.current_location.name}"
        elif state.game_state == "SYSTEM" and state.current_object is not None:
            where += f" · {state.current_object.name} in range"
        self._text(surf, where, fs * 0.95, ACCENT, topleft=(x, y), max_w=w, alpha=a)

    def _draw_toast(self, surf):
        if not self._toast:
            return
        text, until = self._toast
        left = until - time.monotonic()
        if left <= 0:
            self._toast = None
            return
        fade = min(1.0, left / 0.6)
        W, H = surf.get_size()
        fade = round(fade, 1)
        img = self._render(text if len(text) < 90 else text[:87] + "...", H * 0.028,
                           ui.message_color(text), int(255 * fade))
        box = img.get_rect(midbottom=(W // 2, H - H * 0.03)).inflate(H * 0.04, H * 0.02)
        pygame.draw.rect(surf, PANEL + (int(220 * fade),), box, border_radius=10)
        pygame.draw.rect(surf, BTN_BORDER + (int(255 * fade),), box, width=2, border_radius=10)
        surf.blit(img, img.get_rect(center=box.center))
        self._toast_box = box.inflate(4, 4)

    def _signature(self):
        """What the overlay shows, in four parts, so a change to one part only
        redraws that part: (layout, pressed buttons, ship stats, pop-up)."""
        ship = state.player_ship
        toast = None
        if self._toast:
            left = self._toast[1] - time.monotonic()
            toast = (self._toast[0], round(min(1.0, max(0.0, left / 0.6)), 1)) if left > 0 else None
        where = (state.current_system.name if state.current_system else None,
                 getattr(state.current_object, "name", None),
                 getattr(state.current_location, "name", None))
        layout = (self._ctx_key, state.game_state, round(opacity(), 2))
        held = tuple(sorted(id(h[0]) for h in self.held.values()))
        stats = (ship.hull, int(state.fuel), state.credits, state.inventory.used_space(),
                 state.day, state.loan_deadline_day, state.debt, where)
        return (layout, held, stats, toast)

    def dirty(self):
        """True if the controls need redrawing (cheap check)."""
        if not self.enabled or self.overlay is None:
            return False
        self._layout_context()
        return self._signature() != self._last_sig

    def draw(self, screen, dirty=None, backdrop=None, offset=(0, 0)):
        """Draw the controls over the game. Returns the screen regions updated.

        dirty: game regions changed this frame. Only overlay regions that
        overlap them need to be redrawn; if None, redraw every control.
        backdrop/offset: the game canvas and its screen position. Restoring
        it under each overlay region erases controls that disappeared
        (e.g. an expired toast) instead of leaving ghost pixels behind.
        """
        if not self.enabled or self.overlay is None:
            return []
        self._layout_context()
        sig = self._signature()
        last = self._last_sig
        surf = self.overlay
        in_game = state.game_state not in NO_ICONS
        changed = last is None or sig[0] != last[0]
        if changed:
            self._last_sig = sig
            surf.fill((0, 0, 0, 0))
            for b in self.icons:
                b.active = any(st == state.game_state for _, _, k, st in ICON_BAR if k == b.key)
            for b in self.dpad + (self.icons if in_game else []) + self.ctx:
                self._draw_button(surf, b)
            if in_game:
                self._status(surf)
            self._toast_box = None
            self._draw_toast(surf)
        elif sig != last:
            # Only part of the controls changed: redraw just that part.
            self._last_sig = sig
            areas = []
            if sig[1] != last[1]:
                flipped = set(sig[1]) ^ set(last[1])
                for b in self.dpad + (self.icons if in_game else []) + self.ctx:
                    if id(b) in flipped:
                        r = b.rect.inflate(6, 6).clip(surf.get_rect())
                        surf.fill((0, 0, 0, 0), r)
                        self._draw_button(surf, b)
                        areas.append(r)
            if sig[2] != last[2] and in_game:
                r = self.status_rect.inflate(6, 6).clip(surf.get_rect())
                surf.fill((0, 0, 0, 0), r)
                self._status(surf)
                areas.append(r)
            if sig[3] != last[3]:
                if self._toast_box is not None:
                    r = self._toast_box.inflate(4, 4).clip(surf.get_rect())
                    surf.fill((0, 0, 0, 0), r)
                    areas.append(r)
                self._toast_box = None
                self._draw_toast(surf)
                if self._toast_box is not None:
                    areas.append(self._toast_box.inflate(4, 4).clip(surf.get_rect()))
            out = self._blend_dirty(screen, dirty) if dirty else []
            areas = _merge(areas)
            self._restore(screen, areas, backdrop, offset)
            for r in areas:
                screen.blit(surf, r, area=r)
            self._last_regions = self._regions()
            return out + areas

        regions = self._regions()
        if changed or dirty is None:
            # Controls changed (or a full redraw): put the game back under
            # every old and new control area, then draw the controls once.
            restore = _merge(self._last_regions + regions)
            self._restore(screen, restore, backdrop, offset)
            for r in restore:
                screen.blit(self.overlay, r, area=r)
            self._last_regions = regions
            return restore
        return self._blend_dirty(screen, dirty)

    def _restore(self, screen, rects, backdrop, offset):
        """Copy the plain game picture back into `rects` (erases old controls)."""
        if backdrop is None:
            return
        dx, dy = offset
        game = pygame.Rect(dx, dy, backdrop.get_width(), backdrop.get_height())
        for r in rects:
            screen.fill((6, 8, 16), r)
            src = r.clip(game)
            if src.width and src.height:
                screen.blit(backdrop, src.topleft, area=src.move(-dx, -dy))

    def _blend_dirty(self, screen, dirty):
        """The presenter has just copied fresh game pixels into the `dirty`
        rects, wiping the controls there. Re-draw the controls ONLY in those
        small overlaps. (Blending see-through pixels is slow on phone chips,
        so never redo whole panels because one star twinkled.)"""
        out = []
        overlay = self.overlay
        for r in _merge(self._last_regions):
            for i in r.collidelistall(dirty):
                part = r.clip(dirty[i])
                screen.blit(overlay, part, area=part)
                out.append(part)
        return out

    def _regions(self):
        """Tight screen areas that hold controls (one per button/card)."""
        regs = [b.rect.inflate(6, 6) for b in self.dpad]
        if state.game_state not in NO_ICONS:
            regs += [b.rect.inflate(6, 6) for b in self.icons]
            regs.append(self.status_rect.inflate(6, 6))
        regs += [b.rect.inflate(6, 6) for b in self.ctx]
        if self._toast_box is not None:
            regs.append(self._toast_box.inflate(4, 4))
        sr = self.overlay.get_rect()
        return [r.clip(sr) for r in regs]
