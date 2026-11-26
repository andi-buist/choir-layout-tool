import numpy as np
import pandas as pd
from functools import partial
from io import StringIO
from typing import List, Optional, Tuple

from nicegui import ui

from src.objects import VOICE_PRETTY_NAMES, VOICE_COLOURS, NONE_COLOUR

VOICE_PARTS: Tuple[Optional[str], ...] = ("a1", "a2", "b", "s2", "s1", None)

DEFAULT_ROWS = 9
DEFAULT_COLUMNS = 17
DEFAULT_MISSING_PLACES = ("H01", "H15",
                          *[chr(ord("A") + x) + "16" for x in range(DEFAULT_ROWS - 1)],
                          *[chr(ord("A") + x) + "17" for x in range(DEFAULT_ROWS - 1)]) # Adding 2 front seats by default
VOICE_PART_WEIGHTS = {"a1": 1,
                      "a2": 1,
                      "b": 1,
                      "s2": 1,
                      "s1": 2}

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


def stage_layout_to_csv(assignments: np.ndarray) -> str:
    return pd.DataFrame(assignments[::-1, :]).to_csv(
        index=False,
        header=False,
        na_rep="None",
        lineterminator="\n",
    )


def stage_layout_from_csv(contents: str) -> np.ndarray:
    frame = pd.read_csv(
        StringIO(contents),
        header=None,
        dtype=str,
        keep_default_na=False,
    )
    display_assignments = np.array([
        [
            None if value.strip().lower() in ("", "none") else value.strip().lower()
            for value in row
        ]
        for row in frame.values.tolist()
    ], dtype=object)
    return display_assignments[::-1, :].copy()


class StageEditor:
    def __init__(self, assignments: np.ndarray):
        self.assignments = assignments.copy()
        self.dialog = None
        self.result: Optional[np.ndarray] = None
        self._refresh_content = None
        self.auto_reweight = True

    @property
    def rows(self) -> int:
        return self.assignments.shape[0]

    @property
    def columns(self) -> int:
        return self.assignments.shape[1]

    def _refresh(self) -> None:
        if self._refresh_content is not None:
            self._refresh_content.refresh()

    def _add_row(self) -> None:
        if self.rows < MAX_ROWS:
            if self.auto_reweight:
                new_row = np.array(get_default_voice_parts(self.columns), dtype=object)
            else:
                new_row = self.assignments[-1, :].copy()
            self.assignments = np.vstack((self.assignments, new_row))
            self._refresh()

    def _remove_row(self) -> None:
        if self.rows > 1:
            self.assignments = np.delete(self.assignments, -1, axis=0)
            self._refresh()

    def _resize_columns(self, columns: int) -> None:
        if self.auto_reweight:
            preserved_columns = min(self.columns, columns)
            missing_rows, missing_columns = np.where(
                np.equal(self.assignments[:, :preserved_columns], None)
            )
            rebalanced_row = np.array(get_default_voice_parts(columns), dtype=object)
            self.assignments = np.tile(rebalanced_row, (self.rows, 1))
            self.assignments[missing_rows, missing_columns] = None
        elif columns == (self.columns + 1):
            new_column = self.assignments[:, -1:].copy()
            self.assignments = np.hstack((self.assignments, new_column))
        else:
            self.assignments = np.delete(self.assignments, -1, axis=1)

        self._refresh()

    def _reset_weighting(self) -> None:
        default_row = np.array(get_default_voice_parts(self.columns), dtype=object)
        self.assignments = np.tile(default_row, (self.rows, 1))
        self._refresh()

    def _add_column(self) -> None:
        self._resize_columns(self.columns + 1)

    def _remove_column(self) -> None:
        if self.columns > 1:
            self._resize_columns(self.columns - 1)

    def _cycle_assignment(self, row: int, column: int) -> None:
        current = self.assignments[row][column]
        self.assignments[row][column] = VOICE_PARTS[
            (VOICE_PARTS.index(current) + 1) % len(VOICE_PARTS)
        ]
        self._refresh()

    def _none_rc(
        self,
        row: Optional[int] = None,
        column: Optional[int] = None,
    ) -> None:
        if (row is None) == (column is None):
            raise ValueError("Specify exactly one row or column")
        if row is not None:
            self.assignments[row, :] = None
        else:
            self.assignments[:, column] = None
        self._refresh()

    async def open_dialog(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-4/5 h-[90vh] max-w-none"):
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
                    ui.checkbox(
                        "Reweight voice parts automatically?",
                        value=self.auto_reweight,
                        on_change=lambda e: setattr(self, "auto_reweight", e.value)
                        )

                with ui.element("div").style(
                    "width: 100%; "
                    "height: calc(90vh - 10rem); "
                    "overflow: hidden; "
                    "display: grid; "
                    f"grid-template-columns: 2rem repeat({self.columns}, minmax(0, 1fr)); "
                    f"grid-template-rows: 2.25rem repeat({self.rows}, minmax(0, 1fr)); "
                    "gap: clamp(1px, 0.25vw, 4px); align-items: stretch;"
                ):
                    gradient = ", ".join(
                        VOICE_COLOURS.values()
                    )
                    ui.button(
                        icon="refresh",
                        color="transparent",
                        on_click=self._reset_weighting,
                    ).style(
                        "width: 1.75rem; height: 1.75rem; min-width: 0; "
                        "padding: 0; margin: auto; "
                        "background-color: transparent !important; "
                        f"background-image: linear-gradient(90deg, {gradient}) !important; "
                        "color: white !important;"
                    )
                    for column in range(self.columns):
                        ui.button(
                            str(column + 1),
                            color=NONE_COLOUR,
                            on_click=partial(self._none_rc, column=column)
                        ).classes("w-full text-center")

                    for display_row in range(self.rows):
                        row = self.rows - display_row - 1
                        assignments = self.assignments[row]
                        row_name = chr(ord("A") + display_row)
                        ui.button(
                            row_name,
                            color=NONE_COLOUR,
                            on_click=partial(self._none_rc, row=row),
                        ).props("dense").classes("w-full h-full text-center")
                        for column, assignment in enumerate(assignments):
                            text = VOICE_PRETTY_NAMES.get(assignment, "None")
                            colour = VOICE_COLOURS.get(assignment, NONE_COLOUR)
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
                        self.result = self.assignments.copy()
                        self.dialog.close()

                    ui.button("Apply", on_click=apply_changes)

            self._refresh_content = editor_content
            editor_content()

        self.dialog.open()
