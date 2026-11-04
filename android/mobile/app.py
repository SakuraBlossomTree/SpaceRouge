"""SpaceRouge mobile: the pygame main loop.

Same game as the desktop version (core/ + render/ are shared code), drawn
with pygame and playable by touch, keyboard or both.

    python main.py              desktop window with the touch panels
    python main.py --keyboard   desktop window, no touch panels
    python main.py --seed 123   start in a specific galaxy
"""

import os
import sys
import time

import pygame

import tcod
from core import state, audio, fonts, tutorial, newgame
from core.events import handle_event, update_hyperspace
from render import story, ui
from mobile.screen import compose, configure as configure_screen, view as map_view
from mobile.presenter import Presenter
from mobile.touch import TouchControls
from mobile import keys
from mobile.fpsmeter import FpsMeter

ON_ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ
FPS = 60                 # loop cap (was 30) - for testing
FAST_STATES = ("HYPERSPACE", "COMBAT", "STORY", "TITLE")
MUSIC_FOLDER = "sfx/music"
TITLE_TRACK = "sfx/music/MyVeryOwnDeadShip.ogg"
# absolute: on Android, SDL looks up relative paths in the APK assets, not cwd
UI_FONT = os.path.abspath("assets/fonts/DejaVuSansMono.ttf")


class Window:
    """What core/events.py expects as context.sdl_window."""

    @property
    def fullscreen(self):
        surf = pygame.display.get_surface()
        return bool(surf and surf.get_flags() & pygame.FULLSCREEN)

    @fullscreen.setter
    def fullscreen(self, value):
        if value != self.fullscreen and not ON_ANDROID:
            pygame.display.toggle_fullscreen()


class Context:
    """Stands in for tcod's context: fullscreen toggle + font changes."""

    def __init__(self, app):
        self.app = app
        self.sdl_window = Window()

    def change_tileset(self, tileset):
        self.app.set_font_family(tileset.family or "sans")


def remove_presplash():
    """Android: hide the startup splash image once the game has drawn a frame.

    Kivy apps do this automatically; a pygame app has to ask, otherwise the
    splash can stay on top of the game."""
    if not ON_ANDROID:
        return
    try:
        import android
        android.remove_presplash()
    except Exception as exc:
        print(f"[android] could not remove presplash: {exc}")


def update_music():
    gs = state.game_state
    if gs == "TITLE":
        audio.ensure_music(TITLE_TRACK)
    elif gs == "STORY":
        if audio.current_music_path:
            audio.stop_music()
    else:
        audio.ensure_playlist(MUSIC_FOLDER, exclude=[TITLE_TRACK])
    audio.update()


