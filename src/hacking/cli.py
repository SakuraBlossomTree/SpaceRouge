"""Play the hacking prototype in a plain terminal (no tcod needed).

    python src/hacking/cli.py            (or: cd src && python -m hacking.cli)
    python src/hacking/cli.py unsent_message     (pick a mission)

Useful for quick testing. The commands only drive the simulated session;
nothing is sent to the real shell or network.
"""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hacking import missions
from hacking.terminal import Terminal

COLORS = {"cmd": "37;1", "info": "36", "ok": "32", "err": "31", "warn": "33",
          "alert": "41;97", "trace": "38;5;208", "dim": "90", "head": "96;1"}


def main():
    session = missions.build(sys.argv[1] if len(sys.argv) > 1 else missions.DEFAULT)
    term = Terminal(session)
    tty = sys.stdout.isatty()

    def show(lines):
        for kind, text in lines:
            print(f"\033[{COLORS[kind]}m{text}\033[0m" if tty and kind in COLORS else text)

    show(term.log)
    show(session.mission_lines())
    while not term.exit_requested:
        try:
            line = input(term.prompt() + " ")
        except (EOFError, KeyboardInterrupt):
            break
        show(term.execute(line)[1:])
        if session.mission and session.mission.finished:
            print(session.mission.result)
            break


if __name__ == "__main__":
    main()
