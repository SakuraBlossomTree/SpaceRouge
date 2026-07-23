# core/audio.py
"""Audio helper using just_playback for looping music.

just_playback plays audio asynchronously in the background, so this
module is safe to use inside a game loop.

Do NOT add a blocking loop like this in your game:

    while playback.active:
        time.sleep(1)

That will freeze your game.
"""

from pathlib import Path
import random

try:
    from just_playback import Playback
except ImportError:
    Playback = None
    print("[audio] just_playback is not installed.")
    print("[audio] Run:")
    print("[audio]     python -m pip install -U just-playback")


# Global music playback object.
# This must stay alive, so we keep it stored here.
_music = None
current_music_path = None
_failed_music_path = None

# Optional simple sound-effect list.
_sfx = []


def _is_active(playback):
    """Return True if the playback object is active."""
    if playback is None:
        return False

    try:
        return bool(playback.active)
    except Exception:
        return False


def stop_music():
    """Stop the current music."""
    global _music, current_music_path, _failed_music_path

    if _music is not None:
        try:
            _music.stop()
        except Exception:
            try:
                _music.pause()
            except Exception:
                pass

    _music = None
    current_music_path = None
    _failed_music_path = None


def play_music(path, loop=True, volume=None):
    """
    Play music using just_playback.

    This loops by default.
    """
    global _music, current_music_path, _failed_music_path

    if Playback is None:
        return

    path = Path(path)

    if not path.exists():
        print(f"[audio] Missing music file: {path}")
        _failed_music_path = str(path)
        current_music_path = None
        return

    path_str = str(path)

    # If the same track is already active, do not restart it.
    if current_music_path == path_str and _is_active(_music):
        try:
            _music.loop_at_end(loop)
        except Exception:
            pass

        # If it is paused, resume it.
        try:
            if getattr(_music, "paused", False):
                _music.resume()
        except Exception:
            pass

        return

    # Stop old music before starting new music.
    stop_music()

    try:
        playback = Playback()
        playback.load_file(path_str)

        if volume is not None:
            try:
                playback.set_volume(volume)
            except Exception:
                pass

        if loop:
            playback.loop_at_end(True)

        playback.play()

        _music = playback
        current_music_path = path_str
        _failed_music_path = None

        print(f"[audio] Playing music: {path_str}")

    except Exception as exc:
        print(f"[audio] just_playback failed to play: {path}")
        print(f"[audio] Error: {exc}")
        _music = None
        current_music_path = None
        _failed_music_path = path_str


def play(path, loop=True):
    """
    Compatibility function.

    Your old code uses:

        audio.play("sfx/music/MyVeryOwnDeadShip.ogg")

    This makes that old call loop by default.
    """
    play_music(path, loop=loop)


def ensure_music(path, loop=True, volume=None):
    """
    Safe to call every frame.

    It only starts music if the requested track is not already playing.
    """
    path_str = str(Path(path))

    if current_music_path == path_str and _is_active(_music):
        return

    if _failed_music_path == path_str:
        return

    play_music(path, loop=loop, volume=volume)


def play_random_music(folder="sfx/music", loop=True, volume=None):
    """
    Pick one random music file from a folder and loop it.

    Call this once, not every frame.
    """
    folder = Path(folder)

    if not folder.exists():
        print(f"[audio] Missing music folder: {folder}")
        return

    tracks = []

    for pattern in ("*.ogg", "*.mp3", "*.wav", "*.flac"):
        tracks.extend(folder.glob(pattern))

    tracks = sorted(tracks)

    if not tracks:
        print(f"[audio] No music files found in: {folder}")
        return

    chosen = random.choice(tracks)
    play_music(chosen, loop=loop, volume=volume)


def play_sfx(path, volume=None):
    """
    Play a one-shot sound effect.

    This uses separate Playback objects so it does not stop the music.
    """
    global _sfx

    if Playback is None:
        return

    path = Path(path)

    if not path.exists():
        print(f"[audio] Missing sound file: {path}")
        return

    # Remove finished sound effects.
    _sfx = [s for s in _sfx if _is_active(s)]

    try:
        sfx = Playback()
        sfx.load_file(str(path))

        if volume is not None:
            try:
                sfx.set_volume(volume)
            except Exception:
                pass

        sfx.play()
        _sfx.append(sfx)

    except Exception as exc:
        print(f"[audio] just_playback failed to play sound effect: {path}")
        print(f"[audio] Error: {exc}")