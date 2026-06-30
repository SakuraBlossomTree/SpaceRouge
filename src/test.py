import miniaudio
import time

device = miniaudio.PlaybackDevice()
device.__enter__()

info = miniaudio.get_file_info("sfx/Reverse-Time-Loop-isaiah658.ogg")

stream = miniaudio.stream_file(
    "sfx/Reverse-Time-Loop-isaiah658.ogg"
)

device.start(stream)

time.sleep(info.duration)

info = miniaudio.get_file_info("sfx/NenadSimic - Muffled Distant Explosion.wav")

stream = miniaudio.stream_file(
    "sfx/NenadSimic - Muffled Distant Explosion.wav"
)

device.start(stream)

time.sleep(info.duration)

device.__exit__(None, None, None)