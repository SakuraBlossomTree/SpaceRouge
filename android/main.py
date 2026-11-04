"""SpaceRouge - mobile / pygame edition. Entry point (Buildozer runs this).

If the game crashes, the error is shown on screen (tap to close) and saved
to crash.log next to this file, instead of the app just disappearing.
"""

import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)                      # assets, saves and settings live here
sys.path.insert(0, HERE)

CRASH_LOG = os.path.join(HERE, "crash.log")

try:                                 # native crashes (segfaults) -> crash.log too
    import faulthandler
    _fh = open(CRASH_LOG + ".native", "w")
    faulthandler.enable(_fh)
except Exception:
    pass


def show_crash(text):
    """Draw the traceback on screen and wait for a tap / key."""
    try:
        import pygame
        if not pygame.get_init():
            pygame.init()
        screen = pygame.display.get_surface() or pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        W, H = screen.get_size()
        size = max(14, H // 40)
        try:
            font = pygame.font.Font(os.path.join(HERE, "assets/fonts/DejaVuSansMono.ttf"), size)
        except Exception:
            font = pygame.font.Font(None, size)
        lines = ["SpaceRouge crashed - please screenshot this.", "Tap to close.", ""]
        for raw in text.splitlines():
            while len(raw) * size * 0.6 > W - 20 and len(raw) > 20:
                cut = int((W - 20) / (size * 0.6))
                lines.append(raw[:cut])
                raw = "    " + raw[cut:]
            lines.append(raw)
        lines = lines[: 3] + lines[3:][-(H // (size + 4) - 3):]
        screen.fill((20, 4, 8))
        for i, line in enumerate(lines):
            colour = (255, 120, 120) if i < 2 else (230, 230, 230)
            screen.blit(font.render(line, True, colour), (10, 10 + i * (size + 4)))
        pygame.display.flip()
        start = time.time()
        while time.time() - start < 600:
            for ev in pygame.event.get():
                if ev.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN,
                               getattr(pygame, "FINGERDOWN", -1)) and time.time() - start > 1:
                    return
            time.sleep(0.05)
    except Exception:
        pass


def run():
    try:
        from mobile.app import main
        main()
    except SystemExit:
        raise
    except BaseException:
        text = traceback.format_exc()
        print(text, file=sys.stderr)
        try:
            with open(CRASH_LOG, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass
        show_crash(text)
        raise


if __name__ == "__main__":
    run()
