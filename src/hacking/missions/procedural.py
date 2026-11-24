"""Procedural data-heist jobs: a seed in, a complete Session out.

A job id looks like "job:<tier>:<seed>" (see hacking/missions/__init__.py).
The same id always builds the same network, so nothing needs saving.

    tier 1  the gateway's public ops log leaks a session token
    tier 2  staff directory + IT notice -> guess a mail password -> the
            mailbox log leaks the token

Both then: probe the vault host -> breach token-replay <token> -> open it ->
read the README (the header word is the crib for the rotation cipher) ->
decrypt -> download -> close -> disconnect. A loud ftp-overflow shortcut
exists on every vault (+40 trace).
"""

import random

from hacking.filesystem import ADMIN, GUEST, USER, Directory, File, FileSystem
from hacking.mission import Mission, Objective
from hacking.network import Account, Device, Host, Network, Vulnerability
from hacking.puzzles import SecretChallenge
from hacking.session import Session

PREFIX = "job"

FIRST = ["Vantor", "Kestrel", "Orsino", "Halvard", "Mirelle", "Tessaly", "Draven",
         "Ostrel", "Brannock", "Calloway", "Ferrow", "Ilyra", "Navarre", "Quillon"]
LAST = ["Freight", "Dynamics", "Combine", "Logistics", "Mutual", "Holdings",
        "Cartel", "Extraction", "Assembly", "Syndicate"]
STAFF = [("a.lindqvist", "Lindqvist"), ("d.okonkwo", "Okonkwo"), ("s.varga", "Varga"),
         ("j.moreau", "Moreau"), ("k.tanaka", "Tanaka"), ("p.haldane", "Haldane")]
PETS = ["miso", "pixel", "rocket", "juno", "tango", "willow", "bolt", "ember", "kiwi", "sable"]
KINDS = [
    ("manifest", "Cargo Manifest", "cargo manifest", "manifest",
     "the real cargo manifest, the one that shows what {co} actually hauls"),
    ("ledger", "Ledger Audit", "off-book ledger", "ledger",
     "the off-book ledger {co} keeps for its backers"),
    ("roster", "Crew Roster", "crew roster", "roster",
     "the sealed crew roster, including contractors {co} never declares"),
    ("route", "Route Plans", "route plans", "routes",
     "the unreleased route plans {co} sells to its best customers"),
]


def make_id(tier, seed):
    return f"{PREFIX}:{int(tier)}:{int(seed)}"


def parse_id(mission_id):
    p, tier, seed = mission_id.split(":")
    if p != PREFIX:
        raise KeyError(mission_id)
    return int(tier), int(seed)


def is_job(mission_id):
    return isinstance(mission_id, str) and mission_id.startswith(PREFIX + ":")


def describe(tier, seed):
    """(title, company, short description) without building the network."""
    rng = random.Random(seed)
    co = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    kind = KINDS[rng.randrange(len(KINDS))]
    return f"{kind[1]}: {co}", co, kind[4].format(co=co)


def _spec(tier, seed):
    rng = random.Random(seed)
    co = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    kind = KINDS[rng.randrange(len(KINDS))]
    slug = co.split()[0].lower()
    staff = rng.sample(STAFF, 3)
    pets = rng.sample(PETS, 3)
    years = [rng.randint(2280, 2297) for _ in range(3)]
    return {
        "co": co, "kind": kind, "slug": slug, "net": f"{slug}.net",
        "vault": f"vault-{rng.randint(10, 99)}",
        "token": f"{slug[:2].upper()}-{rng.randrange(16**4):04X}-{rng.randrange(16**4):04X}",
        "shift": rng.randint(3, 22), "staff": staff, "pets": pets, "years": years,
        "who": rng.randrange(3), "tier": tier,
    }


