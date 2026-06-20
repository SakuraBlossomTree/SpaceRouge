import tcod
import tcod.event
import miniaudio
from pathlib import Path


class MusicPlayerScreen:
    def __init__(self):
        self.device = miniaudio.PlaybackDevice()

        self.albums = {}
        self.selected_album = 0

        self.scroll_offset = 0
        self.visible_rows = 20

        self.current_album = None
        self.current_track_index = 0

        self.is_playing = False

        self.volume = 1.0
        self.muted = False

        self.search_paths = [
            Path("music"),
            Path.home() / "Music"
        ]

    def create_stream(self, filename):
        return miniaudio.stream_file(filename)

    def scan_albums(self):
        self.albums.clear()

        for base in self.search_paths:
            if not base.exists():
                continue

            for folder in base.iterdir():
                if not folder.is_dir():
                    continue

                tracks = []

                for ext in ("*.mp3", "*.flac", "*.ogg", "*.wav"):
                    tracks.extend(folder.glob(ext))

                if tracks:
                    self.albums[folder.name] = sorted(
                        str(t) for t in tracks
                    )

    def play_current(self):
        if not self.current_album:
            return

        track = self.albums[self.current_album][
            self.current_track_index
        ]

        try:
            self.device.stop()

            stream = self.create_stream(track)

            self.device.start(stream)

            self.is_playing = True

            print("Playing:", track)

        except Exception as e:
            print("Playback error:", e)

    def stop(self):
        self.device.stop()
        self.is_playing = False

    def next_track(self):
        if not self.current_album:
            return

        tracks = self.albums[self.current_album]

        self.current_track_index = (
            self.current_track_index + 1
        ) % len(tracks)

        self.play_current()

    def draw(self, console):
        console.clear()

        console.print(
            2,
            1,
            "=== SHIP COMM MUSIC ===",
            fg=(255, 255, 0)
        )

        volume_text = "MUTED" if self.muted else f"{int(self.volume * 100)}%"

        console.print(
            2,
            2,
            f"Volume: {volume_text}",
            fg=(200, 200, 200)
        )

        albums = list(self.albums.keys())

        y = 4

        start = self.scroll_offset
        end = min(
            len(albums),
            start + self.visible_rows
        )

        for i in range(start, end):
            album = albums[i]

            selected = i == self.selected_album

            console.print(
                4,
                y + (i - start),
                f"{'>' if selected else ' '} {album}",
                fg=(0, 255, 0) if selected else (255, 255, 255)
            )

        console.print(
            2,
            27,
            f"Albums {start + 1}-{end} / {len(albums)}",
            fg=(128, 128, 128)
        )

        if self.current_album:
            console.print(
                40,
                5,
                f"Album: {self.current_album}",
                fg=(255, 165, 0)
            )

            track = Path(
                self.albums[self.current_album][
                    self.current_track_index
                ]
            ).name

            console.print(
                40,
                6,
                f"Track: {track}",
                fg=(173, 216, 230)
            )

            console.print(
                40,
                7,
                f"Track {self.current_track_index + 1}/{len(self.albums[self.current_album])}",
                fg=(180, 180, 180)
            )

        console.print(
            2,
            48,
            "UP/DOWN Scroll | PgUp/PgDn Page | ENTER Play | N Next | S Stop | ESC Exit",
            fg=(128, 128, 128)
        )

    def handle_input(self, event):
        albums = list(self.albums.keys())

        if event.sym == tcod.event.KeySym.ESCAPE:
            return "exit"

        elif event.sym == tcod.event.KeySym.UP:

            if self.selected_album > 0:
                self.selected_album -= 1

            if self.selected_album < self.scroll_offset:
                self.scroll_offset = self.selected_album

        elif event.sym == tcod.event.KeySym.DOWN:

            if self.selected_album < len(albums) - 1:
                self.selected_album += 1

            if (
                self.selected_album
                >= self.scroll_offset + self.visible_rows
            ):
                self.scroll_offset += 1

        elif event.sym == tcod.event.KeySym.PAGEUP:

            self.selected_album = max(
                0,
                self.selected_album - self.visible_rows
            )

            self.scroll_offset = max(
                0,
                self.scroll_offset - self.visible_rows
            )

        elif event.sym == tcod.event.KeySym.PAGEDOWN:

            self.selected_album = min(
                len(albums) - 1,
                self.selected_album + self.visible_rows
            )

            self.scroll_offset = min(
                max(0, len(albums) - self.visible_rows),
                self.scroll_offset + self.visible_rows
            )

        elif event.sym in (
            tcod.event.KeySym.RETURN,
            tcod.event.KeySym.KP_ENTER,
        ):
            if albums:
                self.current_album = albums[
                    self.selected_album
                ]

                self.current_track_index = 0

                self.play_current()

        elif event.sym == tcod.event.KeySym.n:
            self.next_track()

        elif event.sym == tcod.event.KeySym.s:
            self.stop()

        elif event.sym == tcod.event.KeySym.MINUS:

            self.volume = max(
                0.0,
                self.volume - 0.1
            )

            print(
                f"Volume: {int(self.volume * 100)}%"
            )

        elif event.sym == tcod.event.KeySym.EQUALS:

            self.volume = min(
                1.0,
                self.volume + 0.1
            )

            print(
                f"Volume: {int(self.volume * 100)}%"
            )

        elif event.sym == tcod.event.KeySym.m:

            self.muted = not self.muted

            if self.muted:
                print("Muted")
            else:
                print("Unmuted")


def main():
    player = MusicPlayerScreen()
    player.scan_albums()

    console = tcod.console.Console(
        80,
        50,
        order="F"
    )

    tileset = tcod.tileset.load_tilesheet(
        "Haberdash_curses_12x12.png", 16, 16, tcod.tileset.CHARMAP_CP437
    )

    with tcod.context.new(
        columns=80,
        rows=50,
        title="Space Rogue Music",
        tileset=tileset
    ) as context:

        while True:
            player.draw(console)

            context.present(console)

            for event in tcod.event.wait():

                context.convert_event(event)

                if isinstance(
                    event,
                    tcod.event.Quit
                ):
                    player.stop()
                    raise SystemExit()

                if isinstance(
                    event,
                    tcod.event.KeyDown
                ):
                    result = player.handle_input(
                        event
                    )

                    if result == "exit":
                        player.stop()
                        raise SystemExit()


if __name__ == "__main__":
    main()