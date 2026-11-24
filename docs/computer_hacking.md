# Computer / hacking subsystem (prototype v0.1)

Branch: `feature-computer-hacking`. Everything is simulated; nothing runs real
shell commands, subprocesses or network requests.

## Run it
    python src/main.py --hack         # in-game computer (ESC on the desktop returns to the title)
    python src/hacking/cli.py         # same engine in a plain terminal, no tcod
    python -m unittest tests.test_hacking -v

## Layout
| Path | Role |
|---|---|
| `src/hacking/` | Engine (no tcod, no game imports): filesystem, puzzles, trace, network data, mission, session rules, terminal parser, UI controller |
| `src/hacking/missions/` | Content. `corporate_archive.py` is the demo mission and the only story-specific file |
| `src/render/computer.py` | Drawing (desktop, terminal, files, mission, result) via `render/ui.py` |
| `src/core/computer_input.py` | tcod key glue; `game_state == "COMPUTER"` |
| `tests/test_hacking.py` | Automated tests |

Hooks in existing files: `core/events.py` (4 lines), `render/screen.py` and
`render_classic/screen.py` (5 lines each), `main.py` (`--hack`, 5 lines).

## Walkthrough: Corporate Archive Breach
    connect helix.net
    scan
    open gateway
    cat public/staff_directory.txt     (logins + pets)
    cat public/it_notice.txt           (password = <pet><year joined>)
    close
    login mail r.vance orbit2291
    open mail
    cat /spool/r.vance/archive_sync.log     (leaked session token)
    close
    probe archive-07
    breach archive-07 token-replay HX-7F3A-92C1
    open archive-07
    cd /vault
    cat README.txt                     (sealed files start with CLASSIFIED)
    decrypt lantern_dossier.sealed 11  (NWLDDTQTPO -> CLASSIFIED = shift 11)
    download lantern_dossier.sealed
    close
    disconnect

Loud shortcut: `breach archive-07 ftp-overflow` (+40 trace, skips the mail step).

## Trace costs (fixed, never random)
scan +3 (first time) · probe +1..4 (first time per host) · failed login +12 ·
open without access +10 · restricted path +5 · failed exploit +15 ·
successful exploit +10 (token) / +40 (overflow) · wrong decrypt key +8 ·
download classified +10. Warnings at 25 / 50 / 75, lockdown at 100.

## Adding things
* New mission: add a module in `hacking/missions/` that returns a `Session`; register it in `missions/__init__.py`.
* New device (home PC, ship, portable): another `Device` (files, contacts, `apps`); the engine is unchanged.
* New command: one row in `terminal.COMMANDS` + a `Session` method.
