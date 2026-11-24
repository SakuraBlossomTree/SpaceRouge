"""Hacking puzzles: a rotation cipher and secret-checking challenges.

Challenges are deliberately tiny and deterministic: a puzzle is solved by
supplying the right answer, found by reading the in-game files. No randomness.
"""


def caesar(text, shift):
    """Rotate letters by `shift` (case kept, everything else untouched)."""
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
        elif "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        else:
            out.append(ch)
    return "".join(out)


def find_shift(cipher_word, plain_word):
    """Shift that turns plain_word into cipher_word (the 'crib' trick)."""
    return (ord(cipher_word[0].upper()) - ord(plain_word[0].upper())) % 26


class SecretChallenge:
    """A password / token check. `check` is exact (after trimming spaces)."""

    def __init__(self, secret, case_sensitive=True):
        self._secret = secret
        self.case_sensitive = case_sensitive

    def check(self, answer):
        answer = (answer or "").strip()
        if self.case_sensitive:
            return answer == self._secret
        return answer.lower() == self._secret.lower()
