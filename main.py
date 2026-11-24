from nicegui import ui
from dataclasses import dataclass, asdict
from typing import List, Optional
import json, math
import zlib, struct, base64

from src.components.files import FileUploader

def make_blank_png(width=800, height=550, color=(0, 0, 0, 255)) -> str:
    raw_row = b"\x00" + bytes(color) * width
    raw_data = raw_row * height

    def chunk(tag, data):
        return (
            struct.pack("!I", len(data))
            + tag
            + data
            + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw_data))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode()

@dataclass
class Singer:
    id: str
    name: str
    voice_part: str
    needs_chair: bool = False
    hearing_req: bool = False
    boundary_req: str = "None"
    locked: bool = False
    spot_id: Optional[str] = None

@dataclass
class StageSpot:
    id: str
    row: int
    index: int
    x: float
    y: float

VOICE_COLORS = {
    "s1": "#ff6b6b",
    "s2": "#ff8787",
    "a1": "#4dabf7",
    "a2": "#339af0",
    "b": "#51cf66"
}

class ChoirApp:
    MISSING_SPOTS = ["H01", "H15"]

    def __init__(self):
        self.spots = self._generate_stage()
        self.singers = [
            Singer("s1", "Person 1", "s1", spot_id="A01"),
            Singer(
                "s2", "Person 2", "s2", boundary_req="Alto 1/Alto 2", spot_id="B02"
            ),
            Singer("s3", "Person 3", "a1", needs_chair=True, spot_id="C03"),
            Singer("s4", "Person 4", "a2", hearing_req=True, spot_id="D04"),
            Singer("s5", "Person 5", "b", locked=True, spot_id="E05"),
        ]
        self.selected: Singer = self.singers[0]
        self.dragging: Optional[Singer] = None
        self.drag_pos = (0.0, 0.0)

    def _generate_stage(self, rows=9, per_row=15) -> List[StageSpot]:
        spots = []
        start, end = math.radians(260), math.radians(280)

        stage_radius = 1800
        stage_offset = (0, stage_radius - 150)
        row_depth = 36

        for r in range(rows):
            row_letter = chr(ord("A") + rows - (r + 1))

            radius = stage_radius + (r * row_depth)

            for i in range(per_row):
                spot_name = f"{row_letter}{str(i+1).zfill(2)}"

                if spot_name not in self.MISSING_SPOTS:
                    theta = start + (i / (per_row - 1)) * (end - start)

                    stage_spot = StageSpot(
                        spot_name,
                        r,
                        i,
                        stage_offset[0] + round(400 + radius * math.cos(theta), 1),
                        stage_offset[1] + round(540 + radius * math.sin(theta), 1),
                    )

                    spots.append(stage_spot)
        return spots

    def get_singer_xy(self, s: Singer, idx: int):
        if self.dragging and self.dragging.id == s.id:
            return self.drag_pos
        spot = next((sp for sp in self.spots if sp.id == s.spot_id), None)
        return (spot.x, spot.y) if spot else (50 + idx * 45, 40)

    def build_svg(self) -> str:
        elements = ['<rect width="800" height="550" fill="#111827" rx="8"/>']
        elements.append(
            '<text x="400" y="525" fill="#9ca3af" font-size="38" font-weight="bold" text-anchor="middle">🎵</text>'
        )

        # Draw spots
        for sp in self.spots:
            elements.append(
                f'<circle cx="{sp.x}" cy="{sp.y}" r="16" fill="#1f2937" stroke="#4b5563" stroke-width="1.5"/>'
            )

        # Draw singers
        for idx, s in enumerate(self.singers):
            x, y = self.get_singer_xy(s, idx)
            color = VOICE_COLORS.get(s.voice_part, "#9ca3af")
            stroke = (
                "#ffffff"
                if s == self.selected
                else ("#ef4444" if s.locked else "#000000")
            )
            sw = 3 if (s == self.selected or s.locked) else 1.5

            elements.append(
                f'<circle cx="{x}" cy="{y}" r="18" fill="{color}" stroke="{stroke}" stroke-width="{sw}"/>'
            )
            elements.append(
                f'<text x="{x}" y="{y+4}" fill="#111" font-size="11" font-weight="bold" text-anchor="middle">{s.name[:4]}</text>'
            )
            if s.needs_chair:
                elements.append(
                    f'<circle cx="{x+13}" cy="{y-13}" r="5" fill="#f97316" stroke="#000"/>'
                )
            if s.hearing_req:
                elements.append(
                    f'<circle cx="{x-13}" cy="{y-13}" r="5" fill="#a855f7" stroke="#000"/>'
                )
        return "".join(elements)

    def handle_mouse(self, e):
        mx, my = e.image_x, e.image_y
        if e.type == "mousedown":
            for idx, s in reversed(list(enumerate(self.singers))):
                sx, sy = self.get_singer_xy(s, idx)
                if math.hypot(mx - sx, my - sy) <= 20:
                    self.selected = s
                    if not s.locked:
                        self.dragging = s
                        self.drag_pos = (sx, sy)
                    self.refresh()
                    break
        elif e.type == "mousemove" and self.dragging:
            self.drag_pos = (mx, my)
            self.stage_view.content = self.build_svg()
        elif e.type == "mouseup" and self.dragging:
            closest = min(
                self.spots,
                key=lambda sp: math.hypot(mx - sp.x, my - sp.y),
                default=None,
            )
            if closest and math.hypot(mx - closest.x, my - closest.y) < 45:
                occupant = next(
                    (
                        s
                        for s in self.singers
                        if s.spot_id == closest.id and s != self.dragging
                    ),
                    None,
                )
                if not occupant:
                    self.dragging.spot_id = closest.id
                elif not occupant.locked:
                    occupant.spot_id, self.dragging.spot_id = (
                        self.dragging.spot_id,
                        closest.id,
                    )
            else:
                self.dragging.spot_id = None
            self.dragging = None
            self.refresh()
        elif e.type == "mouseup":
            self.selected = None
            self.refresh()

    async def upload_callback(self):
        uploader = FileUploader()
        await uploader.open_dialog()
        await uploader.dialog

        data = uploader.data

        self.singers = [Singer(**s) for s in data["singers"]]
        self.spots = [StageSpot(**s) for s in data["spots"]]

        self.refresh()

    def download_callback(self):
        data = {
            "singers": [asdict(s) for s in self.singers],
            "spots": [asdict(sp) for sp in self.spots],
        }

        ui.download(json.dumps(data, indent=2).encode(), "choir_layout.json")

    def refresh(self):
        self.stage_view.content = self.build_svg()
        self.inspector.refresh()

    def build_ui(self):
        ui.dark_mode().enable()

        # 1. Header row with download/upload buttons
        with ui.row().classes("w-full items-center justify-center p-2"):
            ui.label("🎶 Choir Stage Planner").classes("text-2xl font-bold justify-center")
            ui.button("Save", on_click=self.download_callback)
            ui.button("Load", on_click=self.upload_callback)

        # 2. Main region
        with ui.row().classes("w-full no-wrap gap-6 p-2 justify-center"):

            # 2.1. Stage editor
            self.stage_view = (
                ui.interactive_image(
                    source=make_blank_png(800, 550),
                    on_mouse=self.handle_mouse,
                    events=["mousedown", "mousemove", "mouseup"],
                    cross=False,
                )
                .props('draggable="false"')
                .classes(
                    "w-[800px] h-[550px] border border-gray-700 rounded-lg select-none"
                )
            )

            self.stage_view.content = self.build_svg()

            # 2.2. Singer settings panel
            @ui.refreshable
            def inspector_panel():
                with ui.card().classes("w-80"):
                    ui.label("Singer").classes("text-lg font-bold")
                    s = self.selected
                    ui.input(
                        "Name",
                        value=s.name,
                        on_change=lambda e: (
                            setattr(s, "name", e.value),
                            self.refresh(),
                        ),
                    ).classes("w-full")
                    ui.select(
                        list(VOICE_COLORS.keys()),
                        label="Voice Part",
                        value=s.voice_part,
                        on_change=lambda e: (
                            setattr(s, "voice_part", e.value),
                            self.refresh(),
                        )
                    ).classes("w-full")
                    ui.checkbox(
                        "Lock",
                        value=s.locked,
                        on_change=lambda e: (
                            setattr(s, "locked", e.value),
                            self.refresh(),
                        ),
                    ).classes("w-full")
                    ui.checkbox(
                        "Chair",
                        value=s.needs_chair,
                        on_change=lambda e: (
                            setattr(s, "needs_chair", e.value),
                            self.refresh(),
                        ),
                    ).classes("w-full")
                    ui.checkbox(
                        "Hearing Req.",
                        value=s.hearing_req,
                        on_change=lambda e: (
                            setattr(s, "hearing_req", e.value),
                            self.refresh(),
                        ),
                    ).classes("w-full")
                    ui.select(
                        [
                            "None",
                            "Sop1 : Sop2",
                            "Sop2 : Baritone",
                            "Alto1 : Alto2",
                            "Alto2 : Baritone",
                        ],
                        label="Boundary Req.",
                        value=s.boundary_req,
                        on_change=lambda e: setattr(s, "boundary_req", e.value),
                    ).classes("w-full")
                    ui.label(f"Spot: {s.spot_id or 'Pending'}").classes(
                        "text-sm text-gray-400 mt-2"
                    )

            self.inspector = inspector_panel
            self.inspector()


app = ChoirApp()
app.build_ui()
ui.run(title="Choir Stage Planner")
