"""Audio: two independent channels - MUSIC and SFX - mixed into one output.

Uses miniaudio (already in requirements.txt) plus numpy (comes with tcod).

    MUSIC   one track at a time, streamed from disk, loops or follows a
            shuffled playlist, fades in/out when it changes
    SFX     any number of overlapping one-shot (or looping) sounds, decoded
            once and cached; never interrupts the music

Each channel has its own volume (F5/F6 music, F7/F8 effects in-game) and
F4 mutes the music; all saved to settings.json.

Music is loudness-normalised: every track is measured once (ITU BS.1770 /
EBU R128 integrated loudness, the standard streaming services use) and
played back at the same perceived level, TARGET_LUFS. Measurements are kept
in music_levels.json; a track that isn't in there yet is measured in the
background the first time it's needed. If miniaudio is missing or no audio device is
available, every call quietly does nothing and the game keeps running.

Public API:
    play_music(path, loop=True)      ensure_music(path)      stop_music()
    play_playlist(folder)            ensure_playlist(folder)
    play_sfx(path, volume=1.0, loop=False, tag=None)   stop_sfx(tag)
    set_music_volume(v)  set_sfx_volume(v)  music_volume()  sfx_volume()
    update()   - call once per frame (advances the playlist)
"""

import random
import threading
from pathlib import Path

try:
    import miniaudio
    import numpy as np
except ImportError as exc:          # pragma: no cover - depends on install
    miniaudio = None
    np = None
    print(f"[audio] disabled: {exc}. Run: pip install -r requirements.txt")

RATE = 44100
CHANNELS = 2
CHUNK_FRAMES = 4096
FADE_SECONDS = 0.6
AUDIO_EXTS = ("*.ogg", "*.mp3", "*.wav", "*.flac")

_lock = threading.Lock()
_device = None
_failed = False

_music = None          # current _MusicStream
_fading_out = []       # streams fading away after a change
_sfx = []              # active _Sound voices
_sfx_cache = {}        # path -> decoded int16 numpy array

_playlist = []         # remaining tracks (shuffled)
_playlist_folder = None
_playlist_last = None

current_music_path = None
_volume = {"music": 0.6, "sfx": 0.9}
_music_muted = False


# ---------------------------------------------------------------------------
# Loudness normalisation (music)
# ---------------------------------------------------------------------------

TARGET_LUFS = -18.0         # every track is played back at this loudness
MAX_BOOST = 4.0             # never more than +12 dB ...
PEAK_LIMIT = 0.98           # ... or so much that the track's peaks would clip
LEVELS_PATH = Path("music_levels.json")

_levels = None              # file name -> {"lufs", "peak", "size"}
_levels_lock = threading.Lock()
_measuring = set()


def _k_weight_power(freqs):
    """|H(f)|^2 of the BS.1770 K-weighting filter (high shelf + high-pass)."""
    w = 2 * np.pi * freqs / 48000.0
    z = np.exp(-1j * w)

    def biquad(b, a):
        return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)

    h = biquad((1.53512485958697, -2.69169618940638, 1.19839281085285),
               (1.0, -1.69065929318241, 0.73248077421585))
    h *= biquad((1.0, -2.0, 1.0), (1.0, -1.99004745483398, 0.99007225036621))
    return np.abs(h) ** 2


def measure_loudness(samples, rate=RATE):
    """Integrated loudness in LUFS (BS.1770 gating, 400 ms blocks, 75 %
    overlap, K-weighting applied in the frequency domain) and the peak, of
    interleaved stereo int16 samples. Matches ffmpeg's ebur128 to ~0.05 dB."""
    st = samples.reshape(-1, CHANNELS).astype(np.float32) / 32768.0
    peak = float(np.abs(st).max()) if len(st) else 0.0
    block, hop = int(rate * 0.4), int(rate * 0.1)
    n = (len(st) - block) // hop + 1
    if n <= 0:
        return -70.0, peak
    wk = _k_weight_power(np.fft.rfftfreq(block, 1 / rate))[:, None]
    powers = np.empty(n)
    for i in range(n):
        spec = np.fft.rfft(st[i * hop:i * hop + block], axis=0)
        p = np.abs(spec) ** 2 * wk
        p[1:-1] *= 2                                  # one-sided spectrum
        powers[i] = p.sum() / (block * block)         # both channels summed
    lk = -0.691 + 10 * np.log10(powers + 1e-20)
    gated = powers[lk > -70]
    if len(gated) == 0:
        return -70.0, peak
    rel = -0.691 + 10 * np.log10(gated.mean()) - 10
    gated = gated[-0.691 + 10 * np.log10(gated) > rel]
    return float(-0.691 + 10 * np.log10(gated.mean())), peak


