from dataclasses import dataclass
from typing import Optional

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
    "s1": "#bd491b",
}


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
class Place:
    id: str
    row: int
    index: int

    voice_part: str = None
