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


# ---------------------------------------------------------------------------
# System survey / scanner data
# ---------------------------------------------------------------------------

def scanned_systems():
    """Return the persistent set of system names whose local data is known."""
    known = getattr(state, "galaxy_scanned_systems", None)
    if known is None:
        known = set()
        state.galaxy_scanned_systems = known
    elif not isinstance(known, set):
        # Save files may deserialize this as a list. Normalize it once.
        known = set(known)
        state.galaxy_scanned_systems = known
    return known


def scanner_range():
    """Scanner radius in galaxy world-coordinate units (0 means no module).

    The ship upgrade code should set state.galaxy_scanner_range.
    """
    try:
        return max(0.0, float(getattr(state, "galaxy_scanner_range", 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _scanner_origin(stars):
    """Find the player's star in the supplied galaxy star collection."""
    name = getattr(getattr(state, "current_star", None), "name", None)
    if name is None:
        name = getattr(getattr(state, "current_system", None), "name", None)
    if name is None:
        return None
    return next((star for star in stars if star.name == name), None)


def scanner_distance(star, stars):
    """Euclidean distance from the player to a star, in galaxy units."""
    origin = _scanner_origin(stars)
    if origin is None or star is None:
        return None
    dx = star.x - origin.x
    dy = star.y - origin.y
    return (dx * dx + dy * dy) ** 0.5


def scanner_covers(star, stars):
    """Whether the installed scanner currently reaches this system."""
    radius = scanner_range()
    distance = scanner_distance(star, stars)
    return radius > 0 and distance is not None and distance <= radius


def is_system_scanned(star_or_name):
    """Current and previously scanned systems may show their local system map."""
    name = getattr(star_or_name, "name", star_or_name)
    current_name = getattr(getattr(state, "current_star", None), "name", None)
    if current_name is None:
        current_name = getattr(getattr(state, "current_system", None), "name", None)
    return name == current_name or name in scanned_systems()


def update_scanner(stars):
    """Passively survey all systems inside the current scanner's radius.

    Call this when rendering the galaxy map (or from the world-update loop).
    Discovered data is retained after the player moves away.
    """
    radius = scanner_range()
    if radius <= 0:
        return scanned_systems()

    origin = _scanner_origin(stars)
    if origin is None:
        return scanned_systems()

    known = scanned_systems()
    radius_sq = radius * radius
    for star in stars:
        dx = star.x - origin.x
        dy = star.y - origin.y
        if dx * dx + dy * dy <= radius_sq:
            known.add(star.name)
    return known