def _load_levels():
    global _levels
    if _levels is None:
        try:
            import json
            _levels = json.loads(LEVELS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _levels = {}
    return _levels


def _save_levels():
    try:
        import json
        LEVELS_PATH.write_text(json.dumps(_levels, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def _known_level(path):
    """Saved measurement for a track, if it's still the same file."""
    path = Path(path)
    with _levels_lock:
        entry = _load_levels().get(path.name)
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if entry and entry.get("size") == size:
        return entry
    return None


def _measure_track(path):
    path = Path(path)
    try:
        decoded = miniaudio.decode_file(
            str(path), output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=CHANNELS, sample_rate=RATE)
        samples = np.frombuffer(decoded.samples, dtype=np.int16)
        lufs, peak = measure_loudness(samples)
        entry = {"lufs": round(lufs, 2), "peak": round(peak, 4), "size": path.stat().st_size,
                 "seconds": round(len(samples) / CHANNELS / RATE, 1)}
        with _levels_lock:
            _load_levels()[path.name] = entry
            _save_levels()
        print(f"[audio] measured {path.name}: {lufs:.1f} LUFS, peak {peak:.2f}")
        return entry
    except Exception as exc:
        print(f"[audio] couldn't measure {path.name}: {exc}")
        return None
    finally:
        _measuring.discard(str(path))


def _measure_later(paths):
    """Measure tracks on a background thread (one after another)."""
    todo = [Path(p) for p in paths
            if _known_level(p) is None and str(p) not in _measuring]
    if not todo:
        return
    for p in todo:
        _measuring.add(str(p))

    def run():
        for p in todo:
            _measure_track(p)
    threading.Thread(target=run, daemon=True).start()


def track_gain(path):
    """Volume factor that brings a track to TARGET_LUFS, or None if it hasn't
    been measured yet."""
    entry = _known_level(path)
    if entry is None:
        return None
    gain = 10 ** ((TARGET_LUFS - entry["lufs"]) / 20)
    gain = min(gain, MAX_BOOST)
    if entry.get("peak"):
        gain = min(gain, PEAK_LIMIT / entry["peak"])
    return gain


# ---------------------------------------------------------------------------
# Settings (volume persists between runs)
# ---------------------------------------------------------------------------

def _load_volumes():
    try:
        from core import fonts
        s = fonts.settings()
        _volume["music"] = float(s.get("music_volume", _volume["music"]))
        _volume["sfx"] = float(s.get("sfx_volume", _volume["sfx"]))
        global _music_muted
        _music_muted = bool(s.get("music_muted", False))
    except Exception:
        pass


def _save_volumes():
    try:
        from core import fonts
        fonts.settings()["music_volume"] = round(_volume["music"], 2)
        fonts.settings()["sfx_volume"] = round(_volume["sfx"], 2)
        fonts.settings()["music_muted"] = _music_muted
        fonts.save_settings()
    except Exception:
        pass


def music_volume():
    return _volume["music"]


def sfx_volume():
    return _volume["sfx"]


def music_muted():
    _load_once()
    return _music_muted


_loaded = False


def _load_once():
    global _loaded
    if not _loaded:
        _loaded = True
        _load_volumes()


def toggle_music_mute():
    """Mute / unmute the music channel (sound effects keep playing)."""
    global _music_muted
    _load_once()
    _music_muted = not _music_muted
    _save_volumes()
    return _music_muted


def set_music_volume(v):
    _volume["music"] = max(0.0, min(1.0, v))
    _save_volumes()
    return _volume["music"]


def set_sfx_volume(v):
    _volume["sfx"] = max(0.0, min(1.0, v))
    _save_volumes()
    return _volume["sfx"]


# ---------------------------------------------------------------------------
# Voices
# ---------------------------------------------------------------------------

class _MusicStream:
    """A track streamed from disk in chunks, with a fade envelope."""

    def __init__(self, path, loop):
        self.path = str(path)
        self.loop = loop
        self.done = False
        self.gain = 0.0            # fades in from silence
        self.target = 1.0
        # loudness normalisation: None = still being measured (stay silent,
        # at most WAIT_SECONDS, rather than blast a loud track for a moment)
        self.norm = track_gain(path)
        self._waited = 0
        self.frames_played = 0     # for the radio's progress bar
        self._buf = np.zeros(0, dtype=np.int16)
        self._open()

    WAIT_SECONDS = 4.0

    def _open(self):
        self._gen = miniaudio.stream_file(
            self.path, output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=CHANNELS, sample_rate=RATE, frames_to_read=CHUNK_FRAMES)

    def read(self, frames):
        need = frames * CHANNELS
        restarts = 0
        while len(self._buf) < need and not self.done:
            try:
                chunk = next(self._gen)
            except StopIteration:
                if self.loop and restarts < 2:
                    restarts += 1
                    self._open()
                    self.frames_played = 0
                    continue
                self.done = True
                break
            self._buf = np.concatenate((self._buf, np.frombuffer(chunk, dtype=np.int16)))
        if self.norm is None:
            self.norm = track_gain(self.path)
            if self.norm is None:
                self._waited += frames
                if self._waited < RATE * self.WAIT_SECONDS:
                    return np.zeros(need, dtype=np.float32)   # wait for the measurement
                self.norm = 1.0
        out = self._buf[:need]
        self._buf = self._buf[need:]
        self.frames_played += len(out) // CHANNELS
        if len(out) < need:
            out = np.concatenate((out, np.zeros(need - len(out), dtype=np.int16)))
        return out.astype(np.float32) * self.norm

    def envelope(self, frames):
        """Per-sample gain ramp toward target (for fades)."""
        step = frames / (RATE * FADE_SECONDS)
        start = self.gain
        if self.target > self.gain:
            self.gain = min(self.target, self.gain + step)
        else:
            self.gain = max(self.target, self.gain - step)
        ramp = np.linspace(start, self.gain, frames, dtype=np.float32)
        return np.repeat(ramp, CHANNELS)


class _Sound:
    """A decoded sound effect playing from memory."""

    def __init__(self, samples, volume, loop, tag):
        self.samples = samples
        self.pos = 0
        self.volume = volume
        self.loop = loop
        self.tag = tag
        self.done = False

    def read(self, frames):
        need = frames * CHANNELS
        out = np.zeros(need, dtype=np.float32)
        filled = 0
        while filled < need and not self.done:
            take = min(need - filled, len(self.samples) - self.pos)
            out[filled:filled + take] = self.samples[self.pos:self.pos + take]
            filled += take
            self.pos += take
            if self.pos >= len(self.samples):
                if self.loop and len(self.samples):
                    self.pos = 0
                else:
                    self.done = True
        return out * self.volume


# ---------------------------------------------------------------------------
# The mixer (runs on miniaudio's audio thread)
# ---------------------------------------------------------------------------

def _mixer():
    required = yield b""
    while True:
        try:
            n = required * CHANNELS
            music_bus = np.zeros(n, dtype=np.float32)
            sfx_bus = np.zeros(n, dtype=np.float32)
            with _lock:
                streams = ([_music] if _music else []) + list(_fading_out)
                voices = list(_sfx)
            for s in streams:
                music_bus += s.read(required) * s.envelope(required)
            for v in voices:
                sfx_bus += v.read(required)
            with _lock:
                _fading_out[:] = [s for s in _fading_out if s.gain > 0.0 and not s.done]
                _sfx[:] = [v for v in _sfx if not v.done]
            music_gain = 0.0 if _music_muted else _volume["music"]
            mix = music_bus * music_gain + sfx_bus * _volume["sfx"]
            np.clip(mix, -32768, 32767, out=mix)
            required = yield mix.astype(np.int16).tobytes()
        except Exception as exc:       # never let the audio thread die
            print(f"[audio] mixer error: {exc}")
            required = yield bytes(required * CHANNELS * 2)


def _ensure_device():
    global _device, _failed
    if _device is not None:
        return True
    if _failed or miniaudio is None:
        return False
    try:
        _load_volumes()
        _load_radio_mode()
        _device = miniaudio.PlaybackDevice(
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=CHANNELS, sample_rate=RATE, buffersize_msec=120)
        gen = _mixer()
        next(gen)
        _device.start(gen)
        return True
    except Exception as exc:
        print(f"[audio] no audio output: {exc}")
        _failed = True
        _device = None
        return False


def shutdown():
    global _device
    if _device is not None:
        try:
            _device.close()
        except Exception:
            pass
        _device = None


# ---------------------------------------------------------------------------
# MUSIC channel
# ---------------------------------------------------------------------------

def play_music(path, loop=True, volume=None):
    """Start a track on the music channel (fades out whatever was playing)."""
    global _music, current_music_path
    path = Path(path)
    if not path.exists():
        print(f"[audio] Missing music file: {path}")
        return
    if not _ensure_device():
        return
    if track_gain(path) is None:
        _measure_later([path])
    try:
        stream = _MusicStream(path, loop)
    except Exception as exc:
        print(f"[audio] Can't play {path}: {exc}")
        return
    if volume is not None:
        stream.target = max(0.0, min(1.0, volume))
    with _lock:
        if _music is not None:
            _music.target = 0.0
            _fading_out.append(_music)
        _music = stream
    current_music_path = str(path)
    print(f"[audio] Playing music: {path}")


def stop_music():
    """Fade the music channel out (and stop any playlist)."""
    global _music, current_music_path, _playlist_folder
    _playlist_folder = None
    with _lock:
        if _music is not None:
            _music.target = 0.0
            _fading_out.append(_music)
        _music = None
    current_music_path = None


def ensure_music(path, loop=True, volume=None):
    """Safe every frame: only starts the track if it isn't already playing."""
    global _playlist_folder
    if current_music_path == str(Path(path)) and _music is not None and not _music.done:
        return
    _playlist_folder = None
    play_music(path, loop=loop, volume=volume)


def _tracks(folder):
    folder = Path(folder)
    tracks = []
    for pattern in AUDIO_EXTS:
        tracks.extend(folder.glob(pattern))
    return sorted(tracks)


def play_playlist(folder="sfx/music", exclude=()):
    """Shuffle a folder of tracks and play them back to back, forever."""
    global _playlist, _playlist_folder
    exclude = {Path(e).name for e in exclude}
    tracks = [t for t in _tracks(folder) if t.name not in exclude] or _tracks(folder)
    if not tracks:
        print(f"[audio] No music files found in: {folder}")
        _empty_folders.add(str(folder))
        return
    _playlist_folder = (str(folder), tuple(sorted(exclude)))
    _playlist = []
    _next_track()                           # (measures its own track first)
    _measure_later(_tracks(folder))         # then any other new tracks, in the background


_empty_folders = set()


def ensure_playlist(folder="sfx/music", exclude=()):
    """Safe every frame: starts the playlist if it isn't already running."""
    if str(folder) in _empty_folders:
        return
    key = (str(folder), tuple(sorted(Path(e).name for e in exclude)))
    if _playlist_folder == key and _music is not None:
        return
    play_playlist(folder, exclude)


def _next_track():
    global _playlist, _playlist_last
    if _playlist_folder is None:
        return
    folder, exclude = _playlist_folder
    if radio_mode == "order":
        # in-order: the track after the current one, alphabetically, wrapping
        tracks = _tracks(folder)
        if tracks:
            cur = Path(current_music_path) if current_music_path else None
            i = next((k for k, t in enumerate(tracks) if cur and t.name == cur.name), -1)
            track = tracks[(i + 1) % len(tracks)]
            _playlist_last = track
            play_music(track, loop=False)
        return
    if not _playlist:
        tracks = [t for t in _tracks(folder) if t.name not in exclude] or _tracks(folder)
        random.shuffle(tracks)
        if len(tracks) > 1 and tracks[0] == _playlist_last:
            tracks.append(tracks.pop(0))       # don't repeat the last song
        _playlist = tracks
    if _playlist:
        track = _playlist.pop(0)
        _playlist_last = track
        play_music(track, loop=False)


def play_random_music(folder="sfx/music", loop=True, volume=None):
    """Pick one random track from a folder and loop it."""
    tracks = _tracks(folder)
    if tracks:
        play_music(random.choice(tracks), loop=loop, volume=volume)


def update():
    """Call once per frame: moves the playlist on when a track ends."""
    if _playlist_folder is not None and _music is not None and _music.done:
        _next_track()


# ---------------------------------------------------------------------------
# Radio (in-game music player)
# ---------------------------------------------------------------------------

RADIO_MODES = ("shuffle", "order", "repeat")
radio_mode = "shuffle"      # shuffle: random order | order: alphabetical | repeat: loop one
_history = []               # tracks played, for "previous"


def radio_tracks(folder="sfx/music"):
    """Every track in the folder (the title theme too)."""
    return _tracks(folder)


def now_playing():
    """(path, seconds played, track length or None) of the current track."""
    if _music is None or current_music_path is None:
        return None, 0.0, None
    entry = _known_level(current_music_path)
    length = entry.get("seconds") if entry else None
    return current_music_path, _music.frames_played / RATE, length


def radio_play(path):
    """Tune in to a track. The playlist carries on from it afterwards
    (or loops it, in repeat mode)."""
    if current_music_path and (not _history or _history[-1] != current_music_path):
        _history.append(current_music_path)
        del _history[:-50]
    play_music(path, loop=(radio_mode == "repeat"))


def radio_next():
    if current_music_path:
        _history.append(current_music_path)
        del _history[:-50]
    if radio_mode == "repeat":
        tracks = radio_tracks(_playlist_folder[0] if _playlist_folder else "sfx/music")
        if tracks:
            cur = Path(current_music_path).name if current_music_path else None
            i = next((k for k, t in enumerate(tracks) if t.name == cur), -1)
            play_music(tracks[(i + 1) % len(tracks)], loop=True)
        return
    _next_track()


def radio_prev():
    """Back to the previous track (or the start of this one if there's no history)."""
    while _history:
        prev = _history.pop()
        if prev != current_music_path or not _history:
            play_music(prev, loop=(radio_mode == "repeat"))
            return
    if current_music_path:
        play_music(current_music_path, loop=(radio_mode == "repeat"))


def radio_cycle_mode():
    """shuffle -> order -> repeat -> shuffle. Applies to the playing track too."""
    global radio_mode
    radio_mode = RADIO_MODES[(RADIO_MODES.index(radio_mode) + 1) % len(RADIO_MODES)]
    with _lock:
        if _music is not None:
            _music.loop = radio_mode == "repeat"
    try:
        from core import fonts
        fonts.settings()["radio_mode"] = radio_mode
        fonts.save_settings()
    except Exception:
        pass
    return radio_mode


def _load_radio_mode():
    global radio_mode
    try:
        from core import fonts
        m = fonts.settings().get("radio_mode", "shuffle")
        radio_mode = m if m in RADIO_MODES else "shuffle"
    except Exception:
        pass


# ---------------------------------------------------------------------------
# SFX channel
# ---------------------------------------------------------------------------

def _load_sound(path):
    key = str(path)
    if key not in _sfx_cache:
        decoded = miniaudio.decode_file(
            key, output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=CHANNELS, sample_rate=RATE)
        _sfx_cache[key] = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32)
    return _sfx_cache[key]


def play_sfx(path, volume=1.0, loop=False, tag=None):
    """Play a sound effect over the music. Returns True if it started."""
    path = Path(path)
    if not path.exists():
        print(f"[audio] Missing sound file: {path}")
        return False
    if not _ensure_device():
        return False
    try:
        samples = _load_sound(path)
    except Exception as exc:
        print(f"[audio] Can't play sound {path}: {exc}")
        return False
    with _lock:
        _sfx.append(_Sound(samples, volume, loop, tag))
    return True


def stop_sfx(tag=None):
    """Stop sound effects with this tag (or all of them if tag is None)."""
    with _lock:
        for v in _sfx:
            if tag is None or v.tag == tag:
                v.done = True


def play(path, loop=False, tag=None):
    """Old name kept for compatibility: plays on the SFX channel."""
    return play_sfx(path, loop=loop, tag=tag)