def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class App:
    def __init__(self):
        pygame.init()
        try:
            pygame.mixer.pre_init(44100, -16, 2, 1024)
        except Exception:
            pass
        pygame.display.set_caption("SpaceRouge")
        if ON_ANDROID:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)

        self.console = None                 # sized to the screen in relayout()
        family = fonts.FONTS[fonts.current_index()][1]
        self.presenter = Presenter(family)
        self.touch = TouchControls(UI_FONT)
        self.touch.enabled = "--keyboard" not in sys.argv
        self.context = Context(self)
        self.paused = False
        self._force = True
        self._full_redraw = True
        self._last_compose = 0.0
        self.relayout()
        self.fps = FpsMeter(UI_FONT, self.screen.get_height())

        self._splash("Charting the galaxy...")
        remove_presplash()
        state.story_texts = [load_text("story1.txt"), load_text("story2.txt")]
        self.title_text = load_text("title.txt")
        newgame.startup()
        state.last_story_time = time.time()

    # ---- layout --------------------------------------------------------------

    def relayout(self):
        """The game fills the screen; the console size follows the screen."""
        rect = self.screen.get_rect()
        self.game_rect = self.touch.layout(rect)
        self._use_size(*self.presenter.layout(self.game_rect))
        self._force = True
        self._full_redraw = True

    def _use_size(self, cols, rows):
        if self.console is None or (self.console.width, self.console.height) != (cols, rows):
            self.console = tcod.console.Console(cols, rows)
            configure_screen(cols, rows)

    def set_font_family(self, family):
        self._use_size(*self.presenter.set_family(family, self.game_rect))
        self._force = True
        self._full_redraw = True

    def _splash(self, text):
        self.screen.fill((6, 8, 16))
        font = pygame.font.Font(UI_FONT, max(16, self.screen.get_height() // 24))
        surf = font.render(text, True, (120, 205, 255))
        self.screen.blit(surf, surf.get_rect(center=self.screen.get_rect().center))
        pygame.display.flip()

    # ---- input ---------------------------------------------------------------

    def _pointer_down(self, pid, pos):
        if self.touch.press(pid, pos):
            return
        # a tap on the console itself: tap the map to fly toward it
        cell = self.presenter.cell_at(pos)
        if cell and state.game_state == "SYSTEM" and not state.look_mode:
            mx, my = cell[0] - map_view["ox"], cell[1] - map_view["oy"]
            if 0 <= mx < 80 and 0 <= my < 60:
                dx = mx - state.system_player_x
                dy = my - state.system_player_y
                if dx or dy:
                    if abs(dx) >= abs(dy):
                        sym = tcod.event.KeySym.RIGHT if dx > 0 else tcod.event.KeySym.LEFT
                    else:
                        sym = tcod.event.KeySym.DOWN if dy > 0 else tcod.event.KeySym.UP
                    tcod.event.post(tcod.event.KeyDown(sym))

    def pump(self):
        W, H = self.screen.get_size()
        for ev in pygame.event.get():
            t = ev.type
            if t == pygame.QUIT:
                tcod.event.post(tcod.event.Quit())
            elif t == pygame.KEYDOWN:
                k = keys.translate(ev)
                if k is not None:
                    tcod.event.post(k)
            elif t == pygame.MOUSEWHEEL:
                tcod.event.post(tcod.event.MouseWheel(ev.x, ev.y))
            elif t == pygame.FINGERDOWN:
                self._pointer_down(("f", ev.finger_id), (ev.x * W, ev.y * H))
            elif t == pygame.FINGERUP:
                self.touch.release(("f", ev.finger_id))
            elif t == pygame.MOUSEBUTTONDOWN and ev.button == 1 and not getattr(ev, "touch", False):
                self._pointer_down("mouse", ev.pos)
            elif t == pygame.MOUSEBUTTONUP and ev.button == 1 and not getattr(ev, "touch", False):
                self.touch.release("mouse")
            elif t in (pygame.VIDEORESIZE, getattr(pygame, "WINDOWSIZECHANGED", -1)):
                if not ON_ANDROID and t == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(ev.size, pygame.RESIZABLE)
                self.relayout()
            elif t == getattr(pygame, "APP_DIDENTERBACKGROUND", -1):
                self.paused = True
                audio.pause_all()
            elif t == getattr(pygame, "APP_DIDENTERFOREGROUND", -1):
                self.paused = False
                audio.resume_all()
                self.relayout()
        self.touch.update()

    # ---- main loop -------------------------------------------------------------

    def frame(self):
        story_text = (state.story_texts[state.story_index]
                      if state.story_index < len(state.story_texts) else "")
        if state.game_state == "STORY":
            story.update(story_text)
        elif state.game_state == "HYPERSPACE":
            update_hyperspace()
        tutorial.update()
        update_music()

        # Only rebuild the picture when needed: right after input, or at the
        # animation rate (15 fps for twinkling stars; 30 for fast effects).
        now = time.monotonic()
        self.fps.start()
        anim = 1 / 60 if state.game_state in FAST_STATES else 1 / 15
        canvas_changed = False
        if self._force or tcod.event.pending() or now - self._last_compose >= anim:
            compose(self.console, state.stars, self.title_text, story_text)
            self.fps.lap("build")
            canvas_changed = self.presenter.render(self.console)
            self.fps.lap("cells")
            self._last_compose = now
            self._force = False

        # Only send changed regions to the screen. This avoids copying the
        # whole 1080p+ surface on every animation frame on Android.
        need_touch = self.touch.dirty()
        if canvas_changed or self._full_redraw or need_touch:
            rects = []
            full = self._full_redraw
            if full:
                self.screen.fill((6, 8, 16))
                self._full_redraw = False
                self.presenter.present_all(self.screen)
                rects.append(self.screen.get_rect())
            elif canvas_changed:
                rects.extend(self.presenter.present(self.screen))
            if need_touch or rects:
                rects.extend(self.touch.draw(
                    self.screen, None if full else rects,
                    backdrop=self.presenter.canvas,
                    offset=self.presenter.dest.topleft))
            rects.extend(self.fps.draw(self.screen, rects))
            if rects:
                pygame.display.update(rects)
            self.fps.lap("show")
            self.fps.end(True)
        else:
            extra = self.fps.draw(self.screen, [])
            if extra:
                pygame.display.update(extra)
            self.fps.end(False)

        events = tcod.event.get()
        if events:
            self._force = True
        for event in events:
            if isinstance(event, tcod.event.Quit):
                raise SystemExit()
            if (state.game_state == "STORY"
                    and isinstance(event, tcod.event.KeyDown)
                    and event.sym == tcod.event.KeySym.RETURN
                    and state.story_char_index >= len(story_text)
                    and state.current_star is None
                    and state.story_index >= len(state.story_texts) - 1):
                for star in state.stars:
                    if star.name == "Sol":
                        state.current_star = star
                        state.current_system = star.system
                        break
            handle_event(event, story_text, self.context)

    def run(self):
        clock = pygame.time.Clock()
        first = True
        try:
            while True:
                self.pump()
                if self.paused:
                    clock.tick(5)
                    continue
                self.frame()
                if first:
                    remove_presplash()
                    first = False
                clock.tick(FPS)
        finally:
            audio.shutdown()
            pygame.quit()


def main():
    App().run()
