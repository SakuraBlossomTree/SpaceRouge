import miniaudio

device = miniaudio.PlaybackDevice()

device.__enter__()

current_stream = None

def play(path):
    global current_stream

    device.stop()

    current_stream = miniaudio.stream_file(path)
    device.start(current_stream)