def _device(sp):
    home = Directory("pilot", [
        File("briefing.txt",
             f"CLIENT BRIEF (anonymous broker)\n"
             f"{sp['co']} keeps {sp['kind'][4].format(co=sp['co'])} on a sealed host.\n"
             f"Get in, unseal it, pull it, and get out before their security trace\n"
             f"finishes tracing you.\nEntry point: {sp['net']}"),
        File("contacts.txt", f"{sp['net']}   {sp['co']} gateway (target)"),
        Directory("downloads"),
    ])
    fs = FileSystem(Directory("", [Directory("home", [home])]), home="/home/pilot")
    fs.cwd_parts = ["home", "pilot"]
    return Device(id="field-slate", name="Field Slate", kind="mission_terminal",
                  username="pilot", os_name="SR-OS 0.1", filesystem=fs,
                  contacts=[(f"{sp['co']} gateway (target)", sp["net"])])


def _log(sp):
    return ("[2291-11-02 03:00] sync: nightly job started\n"
            "[2291-11-02 03:00] auth-daemon: handshake ok, svc-archiver\n"
            f"[2291-11-02 03:01] auth-daemon: session token {sp['token']}\n"
            "[2291-11-02 03:01] WARNING: token not bound to client address\n"
            "                   (replay possible, ticket still open)\n"
            "[2291-11-02 03:09] sync complete")


def _gateway(sp):
    public = [File("welcome.txt", f"Welcome to the {sp['co']} public gateway.")]
    if sp["tier"] <= 1:
        public.append(File("ops_log.txt", "OPS LOG (public mirror, misconfigured)\n" + _log(sp)))
    else:
        rows = "\n".join(f"  {l:<12}{n}" for (l, n) in
                         ((s[0], s[1]) for s in sp["staff"]))
        pets = "\n".join(f"  {s[1]} .... {p} (pet)" for s, p in zip(sp["staff"], sp["pets"]))
        yrs = "\n".join(f"  {s[0]:<12}joined {y}" for s, y in zip(sp["staff"], sp["years"]))
        public += [
            File("staff_directory.txt",
                 f"{sp['co'].upper()} STAFF (public extract)\n{rows}\n{yrs}\n\n"
                 f"OFFICE PET DAY ROSTER\n{pets}"),
            File("it_notice.txt",
                 "IT NOTICE\nStaff mail passwords follow one format:\n"
                 "  <pet name in lower case><year you joined>\nRotate within 30 days."),
        ]
    fs = Directory("", [Directory("public", public)])
    return Host("gateway", "10.4.0.1", f"Public portal for {sp['co']}.", os="HX-Linux 4",
                security=1, services=["https/443"], filesystem=FileSystem(fs),
                public_access=GUEST, probe_cost=1)


def _mail(sp):
    w = sp["who"]
    login = sp["staff"][w][0]
    fs = Directory("", [Directory("spool", [
        Directory(login, [File("inbox.txt", "Subject: reminder\nPlease rotate your password."),
                          File("archive_sync.log", _log(sp))]),
    ])])
    pw = f"{sp['pets'][w]}{sp['years'][w]}"
    return Host("mail", "10.4.0.12", "Staff mail relay.", os="HX-Linux 4", security=2,
                services=["smtp/25", "imap/143"],
                accounts={login: Account(login, pw, USER)},
                filesystem=FileSystem(fs), probe_cost=4)


def _vault(sp):
    kind = sp["kind"]
    fname = f"{kind[3]}.sealed"
    fs = Directory("", [
        Directory("vault", [
            File("README.txt",
                 "VAULT POLICY\nSealed documents use a rotation cipher (shift 1-25) and\n"
                 "always begin with the standard header word CLASSIFIED.\n"
                 "Failed unseal attempts are logged.", min_access=USER),
            File(fname,
                 f"CLASSIFIED // {sp['co'].upper()}\n{kind[2].upper()}\n"
                 f"Prototype placeholder text for {kind[2]}.\n"
                 "Nothing here is real; the credits are.",
                 min_access=USER, cipher_shift=sp["shift"], classified=True,
                 unseal_penalty=8, download_trace=10),
        ], min_access=USER),
        Directory("admin", [File("core.cfg", "[core settings]")], min_access=ADMIN),
    ])
    vulns = [
        Vulnerability(
            "token-replay", "Session token replay",
            "auth-daemon accepts a captured session token from any address.",
            usage="breach {host} token-replay <token>",
            challenge=SecretChallenge(sp["token"], case_sensitive=False),
            account="svc-archiver", grants=USER, trace_success=10, trace_fail=15,
            success_text="Token accepted. auth-daemon trusts the replayed session.",
            fail_text="auth-daemon rejected the token."),
        Vulnerability(
            "ftp-overflow", "vault-ftp buffer overflow",
            "Crashes the FTP daemon into a root-less shell. Extremely loud.",
            usage="breach {host} ftp-overflow",
            account="ftp-shell", grants=USER, trace_success=40,
            success_text="Overflow succeeded. vault-ftp spawned a shell."),
    ]
    return (Host(sp["vault"], "10.4.0.77", "Sealed document store.", os="VAULT-OS",
                 security=4, services=["vault-ftp/990", "auth-daemon/7007"],
                 vulnerabilities=vulns, filesystem=FileSystem(fs), probe_cost=4),
            "/vault/" + fname)


