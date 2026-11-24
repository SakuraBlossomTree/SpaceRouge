"""One line of terminal output. `kind` decides the colour when drawn."""

from collections import namedtuple

Out = namedtuple("Out", "kind text")

# kinds: cmd (echoed input), out, info, ok, err, warn, alert, trace, dim, head


def out(text=""):
    return Out("out", text)


def info(text):
    return Out("info", text)


def ok(text):
    return Out("ok", text)


def err(text):
    return Out("err", text)


def warn(text):
    return Out("warn", text)


def alert(text):
    return Out("alert", text)


def dim(text):
    return Out("dim", text)


def head(text):
    return Out("head", text)


def trace_line(text):
    return Out("trace", text)
