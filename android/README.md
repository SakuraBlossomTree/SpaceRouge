# SpaceRouge - Mobile (pygame / Android)

A separate build of SpaceRouge that runs on **pygame** instead of python-tcod,
with touch controls, so it can be packaged as an Android APK.

The game itself is the same code as the desktop version:

| Folder      | What it is                                                         |
| ----------- | ------------------------------------------------------------------ |
| `core/`     | Game logic, copied from the desktop game (world, economy, missions, input...) |
| `render/`   | All the screens, copied from the desktop game                      |
| `effects/`  | Combat and star effects, copied from the desktop game              |
| `tcod/`     | A small stand-in for python-tcod (console, events) so the code above runs unchanged |
| `mobile/`   | pygame-only parts: renderer, touch controls, keyboard mapping, main loop |
| `assets/`   | Fonts (DejaVu Sans Mono tilesheets in 5 sizes + the classic pixel font) |
| `sfx/`      | Music and sound effects                                             |

Only two `core/` files differ from the desktop game: `core/audio.py` (uses
`pygame.mixer`, still with separate music and sound-effect channels) and
`core/fonts.py` (font presets without tcod). `UI_TOGGLE` is off - the
mobile build has only the modern UI.

## Run it on your PC first

Double-click **`run_on_pc.bat`**. The first time it creates a `.venv` and
installs pygame-ce + numpy; after that it just starts the game in a window
with the touch panels (click them with the mouse; the keyboard works too).

From a terminal you can also pass options:

```bat
run_on_pc.bat --keyboard      :: no touch panels
run_on_pc.bat --seed 12345    :: a specific galaxy
```

## Touch controls

The game fills the whole screen (about 46 rows of text: a 1080p phone gets
16x23 px cells) and the controls float on top, see-through:

* **Left:** D-pad (hold to keep flying), **OK** (= Enter) and **Back** (= Esc).
* **Right, top:** icons - **Galaxy** map, **Contracts**, **Cargo**,
  **Exchange**, **Log**, **Help**. The one for the open screen is highlighted;
  tap it again to close.
* **Right, middle:** status - hull and fuel bars, credits, cargo, day, next
  loan payment, and where you are / what's in range.
* **Right, bottom:** buttons for the current screen - Dock / Scan on the map,
  Buy / Sell in the market, Accept on the missions board, Zoom / Routes on the
  galaxy chart, and so on.
* New messages pop up at the bottom for a few seconds.
* **Tap the map** in a star system to fly one step toward that spot. The
  system map scrolls up and down to follow your ship.
* The Android **back button** works as Esc.

On the title screen, **Buttons NN%** changes how see-through the controls
are (saved). The game is landscape-only.

## Build the APK on Windows

Buildozer (the APK builder) only runs on Linux, so on Windows it runs inside
**WSL** - Microsoft's built-in Linux. You set that up once:

1. Open **PowerShell as Administrator** and run: `wsl --install -d Ubuntu`
2. **Restart** the laptop. Ubuntu opens by itself - choose a username and password.
   (If it complains about virtualization, enable it in the BIOS/UEFI settings.)

Then, every time you want an APK:

3. Double-click **`build_apk.bat`**.

The first run installs the build tools (it asks for the Ubuntu password you
picked), then downloads the Android SDK/NDK and compiles Python, SDL2, pygame
and numpy for Android. That takes **30-60 minutes** and about **10 GB** of
disk. Later builds take a few minutes. When it finishes, the APK is copied to
`android\bin\` and that folder opens.

The project is copied to `~/spacerouge-android` inside Ubuntu and built
there - building straight from the Windows drive is very slow.

### Put it on your phone

* **Easiest:** copy the `.apk` from `android\bin\` to the phone (USB, Google
  Drive, ...), open it, and allow "install unknown apps" when asked.
* **With a cable:** enable *Developer options -> USB debugging* on the phone,
  install [Android platform-tools](https://developer.android.com/tools/releases/platform-tools)
  on Windows, then `adb install -r android\bin\spacerouge-0.1-*-debug.apk`.

### Building by hand (Linux / macOS / inside WSL)

```bash
bash tools/wsl_build.sh "$(pwd)"      # same script build_apk.bat uses
# or, with buildozer already installed:
buildozer android debug
```

For a Play Store release use `buildozer android release` and sign the AAB.

## Keeping it in sync with the desktop game

`core/`, `render/` and `effects/` are copies. After changing the desktop
game, copy those folders over again - but keep this build's own
`core/audio.py` and `core/fonts.py`, and leave `UI_TOGGLE = False` in
`core/state.py`.

## Fonts

`tools/make_font.py` builds the font tilesheets from
`assets/fonts/DejaVuSansMono.ttf`. The renderer looks for the sizes listed in
`SHEETS` in `mobile/presenter.py`.
