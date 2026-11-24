"""The rules of the simulated computer.

A Session owns one device and the networks it can reach, and implements
every action (connect, scan, probe, breach, login, open, ls, decrypt,
download, ...). Each action returns a list of Out lines; nothing is ever
printed, executed or sent anywhere real. terminal.py is the thin text layer
on top.

Connection states
    offline      -> ls / cd / cat work on the device's own files
    connected    -> network commands: scan inspect probe breach login open
    inside host  -> ls / cd / cat / decrypt / download act on the remote host
"""

from hacking.filesystem import (ADMIN, GUEST, NONE, USER, LEVEL_NAMES,
                                AccessDenied, FSError)
from hacking.output import (alert, dim, err, head, info, ok, out, warn)
from hacking.security import Trace

STARS = "*****"


def _stars(n):
    return STARS[:n] + "." * (5 - n)


def _fmt_size(n):
    return f"{n}B" if n < 1024 else f"{n / 1024:.1f}K"


class Session:
    def __init__(self, device, networks, mission=None):
        self.device = device
        self.networks = {n.address.lower(): n for n in networks}
        self.mission = mission
        self.traces = {}            # network address -> Trace (kept across reconnects)
        self.connection = None      # Network or None
        self.discovered = set()     # (address, host name)
        self.probed = set()
        self.grants = {}            # (address, host name) -> (level, username)
        self.open_host = None
        self.lockdown = False
        self.downloads = []         # (host name, path)
        self.commands_run = 0
        self.realtime = True        # trace creeps up with the clock while connected
        self.on_realtime_change = None
        self._idle = 0.0

    # ------------------------------------------------------------- helpers
    @property
    def trace(self):
        return self.traces.get(self.connection.address) if self.connection else None

    def peak_trace(self):
        return max([t.value for t in self.traces.values()] or [0])

    def level_of(self, host):
        level, _ = self.grants.get((self.connection.address, host.name), (NONE, None))
        return max(level, host.public_access)

    def user_of(self, host):
        _, user = self.grants.get((self.connection.address, host.name), (NONE, None))
        return user or ("guest" if host.public_access else None)

    def _emit(self, kind, **data):
        return self.mission.on_event(self, kind, data) if self.mission else []

    def _hit(self, amount, reason):
        """Raise the trace; handle lockdown. Returns lines."""
        lines = self.trace.add(amount, reason)
        if self.trace.locked and not self.lockdown:
            self.lockdown = True
            self.connection, self.open_host = None, None
            lines.append(alert("Remote security dropped your link. You are offline."))
            lines += self._emit("lockdown")
        return lines

    # ---------------------------------------------------- real-time trace
    def tick(self, seconds):
        """Advance the clock. While connected with real-time trace on, the
        trace rises +1 every net.trace_interval seconds (a fixed rate, so
        it is predictable). Returns lines to print (warnings, lockdown)."""
        if (not self.realtime or self.connection is None or self.lockdown
                or (self.mission and self.mission.finished)):
            return []
        self._idle += seconds
        lines = []
        while self.connection and self._idle >= self.connection.trace_interval:
            self._idle -= self.connection.trace_interval
            lines += [l for l in self._hit(1, "time online") if l.kind != "trace"]
        return lines

    def next_tick_in(self):
        """Seconds until the next +1 (None when no clock is running)."""
        if not self.realtime or self.connection is None or self.lockdown:
            return None
        return max(0.0, self.connection.trace_interval - self._idle)

    def set_realtime(self, value=None):
        if value is None:
            return [info(f"Real-time trace is {'ON' if self.realtime else 'OFF'}. "
                         "Use 'realtime on' or 'realtime off'.")]
        v = value.lower()
        if v not in ("on", "off"):
            return [err("Usage: realtime [on|off]")]
        self.realtime = v == "on"
        if self.on_realtime_change:
            self.on_realtime_change(self.realtime)
        return [ok(f"Real-time trace {'ON: the trace now rises while you are connected.' if self.realtime else 'OFF: the trace only rises from your actions.'}")]

    def _need_network(self, closed=True):
        if self.lockdown and self.connection is None:
            return [err("No connection. Remote security cut your link; "
                        "that network is now blocking you.")]
        if self.connection is None:
            return [err("Not connected. Use 'connect <network>' first.")]
        if closed and self.open_host is not None:
            return [err(f"You are inside {self.open_host.name}. "
                        "Use 'close' to return to the network first.")]
        return None

    def _host(self, name):
        host = self.connection.find(name)
        if host is None or (self.connection.address, host.name) not in self.discovered:
            return None, [err(f"Unknown host '{name}'. Use 'scan' to discover hosts.")]
        return host, None

    def _fs(self):
        if self.open_host:
            return self.open_host.filesystem, self.level_of(self.open_host), self.open_host
        return self.device.filesystem, ADMIN, None

    def _denied(self, host, exc, level):
        lines = [alert(f"ACCESS DENIED: {exc.path} needs {LEVEL_NAMES[exc.required]} "
                       f"clearance (you have {LEVEL_NAMES[level]}).")]
        if host is not None:
            lines += self._hit(host.restricted_penalty,
                               f"restricted access attempt: {host.name}:{exc.path}")
        return lines

    # ------------------------------------------------------------ network
    def connect(self, target=None):
        if target is None:
            lines = [head("Known networks:")]
            for label, addr in self.device.contacts:
                lines.append(out(f"  {addr:<14}{label}"))
            lines.append(dim("Usage: connect <address>"))
            return lines
        if self.connection:
            return [err(f"Already connected to {self.connection.address}. "
                        "Use 'disconnect' first.")]
        net = self.networks.get(target.lower())
        if net is None:
            return [err(f"Cannot reach '{target}': no route to host.")]
        if net.address in self.traces and self.traces[net.address].locked:
            return [alert(f"Connection refused: {net.address} has blacklisted you.")]
        self.traces.setdefault(net.address, Trace())
        self.connection = net
        self._idle = 0.0
        lines = [ok(f"Connected to {net.name} ({net.address}).")]
        lines += [info(b) for b in net.banner]
        t = self.trace
        if t.value:
            lines.append(warn(f"Remote logs still hold your earlier activity: trace {t.value}%."))
        if self.realtime:
            lines.append(warn(f"Real-time trace is ON: +1% every {net.trace_interval:g}s while connected."))
        lines.append(dim("Hint: 'scan' finds the systems on this network."))
        return lines + self._emit("connect", network=net.address)

    def disconnect(self):
        if self.connection is None:
            return [err("Not connected to any network.")]
        net, trace = self.connection, self.trace
        self.connection, self.open_host = None, None
        lines = [ok(f"Disconnected from {net.address}. Link closed cleanly."),
                 dim(f"Final trace on {net.address}: {trace.value}% ({trace.level}).")]
        return lines + self._emit("disconnect", network=net.address)

    def scan(self):
        bad = self._need_network()
        if bad:
            return bad
        net = self.connection
        first = not any(a == net.address for a, _ in self.discovered)
        lines = []
        if first:
            lines.append(info(f"Scanning {net.address} ..."))
        for h in net.hosts:
            self.discovered.add((net.address, h.name))
        lines.append(head(f"  {'HOST':<12}{'ADDRESS':<12}{'SEC':<7}SERVICES"))
        for h in net.hosts:
            lines.append(out(f"  {h.name:<12}{h.address:<12}{_stars(h.security):<7}"
                             f"{', '.join(h.services)}"))
        lines.append(dim(f"{len(net.hosts)} systems found. 'inspect <host>' for details."))
        if first:
            lines += self._hit(net.scan_cost, "network scan is noisy")
        else:
            lines.append(dim("(cached result: no new noise)"))
        return lines + self._emit("scan", network=net.address)

    def inspect(self, name):
        bad = self._need_network()
        if bad:
            return bad
        host, bad = self._host(name)
        if bad:
            return bad
        key = (self.connection.address, host.name)
        lines = [head(f"{host.name} ({host.address})"),
                 out(f"  {host.description}"),
                 out(f"  OS        {host.os}"),
                 out(f"  Security  {_stars(host.security)} ({host.security}/5)"),
                 out(f"  Services  {', '.join(host.services) or 'none'}"),
                 out(f"  Your access  {LEVEL_NAMES[self.level_of(host)]}"
                     + (f" (as {self.user_of(host)})" if self.user_of(host) else ""))]
        if key in self.probed:
            n = len(host.vulnerabilities)
            lines.append(out(f"  Vulnerabilities  {n} known" if n else
                             "  Vulnerabilities  none found"))
        else:
            lines.append(dim("  Vulnerabilities  not probed yet"))
        return lines

    def probe(self, name):
        bad = self._need_network()
        if bad:
            return bad
        host, bad = self._host(name)
        if bad:
            return bad
        key = (self.connection.address, host.name)
        lines = []
        first = key not in self.probed
        if first:
            lines.append(info(f"Probing {host.name} services ..."))
        self.probed.add(key)
        if not host.vulnerabilities:
            lines.append(warn(f"{host.name}: no exploitable vulnerabilities found."))
        else:
            lines.append(head(f"{host.name}: {len(host.vulnerabilities)} vulnerabilities"))
            for v in host.vulnerabilities:
                lines.append(warn(f"  [{v.id}] {v.name}"))
                lines.append(out(f"      {v.description}"))
                if v.usage:
                    lines.append(dim("      use: " + v.usage.format(host=host.name)))
        if first:
            lines += self._hit(host.probe_cost, f"probing {host.name}")
        else:
            lines.append(dim("(cached result: no new noise)"))
        return lines + self._emit("probe", host=host.name)

    def _grant(self, host, level, user, via):
        self.grants[(self.connection.address, host.name)] = (level, user)
        return self._emit("access", host=host.name, level=level, user=user, via=via)

    def login(self, name, user, password):
        bad = self._need_network()
        if bad:
            return bad
        host, bad = self._host(name)
        if bad:
            return bad
        if not host.accounts:
            return [err(f"{host.name} offers no login service.")]
        acct = host.accounts.get(user)
        if acct and self.level_of(host) >= acct.level and self.user_of(host) == user:
            return [info(f"Already authenticated on {host.name} as {user}.")]
        if acct is None or acct.password != password:
            return ([err(f"Authentication failed for {user}@{host.name}.")]
                    + self._hit(host.login_penalty, f"failed login on {host.name}"))
        lines = [ok(f"Authenticated: {user}@{host.name} ({LEVEL_NAMES[acct.level]}).")]
        lines.append(dim(f"Use 'open {host.name}' to start a session."))
        return lines + self._grant(host, acct.level, user, "password")

    def breach(self, name, method=None, arg=None):
        bad = self._need_network()
        if bad:
            return bad
        host, bad = self._host(name)
        if bad:
            return bad
        key = (self.connection.address, host.name)
        if key not in self.probed:
            return [err(f"No known attack surface on {host.name}. Run 'probe {host.name}' first.")]
        if not host.vulnerabilities:
            return [err(f"{host.name} has no vulnerabilities to breach.")]
        if method is None:
            return [err(f"Usage: breach {host.name} <vulnerability-id> [argument]"),
                    dim("Known: " + ", ".join(v.id for v in host.vulnerabilities))]
        vuln = next((v for v in host.vulnerabilities if v.id == method.lower()), None)
        if vuln is None:
            return [err(f"'{method}' is not a known vulnerability of {host.name}.")]
        if self.level_of(host) >= vuln.grants and self.user_of(host):
            return [info(f"You already hold {LEVEL_NAMES[self.level_of(host)]} "
                         f"access on {host.name}.")]
        if vuln.challenge is not None:
            if not arg:
                return [err("This exploit needs an argument."),
                        dim("use: " + vuln.usage.format(host=host.name))]
            if not vuln.challenge.check(arg):
                return ([err(vuln.fail_text)]
                        + self._hit(vuln.trace_fail, f"failed exploit on {host.name}"))
        lines = [ok(vuln.success_text)]
        lines += self._hit(vuln.trace_success, f"exploiting protected system {host.name}")
        if self.lockdown:
            return lines
        lines.append(ok(f"Access granted: {vuln.account}@{host.name} "
                        f"({LEVEL_NAMES[vuln.grants]})."))
        lines.append(dim(f"Use 'open {host.name}' to start a session."))
        return lines + self._grant(host, vuln.grants, vuln.account, vuln.id)

    def open(self, name):
        bad = self._need_network()
        if bad:
            return bad
        host, bad = self._host(name)
        if bad:
            return bad
        if self.level_of(host) < GUEST:
            return ([alert(f"ACCESS DENIED: {host.name} requires authentication.")]
                    + self._hit(host.denied_penalty, f"unauthorized access attempt on {host.name}"))
        self.open_host = host
        host.filesystem.cwd_parts = []
        return [ok(f"Session opened on {host.name} as {self.user_of(host)} "
                   f"({LEVEL_NAMES[self.level_of(host)]})."),
                dim("Use 'ls', 'cd', 'cat'. 'close' returns to the network.")]

    def close(self):
        if self.open_host is None:
            return [err("No host session is open.")]
        name = self.open_host.name
        self.open_host = None
        return [info(f"Session on {name} closed.")]

    # --------------------------------------------------------- files
    def pwd(self):
        fs, _, host = self._fs()
        return [out(f"{host.name + ':' if host else ''}{fs.cwd}")]

    def ls(self, path="."):
        fs, level, host = self._fs()
        try:
            base, nodes = fs.listdir(path, level)
        except AccessDenied as e:
            return self._denied(host, e, level)
        except FSError as e:
            return [err(str(e))]
        if not nodes:
            return [dim("(empty)")]
        listing = fs.resolve(path, level)[0].is_dir
        lines = []
        for n in nodes:
            locked = n.min_access > level
            tag = f"[{LEVEL_NAMES[n.min_access]}]" if n.min_access > GUEST else ""
            if n.is_dir:
                row = f"  {n.name + '/':<28}{tag}"
            else:
                seal = " SEALED" if getattr(n, "sealed", False) else ""
                row = f"  {n.name:<28}{_fmt_size(n.size):>7} {tag}{seal}"
            kind = warn if locked else (info if n.is_dir else out)
            lines.append(kind(row.rstrip()))
            if host and not locked:
                full = base.rstrip("/") + "/" + n.name if listing else base
                lines += self._emit("view", host=host.name, path=full)
        return lines

    def cd(self, path="~"):
        fs, level, host = self._fs()
        try:
            fs.cd(path, level)
        except AccessDenied as e:
            return self._denied(host, e, level)
        except FSError as e:
            return [err(str(e))]
        return []

    def cat(self, path):
        fs, level, host = self._fs()
        try:
            node, abs_path = fs.resolve(path, level)
        except AccessDenied as e:
            return self._denied(host, e, level)
        except FSError as e:
            return [err(str(e))]
        if node.is_dir:
            return [err(f"{path} is a directory.")]
        lines = []
        if node.sealed:
            lines.append(warn("[SEALED] Ciphertext shown. Use 'decrypt' to unseal."))
        lines += [out(t) for t in node.text().split("\n")]
        if host:
            lines += self._emit("view", host=host.name, path=abs_path)
        return lines

    def decrypt(self, path, key=None):
        fs, level, host = self._fs()
        try:
            node, abs_path = fs.resolve(path, level)
        except AccessDenied as e:
            return self._denied(host, e, level)
        except FSError as e:
            return [err(str(e))]
        if node.is_dir:
            return [err(f"{path} is a directory.")]
        if not node.sealed:
            return [info(f"{node.name} is not encrypted.")]
        if key is None:
            return [head(f"{node.name}: sealed with a rotation cipher"),
                    out(f"  Text    {node.text()[:56].replace(chr(10), ' ')}{'...' if node.size > 56 else ''}"),
                    out("  Key     a shift from 1 to 25"),
                    dim(f"Usage: decrypt {path} <shift>. Wrong keys are logged!")]
        try:
            shift = int(key)
        except ValueError:
            return [err("The key must be a whole number from 1 to 25.")]
        if not 1 <= shift <= 25:
            return [err("The key must be a whole number from 1 to 25.")]
        if node.unseal(shift):
            lines = [ok(f"Checksum verified. {node.name} unsealed."),
                     dim(f"Use 'cat {path}' to read it.")]
            if host:
                lines += self._emit("decrypt", host=host.name, path=abs_path)
            return lines
        lines = [err(f"Checksum mismatch with shift {shift}."),
                 dim(f"Output would read: {node.preview(shift)!r}")]
        if host:
            lines += self._hit(node.unseal_penalty, f"failed unseal attempt on {node.name}")
        return lines

    def download(self, path):
        if self.open_host is None:
            return [err("Nothing to download from. Open a host session first.")]
        fs, level, host = self._fs()
        try:
            node, abs_path = fs.resolve(path, level)
        except AccessDenied as e:
            return self._denied(host, e, level)
        except FSError as e:
            return [err(str(e))]
        if node.is_dir:
            return [err(f"{path} is a directory; download files one at a time.")]
        if node.sealed:
            return [err(f"{node.name} is sealed. Sealed files cannot be extracted; decrypt it first.")]
        if (host.name, abs_path) in self.downloads:
            return [info(f"{node.name} was already extracted.")]
        self.downloads.append((host.name, abs_path))
        self.device.filesystem.put(self.device.download_dir, node.copy())
        lines = [ok(f"Extracted {node.name} ({_fmt_size(node.size)}) to {self.device.download_dir}/")]
        lines += self._hit(node.download_trace, f"data exfiltration: {node.name}")
        if self.lockdown:
            return lines
        return lines + self._emit("download", host=host.name, path=abs_path)

    # --------------------------------------------------------- status
    def status(self):
        t = self.trace
        lines = [head("== STATUS =="),
                 out(f"  Device    {self.device.name} ({self.device.username})")]
        if self.connection:
            lines.append(out(f"  Link      CONNECTED to {self.connection.address}"))
            host = self.open_host
            lines.append(out("  Host      " + (f"{host.name} as {self.user_of(host)} "
                                               f"({LEVEL_NAMES[self.level_of(host)]})"
                                               if host else "none (at network level)")))
        else:
            lines.append(out("  Link      OFFLINE" + (" (cut by remote security)"
                                                      if self.lockdown else "")))
        shown = t or (self.traces and max(self.traces.values(), key=lambda x: x.value))
        if shown:
            bar = "#" * (shown.pct // 5) + "-" * (20 - shown.pct // 5)
            kind = alert if shown.pct >= 75 else warn if shown.pct >= 25 else ok
            lines.append(kind(f"  Trace     [{bar}] {shown.value}% {shown.level}"))
        else:
            lines.append(ok("  Trace     [--------------------] 0% CLEAR"))
        lines.append(out(f"  Real-time {'ON' if self.realtime else 'off'}"))
        lines.append(out(f"  Extracted {len(self.downloads)} file(s)"))
        if self.mission:
            d, n = self.mission.progress()
            lines.append(out(f"  Mission   {self.mission.title}: {d}/{n} objectives"))
        return lines

    def mission_lines(self):
        m = self.mission
        if m is None:
            return [info("No active mission.")]
        d, n = m.progress()
        lines = [head(f"== {m.title.upper()} ({d}/{n}) ==")]
        lines += [out(b) for b in m.briefing]
        lines.append(out(""))
        for o in m.objectives:
            lines.append((ok if o.done else out)(f"  [{'x' if o.done else ' '}] {o.text}"))
        if m.finished:
            lines.append((ok if m.status == "success" else alert)(
                f"  Result: {m.status.upper()}"))
        return lines
