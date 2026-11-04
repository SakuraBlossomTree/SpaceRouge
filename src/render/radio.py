"""Render the RADIO overlay (O): pick the music like tuning a ship's radio.

Every track in sfx/music is a "station" on the dial. The needle shows what's
playing; ↑↓ picks a station, ENTER tunes in, ←→ skips, TAB changes the play
mode (shuffle / in order / repeat one), +/- volume, X switches it off and on.
"""

import math
import re
import time
from pathlib import Path

from core import audio, state
from render import ui

W, H = 64, 40
MUSIC_FOLDER = "sfx/music"
FREQ_LO, FREQ_HI = 88.0, 108.0
MODE_NAMES = {"shuffle": "SHUFFLE", "order": "IN ORDER", "repeat": "REPEAT ONE"}


def stations():
    return audio.radio_tracks(MUSIC_FOLDER)


def frequency(i, n):
    """Spread the stations evenly over the FM band."""
    if n <= 1:
        return 98.1
    return round(FREQ_LO + 1.1 + (FREQ_HI - FREQ_LO - 2.2) * i / (n - 1), 1)


def title_artist(path):
    """'Memoraphile - Up in the Sky.ogg' -> ('Up in the Sky', 'Memoraphile');
    'echoes_of_the_past.ogg' -> ('Echoes of the Past', '')."""
    stem = Path(path).stem
    artist = ""
    if " - " in stem:
        artist, stem = stem.split(" - ", 1)
    stem = re.sub(r"_[0-9a-z]{8,}$", "", stem)            # download ids like _3mzut0qtwao
    stem = stem.replace("_", " ").strip()
    small = {"of", "the", "in", "a", "an", "and", "to", "on"}
    words = stem.split()
    if stem == stem.lower():                               # only re-case all-lowercase names
        words = [w if (k and w in small) else w[:1].upper() + w[1:] for k, w in enumerate(words)]
    elif stem.isupper() is False and " " not in stem and len(stem) > 1:
        # "MyVeryOwnDeadShip" -> "My Very Own Dead Ship"
        words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem).split()
    return " ".join(words), artist


