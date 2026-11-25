from nicegui import ui
from dataclasses import dataclass, asdict
from typing import List, Optional
import json, math
import zlib, struct, base64
import time
import random

from src.objects import Singer, Place
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

VOICE_COLORS = {
    "a1": "#a3d6ff",
    "a2": "#0a91ff",
    "b": "#23a338",
    "s2": "#ff3434",
    "s1": "#ffc4c4"
}

VOICE_PART_WEIGHTS = {"a1": 1, "a2": 1, "b": 1, "s2": 1, "s1": 1}

class ChoirApp:
    MISSING_PLACES = ["H01", "H15"]

    def __init__(self):
        self.stage_w, self.stage_h = (800, 400)

        self.places = self._generate_stage()
        self.singers = []
        self.selected: Singer = None
        self.dragging: Optional[Singer] = None
        self.drag_pos = (0.0, 0.0)

    def _get_row_voice_parts(self, per_row: int) -> List[str]:
        total_weight = sum(VOICE_PART_WEIGHTS.values())
        if total_weight <= 0 or any(weight < 0 for weight in VOICE_PART_WEIGHTS.values()):
            raise ValueError("Voice-part weights must be non-negative with a positive total")

        voice_parts = []
        for i in range(per_row):
            position = i * total_weight / per_row
            cumulative_weight = 0
            for voice_part, weight in VOICE_PART_WEIGHTS.items():
                cumulative_weight += weight
                if position < cumulative_weight:
                    voice_parts.append(voice_part)
                    break
        return voice_parts

    def _generate_stage(self, rows=9, per_row=15) -> List[Place]:
        places = []
        row_voice_parts = self._get_row_voice_parts(per_row)

        start, end = math.radians(260), math.radians(280)
        half_angle = math.radians(10)  # Half of the 20-degree (260 to 280) span

        pad = 35
        # Scale radius so the width fits inside self.stage_w and height fits inside self.stage_h
        max_r_by_width = ((self.stage_w / 2) - pad) / math.sin(half_angle)
        row_depth = (self.stage_h - (pad * 2) - 55) / max(1, rows - 1)
        stage_radius = min(1800, max_r_by_width - (rows - 1) * row_depth)

        # Center horizontally at self.stage_w / 2, and anchor top row 'pad' pixels from top
        center_x = self.stage_w / 2
        outer_radius = stage_radius + ((rows - 1) * row_depth)
        center_y = pad + outer_radius

        for r in range(rows):
            row_letter = chr(ord("A") + rows - (r + 1)) # Build front to back, highest letter first
            radius = stage_radius + (r * row_depth)

            for i in range(per_row):
                place_name = f"{row_letter}{str(i+1).zfill(2)}"
                if place_name in self.MISSING_PLACES:
                    continue

                theta = start + (i / (per_row - 1)) * (end - start)

                stage_place = Place(
                    place_name,
                    r,
                    i,
                    round(center_x + radius * math.cos(theta), 1),
                    round(center_y + radius * math.sin(theta), 1),
                    voice_part=row_voice_parts[i],
                )

                places.append(stage_place)
        return places

    def _choose_fallback_place(self, singer: Singer, available_places: List[Place]) -> Place:
        center_index = max(place.index for place in self.places) / 2
        own_block_indexes = {
            place.index for place in self.places
            if place.voice_part == singer.voice_part
        }

        def priority(place: Place):
            block_distance = min(
                (abs(place.index - index) for index in own_block_indexes),
                default=abs(place.index - center_index),
            )
            return block_distance, -abs(place.index - center_index), place.row

        best_priority = min(priority(place) for place in available_places)
        closest_places = [
            place for place in available_places
            if priority(place) == best_priority
        ]
        return random.choice(closest_places)

    def _randomise_singer_places(self):
        unlocked_singers = [s for s in self.singers.copy() if not s.locked]
        locked_place_ids = {s.place_id for s in self.singers if s.locked}
        available_places = [p for p in self.places if p.id not in locked_place_ids]
        matched_place_ids = set()

        for singer in unlocked_singers:
            singer.place_id = None

        for place in available_places:
            if not unlocked_singers:
                break
            matching_singers = [
                singer for singer in unlocked_singers
                if singer.voice_part == place.voice_part
            ]
            if not matching_singers:
                continue
            singer = random.choice(matching_singers)
            singer.place_id = place.id
            unlocked_singers.remove(singer)
            matched_place_ids.add(place.id)

        unmatched_places = [
            place for place in available_places
            if place.id not in matched_place_ids
        ]
        random.shuffle(unlocked_singers)
        for singer in unlocked_singers:
            if not unmatched_places:
                break
            place = self._choose_fallback_place(singer, unmatched_places)
            singer.place_id = place.id
            unmatched_places.remove(place)

        self.refresh()

    def get_singer_xy(self, s: Singer, idx: int):
        if self.dragging and self.dragging.id == s.id:
            return self.drag_pos
        place = next((sp for sp in self.places if sp.id == s.place_id), None)
        return (place.x, place.y) if place else (50 + idx * 45, 40)

    def build_svg(self) -> str:
        COLOUR_DEFS = {
            "dots": {
                "chair": "#f97316",
                "hearing_req": "#a855f7",
                "notes": "#9FA2BE"
            }
        }

        elements = []
        elements.append(
            f'<text x="{self.stage_w / 2}" y="{self.stage_h - 25}" fill="#9ca3af" font-size="38" font-weight="bold" text-anchor="middle">🎵</text>'
        )

        # Draw places
        for sp in self.places:
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
                f'<text x="{x}" y="{y+4}" fill="#111" font-size="11" font-weight="bold" text-anchor="middle">{s.name[:1]}</text>'
            )
            if s.needs_chair:
                elements.append(
                    f'<circle cx="{x+13}" cy="{y-13}" r="3" fill={COLOUR_DEFS["dots"]["chair"]} stroke="#000"/>'
                )
            if s.hearing_req:
                elements.append(
                    f'<circle cx="{x-13}" cy="{y-13}" r="3" fill={COLOUR_DEFS["dots"]["hearing_req"]} stroke="#000"/>'
                )
            if s.notes is not None and s.notes != "":
                elements.append(
                    f'<circle cx="{x+13}" cy="{y+13}" r="3" fill={COLOUR_DEFS["dots"]["notes"]} stroke="#000"/>'
                )

        return "".join(elements)

    def handle_pointer(self, e):
        mx, my = e.image_x, e.image_y

        # Check pointer_type safely, or fall back to mobile User-Agent detection
        pointer_type = getattr(e, "pointer_type", None)
        if pointer_type is not None:
            is_touch = pointer_type in ("touch", "pen")
        else:
            ua = e.client.request.headers.get("user-agent", "") if e.client and e.client.request else ""
            is_touch = any(k in ua for k in ("Mobile", "Android", "iPhone", "iPad"))

        # Mobile
        if is_touch:
            if e.type != "pointerdown":
                return

            # 1. Select a Singer
            for idx, s in reversed(list(enumerate(self.singers))):
                sx, sy = self.get_singer_xy(s, idx)
                if math.hypot(mx - sx, my - sy) <= 28:
                    # Swap two singers
                    if self.selected and self.selected != s and not self.selected.locked and not s.locked:
                        self.selected.place_id, s.place_id = s.place_id, self.selected.place_id
                        self.selected = None  # Done, deselect
                    else:
                        self.selected = s  # Pick up / inspect
                    self.refresh()
                    return

            # 2. Moving a Singer to an empty Place
            if self.selected and not self.selected.locked:
                closest = min(self.places, key=lambda sp: math.hypot(mx - sp.x, my - sp.y), default=None)
                if closest and math.hypot(mx - closest.x, my - closest.y) <= 32:
                    self.selected.place_id = closest.id
                    self.selected = None
                    self.refresh()
                    return

            # 3. Didn't click a Place, deselect
            self.selected = None
            self.refresh()
            return

        # Desktop
        if e.type == "pointerdown":
            for idx, s in reversed(list(enumerate(self.singers))):
                sx, sy = self.get_singer_xy(s, idx)
                if math.hypot(mx - sx, my - sy) <= 20:
                    self.selected = s
                    if not s.locked:
                        self.dragging = s
                        self.drag_pos = (sx, sy)
                        self.last_move_time = 0.0
                    self.refresh()
                    return

            # Clicked empty background
            self.selected = None
            self.refresh()

        elif e.type == "pointermove" and self.dragging:
            # Throttle WebSocket redraws to max ~12 FPS (every 0.08s) so Render never lags
            now = time.monotonic()
            if now - self.last_move_time < 0.08:
                return
            self.last_move_time = now
            self.drag_pos = (mx, my)
            self.stage_view.content = self.build_svg()

        elif e.type == "pointerup" and self.dragging:
            closest = min(self.places, key=lambda sp: math.hypot(mx - sp.x, my - sp.y), default=None)
            if closest and math.hypot(mx - closest.x, my - closest.y) < 45:
                occupant = next((s for s in self.singers if s.place_id == closest.id and s != self.dragging), None)
                if not occupant:
                    self.dragging.place_id = closest.id
                elif not occupant.locked:
                    occupant.place_id, self.dragging.place_id = self.dragging.place_id, closest.id
            else:
                self.dragging.place_id = None
            self.dragging = None
            self.refresh()

    async def upload_callback(self):
        uploader = FileUploader()
        await uploader.open_dialog()
        await uploader.dialog

        self.singers = [Singer(**s) for s in uploader.data]
        self.places = self._generate_stage()

        self._randomise_singer_places()

        self.refresh()

    def download_callback(self):
        singers = [asdict(s) for s in self.singers]

        ui.download(json.dumps(singers, indent=2).encode(), "singers.json")

    def refresh(self):
        self.stage_view.content = self.build_svg()
        self.inspector.refresh()

    def build_ui(self):
        ui.dark_mode().enable()

        # 1. Header row with download/upload buttons
        with ui.row().classes("w-full items-center justify-center p-2"):
            ui.label("🎶 Choir Stage Planner").classes("text-2xl font-bold justify-center")
            ui.button("Randomise", color="secondary", on_click=self._randomise_singer_places)
            ui.button("Save", on_click=self.download_callback)
            ui.button("Load", on_click=self.upload_callback)

        # 2. Stage editor
        self.stage_view = (
            ui.interactive_image(
                source=make_blank_png(800, 400),
                on_mouse=self.handle_pointer,
                events=["pointerdown", "pointermove", "pointerup"],
                cross=False,
            )
            .props('draggable="false" ondragstart="return false;" style="width: full; height: auto;"')
            .classes("w-4/5 mx-auto border border-gray-700 rounded-lg select-none")
            .on(type="pointer_move", throttle=0.2)
        )
        self.stage_view.content = self.build_svg()

        # 3. Singer settings panel
        @ui.refreshable
        def inspector_panel():
            with ui.card().classes("w-4/5 mx-auto p-4"):
                ui.label("Singer").classes("text-lg font-bold")
                s = self.selected

                if s is not None:
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
                            "Alto1 : Baritone",
                        ],
                        label="Boundary Req.",
                        value=s.boundary_req,
                        on_change=lambda e: setattr(s, "boundary_req", e.value),
                    ).classes("w-full")
                    ui.textarea(
                        "Notes",
                        value=s.notes,
                        on_change=lambda e: (
                            setattr(s, "notes", e.value),
                            self.refresh(),
                        ),
                    ).classes("w-full")
                    ui.label(f"Place: {s.place_id or 'Pending'}").classes(
                        "text-sm text-gray-500 mt-2"
                    )
                else:
                    ui.label("Nobody selected").classes(
                        "text-sm text-gray-500 mt-2"
                    )

        self.inspector = inspector_panel
        self.inspector()

app = ChoirApp()
app.build_ui()
ui.run(title="Choir Stage Planner")
