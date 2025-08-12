import os
import logging
from dotenv import load_dotenv

from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

from listeners import register_listeners
from utils.secrets_manager import secrets_manager

load_dotenv()

# Get environment setting (default to DEV)
ENVIRONMENT = os.environ.get("ENVIRONMENT", "DEV").upper()

# Initialization
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_slack_credentials():
    """Get Slack credentials from appropriate source based on environment"""
    if ENVIRONMENT == "PROD":
        # Production: Use AWS Secrets Manager
        logger.info("Loading credentials from AWS Secrets Manager")
        bot_token = secrets_manager.get_slack_bot_token()
        signing_secret = secrets_manager.get_slack_signing_secret()
        
        if not bot_token or not signing_secret:
            raise ValueError("Failed to retrieve Slack credentials from Secrets Manager")
            
        return bot_token, signing_secret
    else:
        # Development: Use environment variables (fallback to Secrets Manager if available)
        logger.info("Loading credentials from environment variables")
        bot_token = os.environ.get("SLACK_BOT_TOKEN")
        signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
        
        # Fallback to Secrets Manager if environment variables are not set
        if not bot_token and os.environ.get("SLACK_BOT_TOKEN_SECRET_ARN"):
            logger.info("Falling back to Secrets Manager for bot token")
            bot_token = secrets_manager.get_slack_bot_token()
            
        if not signing_secret and os.environ.get("SLACK_SIGNING_SECRET_SECRET_ARN"):
            logger.info("Falling back to Secrets Manager for signing secret")
            signing_secret = secrets_manager.get_slack_signing_secret()
        
        if not bot_token or not signing_secret:
            raise ValueError("Failed to retrieve Slack credentials from environment variables or Secrets Manager")
            
        return bot_token, signing_secret

# Get credentials
try:
    slack_bot_token, slack_signing_secret = get_slack_credentials()
except ValueError as e:
    logger.error(f"Failed to initialize Slack credentials: {e}")
    raise

if ENVIRONMENT == "PROD":
    # Lambda/Production configuration
    # process_before_response must be True when running on FaaS
    app = App(
        token=slack_bot_token,
        signing_secret=slack_signing_secret,
        process_before_response=True
    )
else:
    # DEV/ngrok configuration using HTTP mode
    app = App(
        token=slack_bot_token,
        signing_secret=slack_signing_secret
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