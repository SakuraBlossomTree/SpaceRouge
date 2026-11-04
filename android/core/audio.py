"""Audio for the mobile build: two separate channels on pygame.mixer.

    MUSIC   pygame.mixer.music - one streamed track, loops or plays a
            shuffled playlist; fades in when it changes
    SFX     pygame.mixer.Sound on their own mixer channels - overlap freely
            and never interrupt the music

Same functions as the desktop core/audio.py, so the game code is unchanged.
Volumes and mute are saved in settings.json.
"""

import random
from pathlib import Path

try:
    import pygame
except ImportError:          # pragma: no cover
    pygame = None

AUDIO_EXTS = ("*.ogg", "*.mp3", "*.wav", "*.flac")
FADE_MS = 600

_ready = False
_failed = False
_volume = {"music": 0.6, "sfx": 0.9}
_music_muted = False
_loaded = False

current_music_path = None
_music_loop = True
_playlist = []
_playlist_folder = None
_playlist_last = None

_sounds = {}             # path -> pygame.mixer.Sound
_tagged = {}             # tag -> [Channel]


# ---------------------------------------------------------------------------
# setup & settings
# ---------------------------------------------------------------------------

def _load_once():
    global _loaded, _music_muted
    if _loaded:
        return
    _loaded = True
    try:
        from core import fonts
        s = fonts.settings()
        _volume["music"] = float(s.get("music_volume", _volume["music"]))
        _volume["sfx"] = float(s.get("sfx_volume", _volume["sfx"]))
        _music_muted = bool(s.get("music_muted", False))
    except Exception:
        pass


def _save():
    try:
        from core import fonts
        s = fonts.settings()
        s["music_volume"] = round(_volume["music"], 2)
        s["sfx_volume"] = round(_volume["sfx"], 2)
        s["music_muted"] = _music_muted
        fonts.save_settings()
    except Exception:
        pass


def _ensure():
    global _ready, _failed
    if _ready:
        return True
    if _failed or pygame is None:
        return False
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(44100, -16, 2, 1024)
        pygame.mixer.set_num_channels(16)
        _load_once()
        _ready = True
        _apply_music_volume()
        return True
    except Exception as exc:
        print(f"[audio] no audio output: {exc}")
        _failed = True
        return False


def _apply_music_volume():
    if _ready:
        pygame.mixer.music.set_volume(0.0 if _music_muted else _volume["music"])


def shutdown():
    if _ready:
        try:
            pygame.mixer.music.stop()
            pygame.mixer.stop()
        except Exception:
            pass


def pause_all():
    """Android: app went to the background."""
    if _ready:
        pygame.mixer.music.pause()
        pygame.mixer.pause()


def resume_all():
    if _ready:
        pygame.mixer.music.unpause()
        pygame.mixer.unpause()


# ---------------------------------------------------------------------------
# volume / mute
# ---------------------------------------------------------------------------

def music_volume():
    _load_once()
    return _volume["music"]


def sfx_volume():
    _load_once()
    return _volume["sfx"]


def set_music_volume(v):
    _load_once()
    _volume["music"] = max(0.0, min(1.0, v))
    _apply_music_volume()
    _save()
    return _volume["music"]


def set_sfx_volume(v):
    _load_once()
    _volume["sfx"] = max(0.0, min(1.0, v))
    _save()
    return _volume["sfx"]


def music_muted():
    _load_once()
    return _music_muted


def toggle_music_mute():
    global _music_muted
    _load_once()
    _music_muted = not _music_muted
    _apply_music_volume()
    _save()
    return _music_muted


# ---------------------------------------------------------------------------
# MUSIC channel
# ---------------------------------------------------------------------------

def play_music(path, loop=True, volume=None):
    global current_music_path, _music_loop
    path = Path(path)
    if not path.exists():
        print(f"[audio] Missing music file: {path}")
        return
    if not _ensure():
        return
    try:
        pygame.mixer.music.load(str(path.resolve()))   # absolute: see play_sfx
        pygame.mixer.music.play(loops=-1 if loop else 0, fade_ms=FADE_MS)
        _apply_music_volume()
    except Exception as exc:
        print(f"[audio] Can't play {path}: {exc}")
        return
    current_music_path = str(path)
    _music_loop = loop
    print(f"[audio] Playing music: {path}")


