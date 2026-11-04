# effects/combat_effects.py
"""Visual effects for the combat screen.

This module is intentionally renderer-only. It reads abstract events
emitted by core.combat.CombatManager and turns them into temporary
animations: lunges, projectiles, shields, escape burn, floating damage.
"""

import math
import random


PLAYER_FG = (110, 220, 255)
ENEMY_FG = (255, 110, 110)
DAMAGE_FG = (255, 80, 80)
SHIELD_FG = (120, 180, 255)
ESCAPE_FG = (255, 220, 90)
EXPLOSION_FG = (255, 190, 80)


# Simple ASCII ships.
# Enemy is drawn at the top, player at the bottom.
PLAYER_SPRITE = [
    "  /\\  ",
    " /  \\ ",
    "| == |",
    " \\  / ",
    "  \\/  ",
]

ENEMY_SPRITE = [
    "  /\\  ",
    " /  \\ ",
    "| XX |",
    " /  \\ ",
    "  /\\  ",
]


def get_combat_layout(width, height):
    """
    Central place for combat-screen layout values used by both
    render/combat.py and the effect system.
    """
    action_row = max(18, height - 8)
    player_ship_y = max(11, action_row - 7)
    log_row = max(8, player_ship_y - 6)
    ship_x = max(18, width // 2 - 3)

    return {
        "width": width,
        "height": height,

        "title_y": 1,
        "stats_row": 3,

        "player_col": 4,
        "enemy_col": max(44, width - 36),

        "log_row": log_row,
        "action_row": action_row,

        # Ships
        "enemy_ship_x": ship_x,
        "enemy_ship_y": 3,
        "player_ship_x": ship_x,
        "player_ship_y": player_ship_y,

        # Top-right floating enemy damage text.
        "enemy_damage_x": max(2, width - 22),
        "enemy_damage_y": 2,
    }


class Effect:
    """Base class for all temporary visual effects."""

    def __init__(self, lifetime=0.5, delay=0.0):
        self.lifetime = lifetime
        self.delay = delay
        self.elapsed = 0.0

    @property
    def done(self):
        return self.delay <= 0.0 and self.elapsed >= self.lifetime

    def update(self, dt):
        if self.delay > 0.0:
            self.delay = max(0.0, self.delay - dt)
            return
        self.elapsed += dt

    def draw(self, console):
        pass


class FloatText(Effect):
    """Floating combat text."""

    def __init__(
        self,
        x,
        y,
        text,
        fg=(255, 255, 255),
        lifetime=0.8,
        rise=2,
        delay=0.0,
    ):
        super().__init__(lifetime=lifetime, delay=delay)
        self.x = x
        self.y = y
        self.text = text
        self.fg = fg
        self.rise = rise

    def draw(self, console):
        if self.delay > 0.0:
            return

        progress = min(1.0, self.elapsed / max(0.001, self.lifetime))
        y = int(self.y - (progress * self.rise))
        console.print(int(self.x), y, self.text, fg=self.fg)


class Projectile(Effect):
    """Simple moving projectile between two points."""

    def __init__(
        self,
        sx,
        sy,
        tx,
        ty,
        char="*",
        impact_char="*",
        fg=(255, 220, 120),
        lifetime=0.28,
        delay=0.0,
    ):
        super().__init__(lifetime=lifetime, delay=delay)
        self.sx = sx
        self.sy = sy
        self.tx = tx
        self.ty = ty
        self.char = char
        self.impact_char = impact_char
        self.fg = fg

    def draw(self, console):
        if self.delay > 0.0:
            return

        progress = min(1.0, self.elapsed / max(0.001, self.lifetime))
        x = self.sx + (self.tx - self.sx) * progress
        y = self.sy + (self.ty - self.sy) * progress

        if progress < 1.0:
            console.print(int(x), int(y), self.char, fg=self.fg)
        else:
            console.print(int(self.tx), int(self.ty), self.impact_char, fg=self.fg)


class Burst(Effect):
    """Small particle burst for hits and explosions."""

    def __init__(
        self,
        x,
        y,
        chars="*+#.",
        fg=(255, 180, 80),
        lifetime=0.45,
        count=10,
        radius=3,
        delay=0.0,
    ):
        super().__init__(lifetime=lifetime, delay=delay)
        self.x = x
        self.y = y
        self.fg = fg
        self.particles = []

        for _ in range(count):
            angle = random.uniform(0.0, math.pi * 2.0)
            speed = random.uniform(0.5, float(radius))
            ch = random.choice(chars)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed * 0.6
            self.particles.append((dx, dy, ch))

    def draw(self, console):
        if self.delay > 0.0:
            return

        progress = min(1.0, self.elapsed / max(0.001, self.lifetime))
        for dx, dy, ch in self.particles:
            x = int(self.x + dx * progress)
            y = int(self.y + dy * progress)
            console.print(x, y, ch, fg=self.fg)


class DelayedCallback(Effect):
    """Utility effect to trigger something after a delay."""

    def __init__(self, delay, callback):
        super().__init__(lifetime=0.01, delay=delay)
        self.callback = callback
        self.called = False

    def update(self, dt):
        super().update(dt)
        if self.delay <= 0.0 and not self.called:
            self.callback()
            self.called = True


class CombatEffectManager:
    """
    Owns all transient combat visuals.

    This class does not change game logic. It only reacts to events
    emitted by CombatManager and animates the combat screen.
    """

    PLAYER_LUNGE_TIME = 0.26
    ENEMY_LUNGE_TIME = 0.26
    SHIELD_TIME = 1.45
    ESCAPE_TIME = 1.0

    def __init__(self):
        self.reset()

    def reset(self):
        self.effects = []

        self.player_lunge = 0.0
        self.enemy_lunge = 0.0

        self.player_shield = 0.0
        self.player_escape = 0.0
        self.player_shake = 0.0

        self.player_flash = 0.0
        self.enemy_flash = 0.0

        self.player_dying = 0.0
        self.enemy_dying = 0.0
        self.player_destroyed = 0.0
        self.enemy_destroyed = 0.0

        self.player_dx = 0
        self.player_dy = 0
        self.enemy_dx = 0
        self.enemy_dy = 0

    def handle_event(self, event, layout):
        """
        Convert a core combat event into visual effects.
        """
        etype = event.get("type")

        # Sprite centers.
        px = layout["player_ship_x"] + 3
        py = layout["player_ship_y"] + 2
        ex = layout["enemy_ship_x"] + 3
        ey = layout["enemy_ship_y"] + 2

        # Top-right screen position for enemy damage.
        top_x = layout["enemy_damage_x"]
        top_y = layout["enemy_damage_y"]

        if etype == "player_attack":
            self.player_lunge = self.PLAYER_LUNGE_TIME
            self.effects.append(
                Projectile(
                    sx=px,
                    sy=py - 1,
                    tx=ex,
                    ty=ey + 1,
                    char="^",
                    impact_char="*",
                    fg=PLAYER_FG,
                    lifetime=0.24,
                )
            )

        elif etype == "enemy_damaged":
            amount = event.get("amount", 0)
            delay = 0.16

            # Flash enemy sprite.
            self.effects.append(
                DelayedCallback(delay, lambda: setattr(self, "enemy_flash", 0.20))
            )

            # Top-right damage text, as requested.
            self.effects.append(
                FloatText(
                    top_x,
                    top_y + random.randint(0, 1),
                    f"ENEMY -{amount}",
                    fg=DAMAGE_FG,
                    lifetime=0.95,
                    rise=1,
                    delay=delay,
                )
            )

            # Also show a smaller damage number near the enemy ship.
            self.effects.append(
                FloatText(
                    ex + 2,
                    ey - 1,
                    f"-{amount}",
                    fg=DAMAGE_FG,
                    lifetime=0.75,
                    rise=1,
                    delay=delay,
                )
            )

            # Small hit burst.
            self.effects.append(
                Burst(
                    ex,
                    ey,
                    count=7,
                    radius=2,
                    lifetime=0.35,
                    delay=delay,
                )
            )

        elif etype == "player_defend":
            self.player_shield = self.SHIELD_TIME
            self.effects.append(
                FloatText(
                    px - 2,
                    py - 2,
                    "DEFEND",
                    fg=SHIELD_FG,
                    lifetime=0.75,
                    rise=1,
                )
            )

        elif etype == "player_escape":
            self.player_shake = 0.35
            self.effects.append(
                FloatText(
                    px - 2,
                    py - 2,
                    "BURN",
                    fg=ESCAPE_FG,
                    lifetime=0.7,
                    rise=1,
                )
            )

        elif etype == "escape_success":
            self.player_escape = self.ESCAPE_TIME
            self.effects.append(
                FloatText(
                    px - 3,
                    py - 2,
                    "ESCAPED!",
                    fg=ESCAPE_FG,
                    lifetime=1.0,
                    rise=2,
                    delay=0.2,
                )
            )

        elif etype == "escape_fail":
            self.effects.append(
                FloatText(
                    px - 3,
                    py - 2,
                    "BLOCKED!",
                    fg=DAMAGE_FG,
                    lifetime=0.8,
                    rise=1,
                    delay=0.2,
                )
            )

        elif etype == "enemy_attack":
            # Delay enemy response slightly so the player attack reads clearly.
            delay = 0.48

            self.effects.append(
                DelayedCallback(
                    delay,
                    lambda: setattr(self, "enemy_lunge", self.ENEMY_LUNGE_TIME),
                )
            )

            self.effects.append(
                Projectile(
                    sx=ex,
                    sy=ey + 1,
                    tx=px,
                    ty=py - 1,
                    char="v",
                    impact_char="*",
                    fg=ENEMY_FG,
                    lifetime=0.24,
                    delay=delay,
                )
            )

        elif etype == "player_damaged":
            amount = event.get("amount", 0)
            delay = 0.68

            self.effects.append(
                DelayedCallback(delay, lambda: setattr(self, "player_flash", 0.20))
            )

            self.effects.append(
                FloatText(
                    px + 2,
                    py - 1,
                    f"-{amount}",
                    fg=DAMAGE_FG,
                    lifetime=0.8,
                    rise=1,
                    delay=delay,
                )
            )

        elif etype == "enemy_destroyed":
            self.enemy_dying = 1.0
            delay = 0.28

            self.effects.append(
                DelayedCallback(delay, lambda: setattr(self, "enemy_destroyed", 0.8))
            )

            self.effects.append(
                Burst(
                    ex,
                    ey,
                    count=16,
                    radius=4,
                    lifetime=0.65,
                    delay=delay,
                    fg=EXPLOSION_FG,
                )
            )

            self.effects.append(
                FloatText(
                    ex - 2,
                    ey,
                    "BOOM",
                    fg=EXPLOSION_FG,
                    lifetime=0.8,
                    rise=1,
                    delay=delay,
                )
            )

            self.effects.append(
                FloatText(
                    top_x,
                    top_y,
                    "DESTROYED",
                    fg=EXPLOSION_FG,
                    lifetime=1.0,
                    rise=1,
                    delay=delay,
                )
            )

        elif etype == "player_destroyed":
            self.player_dying = 1.0
            delay = 0.28

            self.effects.append(
                DelayedCallback(delay, lambda: setattr(self, "player_destroyed", 0.8))
            )

            self.effects.append(
                Burst(
                    px,
                    py,
                    count=16,
                    radius=4,
                    lifetime=0.65,
                    delay=delay,
                    fg=(255, 130, 70),
                )
            )

            self.effects.append(
                FloatText(
                    px - 2,
                    py,
                    "BOOM",
                    fg=(255, 130, 70),
                    lifetime=0.8,
                    rise=1,
                    delay=delay,
                )
            )

    def update(self, dt):
        """
        Advance all effects and animation timers.
        """
        dt = max(0.0, min(0.1, float(dt)))

        for effect in self.effects:
            effect.update(dt)

        self.effects = [effect for effect in self.effects if not effect.done]

        self.player_lunge = max(0.0, self.player_lunge - dt)
        self.enemy_lunge = max(0.0, self.enemy_lunge - dt)
        self.player_shield = max(0.0, self.player_shield - dt)
        self.player_escape = max(0.0, self.player_escape - dt)
        self.player_shake = max(0.0, self.player_shake - dt)
        self.player_flash = max(0.0, self.player_flash - dt)
        self.enemy_flash = max(0.0, self.enemy_flash - dt)
        self.player_dying = max(0.0, self.player_dying - dt)
        self.enemy_dying = max(0.0, self.enemy_dying - dt)
        self.player_destroyed = max(0.0, self.player_destroyed - dt)
        self.enemy_destroyed = max(0.0, self.enemy_destroyed - dt)

        # Reset offsets.
        self.player_dx = 0
        self.player_dy = 0
        self.enemy_dx = 0
        self.enemy_dy = 0

        # Player attack lunge upward.
        if self.player_lunge > 0.0:
            progress = 1.0 - (self.player_lunge / self.PLAYER_LUNGE_TIME)
            self.player_dy = -int(math.sin(progress * math.pi) * 3)

        # Enemy attack lunge downward.
        if self.enemy_lunge > 0.0:
            progress = 1.0 - (self.enemy_lunge / self.ENEMY_LUNGE_TIME)
            self.enemy_dy = int(math.sin(progress * math.pi) * 2)

        # Escape animation: ship drops downward.
        if self.player_escape > 0.0:
            progress = 1.0 - (self.player_escape / self.ESCAPE_TIME)
            self.player_dy += int(progress * 6)

        # Escape shake.
        if self.player_shake > 0.0:
            self.player_dx += random.choice((-1, 0, 1))

    def draw_ships(self, console, layout, combat=None):
        """
        Draw enemy ship at top and player ship at bottom.
        """
        ex = int(layout["enemy_ship_x"] + self.enemy_dx)
        ey = int(layout["enemy_ship_y"] + self.enemy_dy)
        px = int(layout["player_ship_x"] + self.player_dx)
        py = int(layout["player_ship_y"] + self.player_dy)

        # Enemy ship
        enemy_alive = combat.enemy.is_alive() if combat else True
        if enemy_alive or self.enemy_dying > 0.0 or self.enemy_destroyed > 0.0:
            if self.enemy_destroyed > 0.0:
                console.print(ex, ey + 1, "*BOOM*", fg=EXPLOSION_FG)
            else:
                self._draw_sprite(
                    console,
                    ex,
                    ey,
                    ENEMY_SPRITE,
                    ENEMY_FG,
                    self.enemy_flash > 0.0,
                )

        # Player ship
        player_alive = combat.player.is_alive() if combat else True
        if player_alive or self.player_dying > 0.0 or self.player_destroyed > 0.0:
            if self.player_destroyed > 0.0:
                console.print(px, py + 1, "*BOOM*", fg=(255, 150, 80))
            else:
                player_color = (120, 120, 120) if self.player_escape > 0.0 else PLAYER_FG
                self._draw_sprite(
                    console,
                    px,
                    py,
                    PLAYER_SPRITE,
                    player_color,
                    self.player_flash > 0.0,
                )

            if self.player_shield > 0.0:
                console.print(px - 2, py + len(PLAYER_SPRITE), "(( SHIELD ))", fg=SHIELD_FG)

    def draw_effects(self, console):
        """
        Draw all active temporary effects.
        """
        for effect in self.effects:
            effect.draw(console)

    def _draw_sprite(self, console, x, y, sprite, fg, flash=False):
        color = (255, 255, 255) if flash else fg
        for i, line in enumerate(sprite):
            console.print(int(x), int(y + i), line, fg=color)