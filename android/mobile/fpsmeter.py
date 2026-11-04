"""Tiny on-screen speed readout (top-left corner) for testing on phones.

    58 fps | build 4.1  cells 2.0  show 3.9 ms | peak 41

fps   - how many times a second the game loop runs (60 is the cap)
build - the game drawing its text screen (Python game code)
cells - turning changed characters into pixels
show  - copying to the screen and handing the frame to Android. This can
        include WAITING for the display's next refresh, which is idle time,
        not work.
Times are TYPICAL (median) values over the last second, for frames where the
screen changed, so one slow frame (e.g. switching menus redraws everything)
doesn't blow up the numbers. "peak" is the slowest single frame in that second.
Set ENABLED = False to hide it.
"""

import time

import pygame

ENABLED = True
PARTS = ("build", "cells", "show")


def _median(values):
    v = sorted(values)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


class FpsMeter:
    def __init__(self, font_path, height):
        self.font = pygame.font.Font(font_path, max(12, int(height * 0.022)))
        self.loops = 0
        self.samples = []          # one (build, cells, show) tuple per drawn frame
        self.t0 = time.monotonic()
        self.label = None
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._new = False
        self._mark = None
        self._cur = {}

    # ---- timing a frame: start(), lap("build"), lap("cells"), lap("show") --

    def start(self):
        self._mark = time.perf_counter()
        self._cur = {}

    def lap(self, part):
        now = time.perf_counter()
        if self._mark is not None:
            self._cur[part] = self._cur.get(part, 0.0) + (now - self._mark)
        self._mark = now

    def end(self, drew):
        """Call once per loop; drew = the screen changed this loop."""
        self.loops += 1
        if drew:
            self.samples.append(tuple(self._cur.get(k, 0.0) for k in PARTS))
        now = time.monotonic()
        if now - self.t0 >= 1.0:
            fps = self.loops / (now - self.t0)
            if self.samples:
                ms = [1000 * _median([smp[i] for smp in self.samples]) for i in range(len(PARTS))]
                peak = 1000 * max(sum(smp) for smp in self.samples)
            else:
                ms, peak = [0.0] * len(PARTS), 0.0
            text = (f" {fps:4.1f} fps | build {ms[0]:4.1f}  cells {ms[1]:4.1f}"
                    f"  show {ms[2]:4.1f} ms | peak {peak:3.0f} ")
            self.label = self.font.render(text, True, (255, 230, 120), (0, 0, 0))
            self.rect = self.label.get_rect(topleft=(4, 4))
            self.loops = 0
            self.samples = []
            self.t0 = now
            self._new = True

    def draw(self, screen, rects):
        """Draw the label if it changed or was painted over. Returns rects to update."""
        if not ENABLED or self.label is None:
            return []
        if self._new or self.rect.collidelist(rects) >= 0:
            screen.blit(self.label, self.rect)
            self._new = False
            return [self.rect]
        return []