def stop_music():
    global current_music_path, _playlist_folder
    _playlist_folder = None
    current_music_path = None
    if _ready:
        try:
            pygame.mixer.music.fadeout(FADE_MS)
        except Exception:
            pygame.mixer.music.stop()


def _playing():
    return _ready and pygame.mixer.music.get_busy()


def ensure_music(path, loop=True, volume=None):
    global _playlist_folder
    if current_music_path == str(Path(path)) and _playing():
        return
    _playlist_folder = None
    play_music(path, loop=loop, volume=volume)


def _tracks(folder):
    tracks = []
    for pattern in AUDIO_EXTS:
        tracks.extend(Path(folder).glob(pattern))
    return sorted(tracks)


def play_playlist(folder="sfx/music", exclude=()):
    global _playlist, _playlist_folder
    exclude = tuple(sorted(Path(e).name for e in exclude))
    if not _tracks(folder):
        print(f"[audio] No music files found in: {folder}")
        _empty_folders.add(str(folder))
        return
    _playlist_folder = (str(folder), exclude)
    _playlist = []
    _next_track()


_empty_folders = set()


def ensure_playlist(folder="sfx/music", exclude=()):
    if str(folder) in _empty_folders:
        return
    key = (str(folder), tuple(sorted(Path(e).name for e in exclude)))
    if _playlist_folder == key and current_music_path is not None:
        return
    play_playlist(folder, exclude)


def _next_track():
    global _playlist, _playlist_last
    if _playlist_folder is None:
        return
    folder, exclude = _playlist_folder
    if not _playlist:
        tracks = [t for t in _tracks(folder) if t.name not in exclude] or _tracks(folder)
        random.shuffle(tracks)
        if len(tracks) > 1 and tracks[0] == _playlist_last:
            tracks.append(tracks.pop(0))
        _playlist = tracks
    if _playlist:
        track = _playlist.pop(0)
        _playlist_last = track
        play_music(track, loop=False)


def play_random_music(folder="sfx/music", loop=True, volume=None):
    tracks = _tracks(folder)
    if tracks:
        play_music(random.choice(tracks), loop=loop, volume=volume)


def update():
    """Call once per frame: moves the playlist on when a track ends."""
    if _playlist_folder is not None and current_music_path is not None and _ready \
            and not pygame.mixer.music.get_busy():
        _next_track()
    for tag in list(_tagged):
        _tagged[tag] = [c for c in _tagged[tag] if c.get_busy()]


# ---------------------------------------------------------------------------
# SFX channel
# ---------------------------------------------------------------------------

def play_sfx(path, volume=1.0, loop=False, tag=None):
    path = Path(path)
    if not path.exists():
        print(f"[audio] Missing sound file: {path}")
        return False
    if not _ensure():
        return False
    try:
        # absolute path: on Android, SDL resolves relative paths inside the APK
        # assets instead of the working directory
        key = str(path.resolve())
        if key not in _sounds:
            _sounds[key] = pygame.mixer.Sound(key)
        channel = _sounds[key].play(loops=-1 if loop else 0)
    except Exception as exc:
        print(f"[audio] Can't play sound {path}: {exc}")
        return False
    if channel is None:
        return False
    channel.set_volume(max(0.0, min(1.0, volume * _volume["sfx"])))
    if tag:
        _tagged.setdefault(tag, []).append(channel)
    return True


def stop_sfx(tag=None):
    if not _ready:
        return
    if tag is None:
        for chans in _tagged.values():
            for c in chans:
                c.stop()
        _tagged.clear()
        pygame.mixer.stop()
        return
    for c in _tagged.pop(tag, []):
        c.stop()


def play(path, loop=False, tag=None):
    return play_sfx(path, loop=loop, tag=tag)
