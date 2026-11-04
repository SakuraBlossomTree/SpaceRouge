"""Camera + zoom for the galaxy chart.

The galaxy is bigger than the 80x60 viewport, so the chart is a window onto
it. World coordinates are the stars' x/y; screen coordinates are cells in the
map viewport. `scale` is how many world units one screen cell covers:

    0.5  -> close-up (each world unit is 2 cells apart, names everywhere)
    1.0  -> normal
    1.6  -> wide
    2.4  -> the whole galaxy fits on screen

All the maths lives here so the renderer and the input handler agree.
"""

from core import state
from core.world import GALAXY_W, GALAXY_H

VIEW_W, VIEW_H = 80, 60

ZOOMS = [0.5, 1.0, 1.6, max(GALAXY_W / VIEW_W, GALAXY_H / VIEW_H)]


def configure(view_w, view_h):
    """Set the chart's size in cells (the mobile build uses its own size)."""
    global VIEW_W, VIEW_H
    VIEW_W, VIEW_H = view_w, view_h
    ZOOMS[-1] = max(GALAXY_W / VIEW_W, GALAXY_H / VIEW_H)
    clamp()


ZOOM_NAMES = ["x2", "x1", "wide", "full"]
DEFAULT_ZOOM = 1


def scale():
    return ZOOMS[state.galaxy_zoom]


def zoom_name():
    return ZOOM_NAMES[state.galaxy_zoom]


def project(wx, wy):
    """World -> screen cell (may be off-screen)."""
    s = scale()
    sx = int(round((wx - state.galaxy_cam_x) / s + VIEW_W / 2))
    sy = int(round((wy - state.galaxy_cam_y) / s + VIEW_H / 2))
    return sx, sy


def unproject(sx, sy):
    s = scale()
    return ((sx - VIEW_W / 2) * s + state.galaxy_cam_x,
            (sy - VIEW_H / 2) * s + state.galaxy_cam_y)


def on_screen(sx, sy):
    return 0 <= sx < VIEW_W and 0 <= sy < VIEW_H


def visible_rect():
    """(x0, y0, x1, y1) of the world area currently shown."""
    s = scale()
    hw, hh = VIEW_W * s / 2, VIEW_H * s / 2
    return (state.galaxy_cam_x - hw, state.galaxy_cam_y - hh,
            state.galaxy_cam_x + hw, state.galaxy_cam_y + hh)


def clamp():
    """Keep the camera inside the galaxy (or centred if it all fits)."""
    s = scale()
    hw, hh = VIEW_W * s / 2, VIEW_H * s / 2
    margin = 2
    if hw * 2 >= GALAXY_W:
        state.galaxy_cam_x = GALAXY_W / 2
    else:
        state.galaxy_cam_x = max(hw - margin, min(GALAXY_W - hw + margin, state.galaxy_cam_x))
    if hh * 2 >= GALAXY_H:
        state.galaxy_cam_y = GALAXY_H / 2
    else:
        state.galaxy_cam_y = max(hh - margin, min(GALAXY_H - hh + margin, state.galaxy_cam_y))


def center_on(wx, wy):
    state.galaxy_cam_x, state.galaxy_cam_y = wx, wy
    clamp()


def scroll(dx_cells, dy_cells):
    """Pan by a number of screen cells (so it feels the same at every zoom)."""
    s = scale()
    state.galaxy_cam_x += dx_cells * s
    state.galaxy_cam_y += dy_cells * s
    clamp()


def follow(wx, wy, margin=6):
    """Pan just enough to keep a world point (e.g. the scan cursor) on screen."""
    sx, sy = project(wx, wy)
    s = scale()
    if sx < margin:
        state.galaxy_cam_x -= (margin - sx) * s
    elif sx > VIEW_W - 1 - margin:
        state.galaxy_cam_x += (sx - (VIEW_W - 1 - margin)) * s
    if sy < margin:
        state.galaxy_cam_y -= (margin - sy) * s
    elif sy > VIEW_H - 1 - margin:
        state.galaxy_cam_y += (sy - (VIEW_H - 1 - margin)) * s
    clamp()


def set_zoom(level, anchor=None):
    """Change zoom, keeping `anchor` (world x, y) at the same screen cell."""
    level = max(0, min(len(ZOOMS) - 1, level))
    if level == state.galaxy_zoom:
        return
    if anchor is None:
        anchor = (state.galaxy_cam_x, state.galaxy_cam_y)
    ax, ay = anchor
    sx, sy = project(ax, ay)
    state.galaxy_zoom = level
    s = scale()
    state.galaxy_cam_x = ax - (sx - VIEW_W / 2) * s
    state.galaxy_cam_y = ay - (sy - VIEW_H / 2) * s
    clamp()


def zoom(step, anchor=None):
    """step > 0 zooms in (closer), step < 0 zooms out."""
    set_zoom(state.galaxy_zoom - step, anchor)


def star_at_cell(stars, sx, sy):
    """The star drawn at a screen cell (nearest to the cell centre if several)."""
    best, best_d = None, None
    cx, cy = unproject(sx, sy)
    for star in stars:
        if project(star.x, star.y) == (sx, sy):
            d = (star.x - cx) ** 2 + (star.y - cy) ** 2
            if best_d is None or d < best_d:
                best, best_d = star, d
    return best
