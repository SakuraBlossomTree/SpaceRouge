"""Tileset references. The pygame presenter turns these into glyph atlases."""

CHARMAP_CP437 = "cp437"


class Tileset:
    def __init__(self, path, columns=16, rows=16, family=None):
        self.path = str(path)
        self.columns = columns
        self.rows = rows
        self.family = family     # e.g. "sans": presenter picks the best size


def load_tilesheet(path, columns, rows, charmap=CHARMAP_CP437, family=None):
    return Tileset(path, columns, rows, family)
