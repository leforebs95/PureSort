from slack_bolt import App
from .file_shared import file_shared_callback

def register(app: App):
    app.event("file_shared")(file_shared_callback)