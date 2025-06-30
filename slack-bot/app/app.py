import os
import logging
from dotenv import load_dotenv

from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

from listeners import register_listeners

load_dotenv()

# Get environment setting (default to DEV)
ENVIRONMENT = os.environ.get("ENVIRONMENT", "DEV").upper()

# Initialization
logging.basicConfig(level=logging.INFO)

if ENVIRONMENT == "PROD":
    # Lambda/Production configuration
    # process_before_response must be True when running on FaaS
    app = App(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
        process_before_response=True
    )
else:
    # DEV/ngrok configuration using HTTP mode
    app = App(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
    )

# Register Listeners
register_listeners(app)

# Lambda handler function (only used in PROD)
def lambda_handler(event, context):
    """AWS Lambda handler function"""
    if ENVIRONMENT != "PROD":
        raise RuntimeError("Lambda handler should only be called in PROD environment")
    
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context)

# Start application
if __name__ == "__main__":
    if ENVIRONMENT == "PROD":
        print("Running in PROD mode - Lambda handler ready")
        # In Lambda, the handler function will be called automatically
        # This section won't execute in Lambda, but helps with local testing
    else:
        print("Running in DEV mode with HTTP server")
        print("Make sure ngrok is running: ngrok http 3000")
        print("Update your Slack app's Request URL to: https://your-ngrok-url.ngrok.io/slack/events")
        app.start(port=3000)