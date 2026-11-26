"""
Defintions of Singer and Stage class, as well as some UI helpers for colours and names
"""

from dataclasses import dataclass
from typing import Iterator, Optional, Tuple
import colour

import numpy as np

def colour_variants(hex: str) -> tuple[str]:
    hsl_decomp = colour.hex2hsl(hex)
    
    subdued = (min(a*b, 1) for a,b in zip(hsl_decomp, (1,0.3,0.6)))
    deep = (min(a*b, 1) for a,b in zip(hsl_decomp, (1,2,0.4)))

    return (colour.hsl2hex(subdued), colour.hsl2hex(deep))

MARKER_ICONS = {
    "chair": ("#d8d9e2", "event_seat"),
    "hearing_req": ("#d8d9e2", "hearing"),
    "notes": ("#d8d9e2", "notes"),
}

VOICE_PRETTY_NAMES = {
    "a1": "Alto 1",
    "a2": "Alto 2",
    "b": "Bari.",
    "s2": "Sop. 2",
    "s1": "Sop. 1",
}
VOICE_COLOURS = {
    "a1": "#432e92",
    "a2": "#234591",
    "b": "#18812a",
    "s2": "#801b1b",
    "s1": "#bd491b"
}
NONE_COLOUR = "#6b7280"
none_colour_subdued, none_colour_deep = colour_variants(NONE_COLOUR)

# build alternate colours from main colour register
voice_colours_subdued = {}
voice_colours_deep = {}

for k,v in VOICE_COLOURS.items():
    result = colour_variants(v)
    voice_colours_subdued[k], voice_colours_deep[k] = result

@dataclass
class Singer:
    id: str
    name: str
    voice_part: str

    notes: str = None

    place_id: Optional[str] = None

    locked: bool = False

    row_pref: int = None
    boundary_req: str = None

    needs_chair: bool = False
    hearing_req: bool = False

@dataclass
class Stage:
    matrix: np.ndarray

    @property
    def rows(self) -> int:
        return self.matrix.shape[0]

    @property
    def columns(self) -> int:
        return self.matrix.shape[1]

    def place_id(self, row: int, column: int) -> str:
        row_letter = chr(ord("A") + self.rows - row - 1)
        return f"{row_letter}{str(column + 1).zfill(2)}"

    def iter_places(self) -> Iterator[Tuple[str, int, int, str]]:
        for row, assignments in enumerate(self.matrix):
            for column, voice_part in enumerate(assignments):
                if voice_part is not None:
                    yield self.place_id(row, column), row, column, voice_part
