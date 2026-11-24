"""Simulated filesystem with access levels.

Every node has a `min_access`; a path is only reachable if every directory
on the way and the node itself are within the caller's access level.
Nothing here touches the real disk.
"""

from hacking.puzzles import caesar

NONE, GUEST, USER, ADMIN = range(4)
LEVEL_NAMES = ("none", "guest", "user", "admin")


class FSError(Exception):
    pass


class AccessDenied(FSError):
    def __init__(self, path, required):
        super().__init__(f"access denied: {path}")
        self.path = path
        self.required = required


class Node:
    is_dir = False

    def __init__(self, name, min_access=GUEST):
        self.name = name
        self.min_access = min_access


class File(Node):
    """A file. With cipher_shift set the file is stored sealed (rotation
    cipher) until unseal() is called with the right shift."""

    def __init__(self, name, content="", *, min_access=GUEST, cipher_shift=None,
                 classified=False, unseal_penalty=8, download_trace=1):
        super().__init__(name, min_access)
        self.content = content          # always the plain text
        self.cipher_shift = cipher_shift
        self.unsealed = cipher_shift is None
        self.classified = classified
        self.unseal_penalty = unseal_penalty
        self.download_trace = download_trace

    @property
    def sealed(self):
        return not self.unsealed

    @property
    def size(self):
        return len(self.content)

    def text(self):
        """What a reader sees: ciphertext while sealed, plain text after."""
        return caesar(self.content, self.cipher_shift) if self.sealed else self.content

    def preview(self, shift, n=30):
        """First n characters of the ciphertext rotated back by `shift`."""
        return caesar(self.text(), -shift)[:n]

    def unseal(self, shift):
        if self.sealed and shift == self.cipher_shift:
            self.unsealed = True
        return self.unsealed

    def copy(self):
        return File(self.name, self.content, min_access=GUEST,
                    classified=self.classified)


class Directory(Node):
    is_dir = True

    def __init__(self, name, children=(), *, min_access=GUEST):
        super().__init__(name, min_access)
        self.children = {}
        for c in children:
            self.add(c)

    def add(self, node):
        self.children[node.name] = node
        return node


class FileSystem:
    def __init__(self, root=None, home="/"):
        self.root = root or Directory("")
        self.home = home
        self.cwd_parts = []

    # --- paths -------------------------------------------------------------
    def _parts(self, path):
        if path == "~" or path.startswith("~/"):
            path = self.home.rstrip("/") + path[1:]
        parts = [] if path.startswith("/") else list(self.cwd_parts)
        for p in path.split("/"):
            if p in ("", "."):
                continue
            if p == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(p)
        return parts

    @property
    def cwd(self):
        return "/" + "/".join(self.cwd_parts)

    def display_cwd(self):
        home = self.home.rstrip("/")
        if home and (self.cwd == home or self.cwd.startswith(home + "/")):
            return "~" + self.cwd[len(home):]
        return self.cwd

    def resolve(self, path, level=ADMIN):
        """-> (node, absolute path). Raises FSError / AccessDenied."""
        node, walked = self.root, ""
        for p in self._parts(path):
            if not node.is_dir:
                raise FSError(f"not a directory: {walked or '/'}")
            if node.min_access > level:
                raise AccessDenied(walked or "/", node.min_access)
            child = node.children.get(p)
            if child is None:
                raise FSError(f"no such file or directory: {path}")
            node, walked = child, walked + "/" + p
        if node.min_access > level:
            raise AccessDenied(walked or "/", node.min_access)
        return node, walked or "/"

    # --- operations --------------------------------------------------------
    def listdir(self, path=".", level=ADMIN):
        """-> (abs path, [nodes]) dirs first, then files, each sorted."""
        node, abs_path = self.resolve(path, level)
        if not node.is_dir:
            return abs_path, [node]
        kids = sorted(node.children.values(), key=lambda n: (not n.is_dir, n.name))
        return abs_path, kids

    def cd(self, path, level=ADMIN):
        node, _ = self.resolve(path, level)
        if not node.is_dir:
            raise FSError(f"not a directory: {path}")
        self.cwd_parts = self._parts(path)

    def put(self, dir_path, node):
        """Create the directory chain if needed and store node in it."""
        cur = self.root
        for p in self._parts(dir_path):
            nxt = cur.children.get(p)
            if nxt is None or not nxt.is_dir:
                nxt = cur.add(Directory(p))
            cur = nxt
        cur.add(node)
        return node
