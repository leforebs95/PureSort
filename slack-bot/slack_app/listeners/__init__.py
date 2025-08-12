from listeners import assistant
from listeners import events

def register_listeners(app):
    # Using assistant middleware is the recommended way.
    assistant.register(app)
    events.register(app)
