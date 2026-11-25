from nicegui import ui
from nicegui.events import UploadEventArguments

from src.components.stage_edit import stage_layout_from_csv

class FileUploader:
    def __init__(self):
        self.dialog = None
        self.singers = None
        self.stage_layout = None
        self.confirmed = False

    async def open_dialog(self):
        with ui.dialog() as self.dialog, ui.card().classes("w-96"):
            ui.markdown("##### Load singers and/or a stage layout")
            ui.label("Singer list (.json)")
            ui.upload(
                multiple=False,
                max_files=1,
                on_upload=self.handle_singer_upload,
                auto_upload=True,
            ).props('accept=".json"')

            ui.label("Stage layout (.csv)")
            ui.upload(
                multiple=False,
                max_files=1,
                on_upload=self.handle_stage_upload,
                auto_upload=True,
            ).props('accept=".csv"')

            with ui.row().classes("justify-end w-full"):
                ui.button("Cancel", on_click=self.dialog.close)
                ui.button("Load", on_click=self.confirm_load)

        self.dialog.open()

    def confirm_load(self):
        self.confirmed = True
        self.dialog.close()

    async def handle_singer_upload(self, uploaded: UploadEventArguments):
        self.singers = None
        try:
            singers = await uploaded.file.json()
        except (UnicodeDecodeError, ValueError) as error:
            ui.notify(f"Could not read singer JSON: {error}", type="negative")
            return

        if not isinstance(singers, list) or any(not isinstance(singer, dict) for singer in singers):
            ui.notify("Singer JSON must contain a list of singer objects", type="negative")
            return

        self.singers = singers

    async def handle_stage_upload(self, uploaded: UploadEventArguments):
        contents = (await uploaded.file.read()).decode("utf-8-sig")
        self.stage_layout = stage_layout_from_csv(contents)
