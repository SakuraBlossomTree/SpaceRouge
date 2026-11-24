"""In-game terminal: parses a command line and calls the Session.

The command line is only ever *parsed*. Nothing typed here is passed to the
real operating system, a subprocess or the network.
"""

import difflib
import shlex

from hacking.output import Out, dim, err, head, info, out

MAX_LOG = 1000
MAX_HISTORY = 100

# name: (usage, summary, where)   where: any | net | host
COMMANDS = {
    "help":       ("help [command]", "Show commands, or details for one", "any"),
    "clear":      ("clear", "Clear the terminal output", "any"),
    "status":     ("status", "Connection, access and security trace", "any"),
    "mission":    ("mission", "Show the mission briefing and objectives", "any"),
    "connect":    ("connect [address]", "Connect to a network (no argument: list known)", "any"),
    "scan":       ("scan", "Discover the systems on the network", "net"),
    "inspect":    ("inspect <host>", "Show a discovered system's details", "net"),
    "probe":      ("probe <host>", "Look for vulnerabilities (noisy the first time)", "net"),
    "breach":     ("breach <host> <vuln-id> [arg]", "Exploit a vulnerability to bypass security", "net"),
    "login":      ("login <host> <user> <password>", "Authenticate with credentials", "net"),
    "open":       ("open <host>", "Open a session on a host you can access", "net"),
    "close":      ("close", "Close the host session, back to the network", "host"),
    "ls":         ("ls [path]", "List files and directories", "any"),
    "cd":         ("cd [path]", "Change directory", "any"),
    "pwd":        ("pwd", "Show the current directory", "any"),
    "cat":        ("cat <file>", "Read a file", "any"),
    "decrypt":    ("decrypt <file> [shift]", "Unseal an encrypted file", "any"),
    "download":   ("download <file>", "Extract a file from the host to this device", "host"),
    "disconnect": ("disconnect", "End the network connection", "net"),
    "realtime":   ("realtime [on|off]", "Show or set real-time trace creep", "any"),
    "exit":       ("exit", "Close the host session, or leave the terminal", "any"),
}
ALIASES = {"?": "help", "cls": "clear", "dir": "ls", "type": "cat", "dl": "download",
           "quit": "exit", "bye": "disconnect"}

# (min, max) argument counts; commands not listed take none
ARG_COUNT = {"help": (0, 1), "connect": (0, 1), "inspect": (1, 1), "probe": (1, 1),
             "breach": (1, 3), "login": (3, 3), "open": (1, 1), "ls": (0, 1),
             "cd": (0, 1), "realtime": (0, 1), "cat": (1, 1), "decrypt": (1, 2), "download": (1, 1)}

HOST_ARG = {"inspect", "probe", "breach", "login", "open"}
PATH_ARG = {"ls", "cd", "cat", "decrypt", "download"}