def _clock(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _dial(console, x, y, w, needle, t, playing):
    """FM scale with tick marks and a needle at frequency `needle`."""
    console.print(x, y, "FM", fg=ui.DIM)
    sx, sw = x + 3, w - 9
    for i in range(sw):
        f = FREQ_LO + (FREQ_HI - FREQ_LO) * i / (sw - 1)
        major = abs(f - round(f / 4) * 4) < (FREQ_HI - FREQ_LO) / sw / 2
        console.print(sx + i, y, "┼" if major else "─", fg=ui.BORDER_HI if major else ui.BORDER)
    for f in range(88, 109, 4):
        i = round((f - FREQ_LO) / (FREQ_HI - FREQ_LO) * (sw - 1))
        console.print(sx + i - len(str(f)) // 2, y + 1, str(f), fg=ui.FAINT)
    console.print(x + w - 3, y, "MHz", fg=ui.DIM)
    if needle is not None:
        i = round((needle - FREQ_LO) / (FREQ_HI - FREQ_LO) * (sw - 1))
        glow = 0.7 + 0.3 * math.sin(t * 6) if playing else 0.45
        console.print(sx + i, y - 1, "▼", fg=ui.scale_color(ui.KEY, glow))
        console.print(sx + i, y, "│", fg=ui.scale_color(ui.KEY, glow))


def _meter(console, x, y, w, t, on):
    """A little bouncing level meter, two rows of half blocks (just for looks).
    Drawn at rows y-1 and y."""
    for i in range(w):
        if not on:
            console.print(x + i, y, "·", fg=ui.FAINT)
            continue
        level = 0.5 + 0.5 * math.sin(t * (3.1 + i * 0.37) + i * 1.7) * math.sin(t * 1.3 + i)
        steps = max(1, min(4, int(level * 4.99)))           # 1..4 half-cells
        fg = ui.lerp_color(ui.GOOD, ui.WARN, i / max(1, w - 1))
        console.print(x + i, y, "█" if steps >= 2 else "▄", fg=fg)
        if steps >= 3:
            console.print(x + i, y - 1, "█" if steps == 4 else "▄", fg=fg)


def draw(console, width, height=ui.MAP_H):
    t = time.time()
    tracks = stations()
    n = len(tracks)
    h = min(H, ui.MAP_H - 2, max(26, 21 + n))       # fits the station list
    x, y = ui.window(console, W, h, "Ship's radio", right_title=MODE_NAMES[audio.radio_mode])
    ix, iw = x + 3, W - 6

    path, played, length = audio.now_playing()
    on = path is not None and not audio.music_muted()
    cur = next((i for i, tr in enumerate(tracks) if path and tr.name == Path(path).name), None)

    # --- now playing --------------------------------------------------------
    needle = frequency(cur, n) if cur is not None else None
    _dial(console, ix, y + 3, iw, needle, t, on)
    if path is None:
        ui.center(console, x + W // 2, y + 6, "No signal", fg=ui.FAINT)
    else:
        name, artist = title_artist(path)
        state_txt = "OFF" if audio.music_muted() else "ON AIR"
        console.print(ix, y + 6, state_txt, fg=ui.BAD if audio.music_muted() else ui.GOOD)
        freq = f"{needle:.1f} MHz" if needle is not None else ""
        ui.right(console, ix + iw - 1, y + 6, freq, fg=ui.ACCENT)
        ui.center(console, x + W // 2, y + 7, ui.clip(name, iw), fg=ui.TITLE)
        if artist:
            ui.center(console, x + W // 2, y + 8, ui.clip(artist, iw), fg=ui.DIM)
        # progress
        bar_w = iw - 14
        if length:
            ui.bar(console, ix + 6, y + 10, bar_w, played % max(1.0, length), length, ui.ACCENT)
            ui.right(console, ix + iw - 1, y + 10, _clock(length), fg=ui.DIM)
        else:
            ui.bar(console, ix + 6, y + 10, bar_w, 0, 1, ui.ACCENT)
        console.print(ix, y + 10, _clock(played % length if length else played), fg=ui.TEXT)
        _meter(console, ix, y + 12, 16, t, on)
        vol = audio.music_volume()
        console.print(ix + iw - 22, y + 12, "VOL", fg=ui.DIM)
        ui.bar(console, ix + iw - 18, y + 12, 12, vol, 1.0, ui.KEY if on else ui.FAINT)
        ui.right(console, ix + iw - 1, y + 12, f"{round(vol * 100)}%", fg=ui.DIM)

    ui.hline(console, x, y + 14, W, fg=ui.BORDER_HI)

    # --- station list ----------------------------------------------------------
    rows = h - 20
    state.radio_index = max(0, min(state.radio_index, n - 1)) if n else 0
    top = max(0, min(state.radio_index - rows // 2, n - rows))
    if n == 0:
        ui.center(console, x + W // 2, y + 16, "No music in sfx/music", fg=ui.DIM)
    for row, i in enumerate(range(top, min(n, top + rows))):
        name, artist = title_artist(tracks[i])
        label = f"{name}" + (f" · {artist}" if artist else "")
        playing = i == cur
        ui.menu_row(console, ix - 1, y + 16 + row, iw + 2,
                    f"{frequency(i, n):5.1f}  {label}",
                    selected=(i == state.radio_index),
                    suffix="♪ playing" if playing else "",
                    suffix_fg=ui.GOOD)
    ui.scrollbar(console, x + W - 2, y + 16, rows, top, rows, n, fg=ui.BORDER_HI)

    ui.hint_row_centered(console, x + W // 2, y + h - 3,
                         [("↑↓", "Station"), ("ENTER", "Tune in"), ("←→", "Prev/next"),
                          ("TAB", "Mode")])
    ui.hint_row_centered(console, x + W // 2, y + h - 2,
                         [("+/-", "Volume"), ("X", "On/off"), ("O", "Close")])
