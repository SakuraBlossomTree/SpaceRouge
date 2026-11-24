"""SpaceRouge computer / hacking subsystem (prototype v0.1).

A self-contained, fully simulated computer: filesystem, networks, security
trace, hacking challenges and missions. Nothing in here touches the real
operating system or the real network, and nothing imports tcod or the rest
of the game, so it can be tested (and played, see cli.py) on its own.

Layers, bottom to top:

    output.py      Out(kind, text) - one line of terminal output
    filesystem.py  simulated files / directories / access levels
    puzzles.py     ciphers and secret-checking challenges
    security.py    the trace meter (warnings + lockdown)
    network.py     Host / Network / Vulnerability / Account data classes
    mission.py     Objective + Mission (win / fail tracking)
    session.py     the rules: connect, scan, probe, breach, open, ls, ...
    terminal.py    command parser, history, completion, help
    computer.py    desktop / apps UI controller (no drawing, no tcod)
    missions/      content: one module per mission (+ its device)

Drawing lives in render/computer.py, key handling in core/computer_input.py.
"""
