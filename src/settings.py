"""User-adjustable keyboard and chord settings."""

BASE_NOTE = 60  # C4
PLACEHOLDER_KEY = '__left_pad__'

GERMAN_KEY_MAP = {
    '<': 0, 'y': 2, 'x': 4, 'c': 6, 'v': 8, 'b': 10, 'n': 12,
    'm': 14, ',': 16, '.': 18, '-': 20,
    'a': 1, 's': 3, 'd': 5, 'f': 7, 'g': 9, 'h': 11, 'j': 13,
    'k': 15, 'l': 17, 'ö': 19, 'ä': 21, '#': 23,
    'q': 0, 'w': 2, 'e': 4, 'r': 6, 't': 8, 'z': 10, 'u': 12,
    'i': 14, 'o': 16, 'p': 18, 'ü': 20, '+': 22,
    '1': -1, '2': 1, '3': 3, '4': 5, '5': 7, '6': 9, '7': 11,
    '8': 13, '9': 15, '0': 17, 'ß': 19, '´': 21,
}

GERMAN_ROWS = [
    [PLACEHOLDER_KEY, '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', 'ß', '´'],
    [PLACEHOLDER_KEY, 'q', 'w', 'e', 'r', 't', 'z', 'u', 'i', 'o', 'p', 'ü', '+'],
    [PLACEHOLDER_KEY, 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'ö', 'ä', '#'],
    ['<', 'y', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '-'],
]

ENGLISH_KEY_MAP = {
    '1': -1, '2': 1, '3': 3, '4': 5, '5': 7, '6': 9, '7': 11,
    '8': 13, '9': 15, '0': 17, '-': 19, '=': 21,
    'q': 0, 'w': 2, 'e': 4, 'r': 6, 't': 8, 'y': 10, 'u': 12,
    'i': 14, 'o': 16, 'p': 18, '[': 20, ']': 22,
    'a': 1, 's': 3, 'd': 5, 'f': 7, 'g': 9, 'h': 11, 'j': 13,
    'k': 15, 'l': 17, ';': 19, "'": 21, '\\': 23,
    'z': 2, 'x': 4, 'c': 6, 'v': 8, 'b': 10, 'n': 12,
    'm': 14, ',': 16, '.': 18, '/': 20,
}

ENGLISH_ROWS = [
    [PLACEHOLDER_KEY, '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '='],
    [PLACEHOLDER_KEY, 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']'],
    [PLACEHOLDER_KEY, 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'", '\\'],
    ['z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/'],
]

KEYBOARD_LAYOUTS = {
    "German": {"key_map": GERMAN_KEY_MAP, "rows": GERMAN_ROWS},
    "English": {"key_map": ENGLISH_KEY_MAP, "rows": ENGLISH_ROWS},
}
DEFAULT_LAYOUT = "German"

# Backwards-compatible aliases for callers using the default layout.
key_map = KEYBOARD_LAYOUTS[DEFAULT_LAYOUT]["key_map"]
ROWS = KEYBOARD_LAYOUTS[DEFAULT_LAYOUT]["rows"]

CHORDS = [
    {"name": "Major", "intervals": [0, 4, 7]},
    {"name": "Minor", "intervals": [0, 3, 7]},
    {"name": "Major7", "intervals": [0, 4, 7, 11]},
    {"name": "Minor7", "intervals": [0, 3, 7, 10]},
    {"name": "7", "intervals": [0, 4, 7, 10]},
    {"name": "dim7", "intervals": [0, 3, 6, 9]},
    {"name": "m6", "intervals": [0, 3, 7, 9]},
    {"name": "Sus2", "intervals": [0, 2, 7]},
    {"name": "Sus4", "intervals": [0, 5, 7]},
    {"name": "Dim", "intervals": [0, 3, 6]},
    {"name": "Aug", "intervals": [0, 4, 8]},
    {"name": "aug7", "intervals": [0, 4, 8, 10]},
]

CHORD_GRID = [
    ["Major", "Minor"],
    ["Major7", "Minor7"],
    ["7", "m6"],
    ["Aug", "Dim"],
    ["aug7", "dim7"],
    ["Sus2", "Sus4"],
]

ROW_OFFSETS = [0, 18, 36, 54]
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
