"""Reusable wheel-driven text entry with redacted password representation."""

LOWER = "abcdefghijklmnopqrstuvwxyz"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
NUMBERS = "0123456789"
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?/\\|~`'\""
GROUPS = (LOWER, UPPER, NUMBERS, SYMBOLS)


class TextEntry:
    """Small mutable editor designed for a tiny display and bounded memory."""

    def __init__(self, title, masked=False, max_length=63, initial=""):
        self.title = title
        self.masked = bool(masked)
        self.max_length = int(max_length)
        self._value = initial[:self.max_length]
        self.group_index = 0
        self.character_index = 0

    def __repr__(self):
        return "TextEntry(title={!r}, value=<redacted>, length={})".format(
            self.title, len(self._value)
        )

    @property
    def value(self):
        return self._value

    @property
    def selected_character(self):
        return GROUPS[self.group_index][self.character_index]

    @property
    def group_name(self):
        return ("abc", "ABC", "123", "#+=")[self.group_index]

    def rotate(self, delta):
        group = GROUPS[self.group_index]
        self.character_index = (self.character_index + delta) % len(group)

    def accept(self):
        if len(self._value) < self.max_length:
            self._value += self.selected_character
            return True
        return False

    def next_group(self):
        self.group_index = (self.group_index + 1) % len(GROUPS)
        self.character_index = 0

    def backspace(self):
        self._value = self._value[:-1]

    def clear(self):
        self._value = ""

    def display_value(self):
        return ("•" * len(self._value)) if self.masked else self._value
