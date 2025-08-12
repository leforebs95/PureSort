from slack_bolt import App
from .file_shared import file_shared_callback
from .new_message import new_message_callback

def register(app: App):
    app.event("file_shared")(file_shared_callback)
    app.event("message")(new_message_callback)