def _rate(session, won):
    if not won:
        return "F - Detected"
    t = session.peak_trace()
    return "S - Ghost" if t <= 35 else "A - Quiet" if t <= 60 else "B - Loud"


def build(mission_id):
    tier, seed = parse_id(mission_id)
    sp = _spec(tier, seed)
    vault, path = _vault(sp)
    hosts = [_gateway(sp)] + ([_mail(sp)] if tier >= 2 else []) + [vault]

    def ev(kind, **want):
        return lambda s, k, i: k == kind and all(i.get(a) == b for a, b in want.items())

    objectives = [
        Objective("connect", f"Connect to the {sp['co']} network ({sp['net']})",
                  ev("connect", network=sp["net"])),
        Objective("scan", "Scan the network for systems", ev("scan")),
        Objective("probe", "Find a vulnerability on the vault server", ev("probe", host=vault.name)),
        Objective("access", "Gain access to the vault server",
                  lambda s, k, i: k == "access" and i["host"] == vault.name and i["level"] >= USER),
        Objective("decrypt", "Decrypt the document", ev("decrypt", host=vault.name, path=path)),
        Objective("download", "Download the document", ev("download", host=vault.name, path=path)),
        Objective("exit", "Disconnect before the trace hits 100%",
                  lambda s, k, i: k == "disconnect" and not s.lockdown
                  and all(o.done for o in s.mission.objectives if o.id != "exit")),
    ]
    title, _, _ = describe(tier, seed)
    mission = Mission(
        id=mission_id, title=title,
        briefing=[f"A broker wants {sp['kind'][4].format(co=sp['co'])}.",
                  "Infiltrate the network, unseal the file, download it, and",
                  "disconnect before the security trace reaches 100%."],
        objectives=objectives,
        success_text="Clean exit. The broker will pay on delivery.",
        failure_text="Security traced you and cut the link. The file stays sealed.",
        rate=_rate)
    net = Network(sp["net"], f"{sp['co']} Secure Network",
                  banner=[f"{sp['co'].upper()} SECURE GATEWAY",
                          "All access is logged. Unauthorized activity will be traced."],
                  hosts=hosts)
    return Session(_device(sp), [net], mission)


def solution(mission_id):
    """The intended command list (used by tests)."""
    tier, seed = parse_id(mission_id)
    sp = _spec(tier, seed)
    vault, path = _vault(sp)
    name = path.rsplit("/", 1)[1]
    cmds = [f"connect {sp['net']}", "scan"]
    if tier <= 1:
        cmds += ["open gateway", "cd /public", "cat ops_log.txt", "close"]
    else:
        w = sp["who"]
        login = sp["staff"][w][0]
        cmds += ["open gateway", "cd /public", "cat staff_directory.txt", "cat it_notice.txt",
                 "close", f"login mail {login} {sp['pets'][w]}{sp['years'][w]}", "open mail",
                 f"cat /spool/{login}/archive_sync.log", "close"]
    cmds += [f"probe {vault.name}", f"breach {vault.name} token-replay {sp['token']}",
             f"open {vault.name}", "cd /vault", "cat README.txt",
             f"decrypt {name} {sp['shift']}", f"download {name}", "close", "disconnect"]
    return cmds
