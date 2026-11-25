import pandas as pd
from functools import partial
from io import StringIO
from typing import List, Optional, Tuple

from nicegui import ui

from src.objects import VOICE_COLOURS, VOICE_PRETTY_NAMES

DEFAULT_ROWS = 10
DEFAULT_COLUMNS = 15
DEFAULT_MISSING_PLACES = ("H01", "H15",
                          *["J" + str(x+1).zfill(2) for x in range(DEFAULT_COLUMNS) if x not in [10,11]]) # Adding 2 front seats by default
VOICE_PARTS: Tuple[Optional[str], ...] = ("a1", "a2", "b", "s2", "s1", None)
VOICE_PART_WEIGHTS = {voice_part: 1 for voice_part in VOICE_PARTS if voice_part is not None}
MAX_ROWS = 26


def get_default_voice_parts(columns: int) -> List[str]:
    total_weight = sum(VOICE_PART_WEIGHTS.values())
    voice_parts = []

    for column in range(columns):
        position = column * total_weight / columns
        cumulative_weight = 0
        for voice_part, weight in VOICE_PART_WEIGHTS.items():
            cumulative_weight += weight
            if position < cumulative_weight:
                voice_parts.append(voice_part)
                break

    return voice_parts


def stage_layout_to_csv(assignments: List[List[Optional[str]]]) -> str:
    return pd.DataFrame(reversed(assignments)).to_csv(
        index=False,
        header=False,
        na_rep="None",
        lineterminator="\n",
    )


def stage_layout_from_csv(contents: str) -> Tuple[int, int, List[List[Optional[str]]]]:
    frame = pd.read_csv(
        StringIO(contents),
        header=None,
        dtype=str,
        keep_default_na=False,
    )
    display_assignments = [
        [
            None if value.strip().lower() in ("", "none") else value.strip().lower()
            for value in row
        ]
        for row in frame.values.tolist()
    ]
    rows, columns = frame.shape
    return rows, columns, list(reversed(display_assignments))


class StageEditor:
    def __init__(
        self,
        rows: int,
        columns: int,
        assignments: List[List[Optional[str]]],
    ):
        self.assignments = [row.copy() for row in assignments]
        self.rows = rows
        self.columns = columns
        self.dialog = None
        self.result: Optional[Tuple[int, int, List[List[Optional[str]]]]] = None
        self._refresh_content = None

    def _refresh(self) -> None:
        if self._refresh_content is not None:
            self._refresh_content.refresh()

    def _add_row(self) -> None:
        if self.rows < MAX_ROWS:
            self.assignments.insert(0, get_default_voice_parts(self.columns))
            self.rows += 1
            self._refresh()

    def _remove_row(self) -> None:
        if self.rows > 1:
            self.assignments.pop(0)
            self.rows -= 1
            self._refresh()

    def _add_column(self) -> None:
        self.columns += 1
        rebalanced_row = get_default_voice_parts(self.columns)

        for row in self.assignments:
            missing_places = [idx for idx,x in enumerate(row) if not x]
            row.append(None)
            row[:] = rebalanced_row
            for idx in missing_places: row[idx] = None

        self._refresh()

    def _remove_column(self) -> None:
        if self.columns > 1:
            self.columns -= 1
            rebalanced_row = get_default_voice_parts(self.columns)

        for row in self.assignments:
            missing_places = [idx for idx,x in enumerate(row) if not x]
            row.pop()
            row[:] = rebalanced_row
            for idx in missing_places: row[idx] = None

            self._refresh()

    def _cycle_assignment(self, row: int, column: int) -> None:
        current = self.assignments[row][column]
        self.assignments[row][column] = VOICE_PARTS[
            (VOICE_PARTS.index(current) + 1) % len(VOICE_PARTS)
        ]
        self._refresh()

    async def open_dialog(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-4/5 h-[90vh] max-w-none"):
            ui.label("Edit stage")

            @ui.refreshable
            def editor_content():
                with ui.row().classes("items-center"):
                    ui.button("Add row", on_click=self._add_row).props(
                        "disable" if self.rows >= MAX_ROWS else ""
                    )
                    ui.button(
                        "Remove row",
                        on_click=self._remove_row,
                    ).props("disable" if self.rows <= 1 else "")
                    ui.button("Add column", on_click=self._add_column)
                    ui.button(
                        "Remove column",
                        on_click=self._remove_column,
                    ).props("disable" if self.columns <= 1 else "")

                with ui.element("div").style(
                    "width: 100%; "
                    "height: calc(90vh - 10rem); "
                    "overflow: hidden; "
                    "display: grid; "
                    f"grid-template-columns: 2rem repeat({self.columns}, minmax(0, 1fr)); "
                    f"grid-template-rows: 1.5rem repeat({self.rows}, minmax(0, 1fr)); "
                    "gap: clamp(1px, 0.25vw, 4px); align-items: stretch;"
                ):
                    ui.label("")
                    for column in range(self.columns):
                        ui.label(str(column + 1)).classes("text-center")

                    for display_row in range(self.rows):
                        row = self.rows - display_row - 1
                        assignments = self.assignments[row]
                        row_name = chr(ord("A") + display_row)
                        ui.label(row_name).classes("text-center")
                        for column, assignment in enumerate(assignments):
                            text = VOICE_PRETTY_NAMES.get(assignment, "None")
                            colour = VOICE_COLOURS.get(assignment, "#6b7280")
                            ui.button(
                                text,
                                color=colour,
                                on_click=partial(self._cycle_assignment, row, column),
                            ).props("dense").style(
                                "color: white; width: 100%; height: 100%; "
                                "min-width: 0; min-height: 0; padding: 0; "
                                "font-size: clamp(0.45rem, min(0.9vw, 1.5vh), 0.85rem); "
                                "line-height: 1; white-space: normal;"
                            )

                with ui.row().classes("justify-end w-full"):
                    ui.button("Cancel", on_click=self.dialog.close)

                    def apply_changes():
                        self.result = (
                            self.rows,
                            self.columns,
                            [row.copy() for row in self.assignments],
                        )
                        self.dialog.close()

                    ui.button("Apply", on_click=apply_changes)

            self._refresh_content = editor_content
            editor_content()

        self.dialog.open()
