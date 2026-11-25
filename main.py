from nicegui import ui
import colour
import numpy as np

import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import json, math
import time
from pathlib import Path

from src.objects import Singer, Stage, VOICE_COLOURS, VOICE_PRETTY_NAMES
from src.components.files import FileUploader
from src.components.interactive_images import make_blank_png
from src.components.placement import assign_singer_places
from src.components.stage_edit import (
    DEFAULT_COLUMNS,
    DEFAULT_MISSING_PLACES,
    DEFAULT_ROWS,
    StageEditor,
    get_default_voice_parts,
    stage_layout_to_csv,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# build alternate colours from main colour register
voice_colours_subdued = {}
voice_colours_deep = {}
for k,v in VOICE_COLOURS.items():
    hsl_decomp = colour.hex2hsl(v)

    subdued = (min(a*b, 1) for a,b in zip(hsl_decomp, (1,0.3,0.6)))
    deep = (min(a*b, 1) for a,b in zip(hsl_decomp, (1,2,0.4)))

    voice_colours_subdued[k] = colour.hsl2hex(subdued)
    voice_colours_deep[k] = colour.hsl2hex(deep)

def _load_local_singers() -> List[Singer]:
    singers_path = Path(__file__).resolve().parent / "data" / "singers.json"
    try:
        with open(singers_path, "r") as singers_file:
            singer_list = [Singer(**singer) for singer in json.load(singers_file)]

            logger.info(f"Local file loaded successfully, {len(singer_list)} singers loaded")
            return singer_list
    except:
        logger.warning("No local file, presuming in deployment")
        return []

class ChoirApp:
    def __init__(self):
        self.stage_w, self.stage_h = (800, 400)
        self.place_positions: Dict[str, Tuple[float, float]] = {}

        self.stage = self._generate_stage(
            DEFAULT_ROWS,
            DEFAULT_COLUMNS,
            list(DEFAULT_MISSING_PLACES),
        )
        self.singers = _load_local_singers()
        self.selected: Singer = None
        self.dragging: Optional[Singer] = None
        self.drag_pos = (0.0, 0.0)

    def _generate_stage(
        self,
        rows: int,
        columns: int,
        missing_places: List[str],
        voice_assignments: Optional[List[List[Optional[str]]]] = None,
    ) -> Stage:
        matrix = (
            voice_assignments
            if voice_assignments is not None
            else [get_default_voice_parts(columns) for _ in range(rows)]
        )
        stage = Stage(np.array(matrix, dtype=object))
        for place_id, row, column, _ in stage.iter_places():
            if place_id in missing_places:
                stage.matrix[row, column] = None
        return stage

    def _randomise_singer_places(self):
        self._assign_singer_places()

    def _assign_singer_places(self, singers_to_assign: Optional[List[Singer]] = None):
        assign_singer_places(
            self.singers,
            self.stage,
            singers_to_assign,
        )

        self.refresh()

    def get_singer_xy(self, s: Singer, idx: int):
        if self.dragging and self.dragging.id == s.id:
            return self.drag_pos
        if s.place_id is not None and s.place_id in self.place_positions:
            return self.place_positions[s.place_id]
        return (50 + idx * 45, 40)

    def _nearest_place(self, x: float, y: float) -> Tuple[Optional[str], float]:
        closest = None
        closest_distance = math.inf

        for place_id, _, _, _ in self.stage.iter_places():
            position = self.place_positions.get(place_id)
            if position is None:
                continue
            distance = math.hypot(x - position[0], y - position[1])
            if distance < closest_distance:
                closest = place_id
                closest_distance = distance

        return closest, closest_distance

    def build_svg(self) -> str:
        MARKER_ICONS = {
            "chair": ("#d8d9e2", "event_seat"),
            "hearing_req": ("#d8d9e2", "hearing"),
            "notes": ("#d8d9e2", "notes"),
        }

        elements = []

        def add_marker_icon(name: str, center_x: float, center_y: float):
            colour, icon_name = MARKER_ICONS[name]
            elements.append(
                f'<text x="{center_x}" y="{center_y}" class="material-icons" '
                f'font-family="Material Icons" font-size="6" fill="{colour}" '
                'text-anchor="middle" dominant-baseline="central" '
                'style="font-feature-settings:\'liga\';-webkit-font-feature-settings:\'liga\';">'
                f'{icon_name}</text>'
            )

        elements.append(
            f'<text x="{self.stage_w / 2}" y="{self.stage_h - 25}" fill="#9ca3af" font-size="26" font-weight="bold" text-anchor="middle">🎵</text>'
        )

        def render_places():
            # this is to follow Kelly's specific use-case
            PLACES_OFFSET = 1.1

            # these should be parameterised/automatically figured out from screen
            STAGE_ANGLE = 20
            STAGE_RADIUS = 1800
            ROW_SQUEEZE = 20

            angle_offset = STAGE_ANGLE/self.stage.columns * PLACES_OFFSET

            start, end = math.radians(270 + angle_offset - STAGE_ANGLE/2), math.radians(270 + angle_offset + STAGE_ANGLE/2)

            row_depth = (self.stage_h - (ROW_SQUEEZE * 2) - 55) / max(1, self.stage.rows - 1)
            center_x = self.stage_w / 2
            center_y = ROW_SQUEEZE + STAGE_RADIUS + ((self.stage.rows - 1) * row_depth)
            positions = {}

            for place_id, row, column, voice_part in self.stage.iter_places():
                radius = STAGE_RADIUS + row * row_depth

                if self.stage.columns > 1:
                    angle = start + (column / (self.stage.columns - 1)) * (end - start)
                else:
                    angle = (start + end) / 2

                x = round(center_x + radius * math.cos(angle), 1)
                y = round(center_y + radius * math.sin(angle), 1)

                colour = voice_colours_subdued.get(voice_part, "#1f2937")
                positions[place_id] = (x, y)
                elements.append(
                    f'<circle cx="{x}" cy="{y}" r="14" fill="{colour}"/>'
                )

            self.place_positions = positions

        def render_singers():
            for idx, singer in enumerate(self.singers):
                x, y = self.get_singer_xy(singer, idx)
                colour = VOICE_COLOURS.get(singer.voice_part, "#9ca3af")
                stroke_colour = voice_colours_deep.get(singer.voice_part, "#131416")
                stroke = (
                    "#ffffff"
                    if singer == self.selected
                    else ("#ef4444" if singer.locked else stroke_colour)
                )
                stroke_width = 3 if (singer == self.selected or singer.locked) else 1.5

                elements.append(
                    f'<circle cx="{x}" cy="{y}" r="16" fill="{colour}" stroke="{stroke}" stroke-width="{stroke_width}"/>'
                )
                elements.append(
                    f'<text x="{x}" y="{y+4}" fill="#111" font-size="11" font-weight="bold" text-anchor="middle">{singer.name[:1]}</text>'
                )
                if singer.needs_chair:
                    add_marker_icon("chair", x + 13, y - 13)
                if singer.hearing_req:
                    add_marker_icon("hearing_req", x + 15, y)
                if singer.notes is not None and singer.notes != "":
                    add_marker_icon("notes", x + 13, y + 13)

        render_places()
        render_singers()

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
                closest, distance = self._nearest_place(mx, my)
                if closest and distance <= 32:
                    self.selected.place_id = closest
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
            closest, distance = self._nearest_place(mx, my)
            if closest and distance < 45:
                occupant = next((s for s in self.singers if s.place_id == closest and s != self.dragging), None)
                if not occupant:
                    self.dragging.place_id = closest
                elif not occupant.locked:
                    occupant.place_id, self.dragging.place_id = self.dragging.place_id, closest
            else:
                self.dragging.place_id = None
            self.dragging = None
            self.refresh()

    async def upload_callback(self):
        uploader = FileUploader()
        await uploader.open_dialog()
        await uploader.dialog

        if not uploader.confirmed:
            return

        if uploader.singers is not None:
            self.singers = [Singer(**singer) for singer in uploader.singers]

        if uploader.stage_layout is not None:
            self._apply_stage_layout(uploader.stage_layout)

        if uploader.singers is not None:
            self._randomise_singer_places()

    def _apply_stage_layout(
        self,
        assignments: np.ndarray,
    ) -> None:
        if assignments.ndim != 2:
            raise ValueError("Stage layout must be a two-dimensional matrix")
        self.stage = Stage(assignments.copy())
        valid_place_ids = {place_id for place_id, _, _, _ in self.stage.iter_places()}
        displaced_singers = [
            singer
            for singer in self.singers
            if singer.place_id is not None and singer.place_id not in valid_place_ids
        ]
        if displaced_singers:
            self._assign_singer_places(displaced_singers)
        else:
            self.refresh()

    def _stage_assignments(self) -> np.ndarray:
        return self.stage.matrix.copy()

    async def stage_editor_callback(self):
        editor = StageEditor(self._stage_assignments())
        await editor.open_dialog()
        await editor.dialog

        if editor.result is None:
            return

        self._apply_stage_layout(editor.result)

    def download_singers_callback(self):
        singers = [asdict(s) for s in self.singers]

        ui.download(json.dumps(singers, indent=2).encode(), "singers.json")

    def download_stage_callback(self):
        stage_csv = stage_layout_to_csv(self._stage_assignments())
        ui.download(stage_csv.encode("utf-8"), "stage.csv")

    def select_save_action(self, action: str) -> None:
        self.save_action = action
        self.save_button.set_text(
            "Save singers" if action == "singers" else "Save stage layout"
        )

    def save_selected_callback(self) -> None:
        if self.save_action == "singers":
            self.download_singers_callback()
        else:
            self.download_stage_callback()

    def refresh(self):
        self.stage_view.content = self.build_svg()
        self.inspector.refresh()

    def build_ui(self):
        ui.dark_mode().enable()

        # 1. Header row with download/upload buttons
        with ui.row().classes("w-full items-center justify-center"):
            ui.label("🎶 Choir Stage Planner").classes("text-2xl font-bold")
        with ui.row().classes("w-full items-center justify-center p-2"):
            ui.button("Randomise", color="secondary", on_click=self._randomise_singer_places)
            ui.button("Edit stage", color="#674079", on_click=self.stage_editor_callback)
            self.save_action = "singers"
            self.save_button = ui.dropdown_button(
                "Save singers",
                split=True,
                auto_close=True,
                on_click=self.save_selected_callback,
            )
            with self.save_button:
                ui.item(
                    "Save singers",
                    on_click=lambda: self.select_save_action("singers"),
                )
                ui.item(
                    "Save stage layout",
                    on_click=lambda: self.select_save_action("stage"),
                )
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
            .classes("w-4/5 mx-auto bg-dark border border-gray-700 rounded-lg select-none")
            .on(type="pointer_move", throttle=0.2)
        )
        self.stage_view.content = self.build_svg()

        # 3. Singer settings panel
        @ui.refreshable
        def inspector_panel():

            with ui.card().classes("w-4/5 mx-auto p-4"):
                ui.markdown("## Singer").classes("w-full text-center")
                s = self.selected

                if s is not None:
                    with ui.row().classes("w-4/5 mx-auto justify-center items-stretch"):
                        ui.markdown(
                            f"#### {VOICE_PRETTY_NAMES.get(s.voice_part)}"
                        ).classes("text-center border border-gray-700 rounded-lg px-4")
                        ui.markdown(
                            f"#### {s.name}"
                        ).classes("text-center border border-gray-700 rounded-lg px-4")
                        ui.button(
                            icon="lock_open" if not s.locked else "lock",
                            color="#a9ddac" if not s.locked else "#e08a6f",
                            on_click=lambda e: (
                                setattr(s, "locked", not s.locked),
                                self.refresh())
                            ).classes("self-stretch text-center border border-gray-700 rounded-lg px-4")
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
                    notes_input = ui.textarea(
                        "Notes",
                        value=s.notes,
                    ).classes("w-full")

                    def commit_notes_on_blur(e):
                        notes = e.args["value"]
                        if notes != s.notes:
                            s.notes = notes
                            self.refresh()

                    notes_input.on(
                        "blur",
                        commit_notes_on_blur,
                        js_handler="(event) => emit({value: event.target.value})",
                    )
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
