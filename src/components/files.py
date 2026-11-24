from nicegui import ui
from nicegui.events import UploadEventArguments
import asyncio

class FileUploader:
    def __init__(self):
        self.dialog = None
        self.data = None
    async def open_dialog(self):
        with ui.dialog() as self.dialog, ui.card():
            ui.label("Upload your saved JSON file")
            upload = ui.upload(
                multiple=False,
                max_files=1,
                on_upload=self.handle_upload,
                auto_upload=True
            )
        self.dialog.open()

    async def handle_upload(self, uploaded: UploadEventArguments):
        data = await uploaded.file.json()
        
        self.data = data
        self.dialog.close()
