from dataclasses import dataclass
from typing import Optional

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
