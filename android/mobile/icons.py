"""Simple vector icons for the mobile icon bar (drawn with pygame.draw).

Each function draws inside rect r in colour c on surface s.
"""

import math

import pygame


def _w(r):
    return max(2, r.width // 14)


def galaxy(s, r, c):
    """Spiral galaxy: an ellipse ring with stars."""
    cx, cy = r.center
    rx, ry = r.width * 0.42, r.height * 0.24
    pts = []
    for i in range(0, 361, 12):
        a = math.radians(i)
        k = 0.35 + 0.65 * i / 360
        pts.append((cx + math.cos(a * 1.5) * rx * k, cy + math.sin(a * 1.5) * ry * k))
    pygame.draw.lines(s, c, False, pts, _w(r))
    pygame.draw.circle(s, c, (cx, cy), max(2, r.width // 10))
    for dx, dy in ((-0.38, -0.32), (0.36, 0.3), (0.3, -0.36)):
        pygame.draw.circle(s, c, (int(cx + dx * r.width), int(cy + dy * r.height)), max(1, r.width // 22))


def contracts(s, r, c):
    """Clipboard with a tick."""
    w = _w(r)
    body = pygame.Rect(0, 0, r.width * 0.56, r.height * 0.7)
    body.center = (r.centerx, r.centery + r.height * 0.04)
    pygame.draw.rect(s, c, body, w, border_radius=max(2, w))
    clip = pygame.Rect(0, 0, body.width * 0.45, r.height * 0.1)
    clip.midtop = (body.centerx, body.top - clip.height // 2)
    pygame.draw.rect(s, c, clip, 0, border_radius=2)
    x0, y0 = body.left + body.width * 0.22, body.centery
    pygame.draw.lines(s, c, False, [(x0, y0), (x0 + body.width * 0.18, y0 + body.height * 0.16),
                                    (x0 + body.width * 0.55, y0 - body.height * 0.2)], w)


def cargo(s, r, c):
    """Crate."""
    w = _w(r)
    box = pygame.Rect(0, 0, r.width * 0.6, r.height * 0.55)
    box.center = (r.centerx, r.centery + r.height * 0.05)
    pygame.draw.rect(s, c, box, w)
    pygame.draw.line(s, c, box.topleft, box.bottomright, w)
    pygame.draw.line(s, c, box.topright, box.bottomleft, w)
    lid = pygame.Rect(box.left - w, box.top - r.height * 0.1, box.width + 2 * w, r.height * 0.1)
    pygame.draw.rect(s, c, lid, 0)


def exchange(s, r, c):
    """Rising price chart."""
    w = _w(r)
    x0, x1 = r.left + r.width * 0.2, r.right - r.width * 0.18
    y0, y1 = r.top + r.height * 0.22, r.bottom - r.height * 0.22
    pygame.draw.lines(s, c, False, [(x0, y0), (x0, y1), (x1, y1)], w)
    pts = [(x0 + (x1 - x0) * f, y1 - (y1 - y0) * v) for f, v in
           ((0.1, 0.15), (0.35, 0.45), (0.55, 0.3), (0.9, 0.85))]
    pygame.draw.lines(s, c, False, pts, w + 1)


def log(s, r, c):
    """Speech bubble with lines."""
    w = _w(r)
    b = pygame.Rect(0, 0, r.width * 0.66, r.height * 0.48)
    b.center = (r.centerx, r.centery - r.height * 0.05)
    pygame.draw.rect(s, c, b, w, border_radius=max(3, r.width // 10))
    tail = [(b.left + b.width * 0.25, b.bottom - 1), (b.left + b.width * 0.2, b.bottom + r.height * 0.14),
            (b.left + b.width * 0.42, b.bottom - 1)]
    pygame.draw.polygon(s, c, tail)
    for k in (0.35, 0.65):
        y = b.top + b.height * k
        pygame.draw.line(s, c, (b.left + b.width * 0.2, y), (b.right - b.width * 0.2, y), w)


def help(s, r, c, font=None):
    """Question mark in a circle."""
    w = _w(r)
    pygame.draw.circle(s, c, r.center, int(min(r.width, r.height) * 0.32), w)
    if font is not None:
        q = font.render("?", True, c)
        s.blit(q, q.get_rect(center=r.center))


def scan(s, r, c):
    """Cross-hair."""
    w = _w(r)
    rad = int(min(r.width, r.height) * 0.28)
    pygame.draw.circle(s, c, r.center, rad, w)
    cx, cy = r.center
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        pygame.draw.line(s, c, (cx + dx * rad * 0.4, cy + dy * rad * 0.4),
                         (cx + dx * rad * 1.45, cy + dy * rad * 1.45), w)


ICONS = {
    "galaxy": galaxy, "contracts": contracts, "cargo": cargo,
    "exchange": exchange, "log": log, "help": help, "scan": scan,
}