class Terminal:
    def __init__(self, session):
        self.session = session
        self.log = []
        self.history = []
        self.exit_requested = False
        self.print(info(f"{session.device.os_name} terminal. Type 'help' for commands."))
        if session.mission:
            self.print(dim("Type 'mission' to review your objective."))

    # ----------------------------------------------------------- output
    def print(self, *lines):
        self.log.extend(lines)
        del self.log[:-MAX_LOG]

    def prompt(self):
        s = self.session
        user = s.device.username
        if s.open_host:
            return f"{s.user_of(s.open_host)}@{s.open_host.name}:{s.open_host.filesystem.display_cwd()}$"
        return f"{user}@local:{s.device.filesystem.display_cwd()}$"

    # ---------------------------------------------------------- execute
    def execute(self, line):
        """Run one command line. Returns the new output lines."""
        start = len(self.log)
        self.print(Out("cmd", f"{self.prompt()} {line}"))
        if line.strip():
            if not self.history or self.history[-1] != line:
                self.history.append(line)
                del self.history[:-MAX_HISTORY]
            self.session.commands_run += 1
            self._run(line)
        new = self.log[start:] if len(self.log) >= start else self.log[:]
        return new

    def _run(self, line):
        try:
            words = shlex.split(line)
        except ValueError:
            self.print(err("Parse error: unbalanced quotes."))
            return
        name, args = words[0].lower(), words[1:]
        name = ALIASES.get(name, name)
        if name not in COMMANDS:
            self.print(err(f"Unknown command '{words[0]}'."))
            close = difflib.get_close_matches(name, COMMANDS, n=1)
            self.print(dim(f"Did you mean '{close[0]}'?" if close
                           else "Type 'help' for the list of commands."))
            return
        lo, hi = ARG_COUNT.get(name, (0, 0))
        if len(args) < lo:
            self.print(err(f"Usage: {COMMANDS[name][0]}"))
            return
        if len(args) > hi:
            self.print(err(f"Too many arguments. Usage: {COMMANDS[name][0]}"))
            return
        s = self.session
        a = args
        if name == "help":
            lines = self._help(a[0] if a else None)
        elif name == "clear":
            self.log.clear()
            return
        elif name == "status":
            lines = s.status()
        elif name == "mission":
            lines = s.mission_lines()
        elif name == "connect":
            lines = s.connect(a[0] if a else None)
        elif name == "scan":
            lines = s.scan()
        elif name == "inspect":
            lines = s.inspect(a[0])
        elif name == "probe":
            lines = s.probe(a[0])
        elif name == "breach":
            lines = s.breach(a[0], a[1] if len(a) > 1 else None, a[2] if len(a) > 2 else None)
        elif name == "login":
            lines = s.login(a[0], a[1], a[2])
        elif name == "open":
            lines = s.open(a[0])
        elif name == "close":
            lines = s.close()
        elif name == "ls":
            lines = s.ls(a[0] if a else ".")
        elif name == "cd":
            lines = s.cd(a[0] if a else "~")
        elif name == "pwd":
            lines = s.pwd()
        elif name == "cat":
            lines = s.cat(a[0])
        elif name == "decrypt":
            lines = s.decrypt(a[0], a[1] if len(a) > 1 else None)
        elif name == "download":
            lines = s.download(a[0])
        elif name == "realtime":
            lines = s.set_realtime(a[0] if a else None)
        elif name == "disconnect":
            lines = s.disconnect()
        else:  # exit
            if s.open_host:
                lines = s.close()
            else:
                self.exit_requested = True
                lines = []
        self.print(*lines)

    def _available(self, where):
        s = self.session
        if where == "any":
            return True
        if where == "net":
            return s.connection is not None and s.open_host is None
        return s.open_host is not None

    def _help(self, topic):
        if topic:
            topic = ALIASES.get(topic.lower(), topic.lower())
            if topic not in COMMANDS:
                return [err(f"No help for '{topic}'.")]
            usage, summary, where = COMMANDS[topic]
            need = {"any": "", "net": "Needs: a network connection (not inside a host).",
                    "host": "Needs: an open host session."}[where]
            return [head(usage), out("  " + summary)] + ([dim("  " + need)] if need else [])
        lines = [head("Commands (dim = not usable in the current state):")]
        for name, (usage, summary, where) in COMMANDS.items():
            row = f"  {usage:<34}{summary}"
            lines.append(out(row) if self._available(where) else dim(row))
        lines.append(dim("Tab completes, Up/Down recalls history, PgUp/PgDn scrolls."))
        return lines

    # ------------------------------------------------------- completion
    def complete(self, line):
        """Tab completion for the command or its last argument."""
        words = line.split(" ")
        if len(words) == 1:
            return self._expand(line, list(COMMANDS) + list(ALIASES))
        cmd = ALIASES.get(words[0].lower(), words[0].lower())
        s, prefix, idx = self.session, words[-1], len(words) - 1
        cands = []
        if cmd == "connect" and idx == 1:
            cands = [a for _, a in s.device.contacts]
        elif cmd in HOST_ARG and idx == 1 and s.connection:
            cands = [h.name for h in s.connection.hosts
                     if (s.connection.address, h.name) in s.discovered]
        elif cmd == "breach" and idx == 2 and s.connection:
            host = s.connection.find(words[1])
            cands = [v.id for v in host.vulnerabilities] if host else []
        elif cmd in PATH_ARG and idx == 1:
            fs, level, _ = s._fs()
            head_part, _, tail = prefix.rpartition("/")
            try:
                node, _ = fs.resolve(head_part + "/" if head_part or prefix.startswith("/") else ".", level)
                cands = [(head_part + "/" if head_part or prefix.startswith("/") else "") + n.name
                         + ("/" if n.is_dir else "") for n in node.children.values()] if node.is_dir else []
            except Exception:
                cands = []
        return " ".join(words[:-1] + [self._expand(prefix, cands)])

    @staticmethod
    def _expand(prefix, cands):
        matches = sorted({c for c in cands if c.lower().startswith(prefix.lower())})
        if not matches:
            return prefix
        if len(matches) == 1:
            return matches[0]
        common = matches[0]
        for m in matches[1:]:
            while not m.lower().startswith(common.lower()):
                common = common[:-1]
        return common if len(common) > len(prefix) else prefix
