import os
import logging
from dotenv import load_dotenv

from slack_bolt import App, Say
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt.adapter.socket_mode import SocketModeHandler

from listeners import register_listeners

load_dotenv()

# Initialization
logging.basicConfig(level=logging.INFO)
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Register Listeners
register_listeners(app)

# Start Bolt app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start()
