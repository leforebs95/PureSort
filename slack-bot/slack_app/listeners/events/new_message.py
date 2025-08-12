import asyncio
import logging
import aiohttp
from slack_bolt import Say, Ack
from slack_sdk import WebClient

from langgraph_sdk import get_sync_client

from dotenv import load_dotenv
load_dotenv()

AGENT_URL = "http://localhost:2024/"

def create_agent_run(message:str):
    client = get_sync_client(url=AGENT_URL)
    
    response = client.runs.wait(
        thread_id=None,
        assistant_id="slack_agent",
        input={
            "slack_message": message,
        }
    )
    return response

def new_message_callback(ack: Ack, event: dict, say: Say, client: WebClient, logger: logging.Logger):
    """
    Handle new_message events from Slack.
    Retrieves and returns information about new messages.
    """
    ack()
    message = event.get("text")
    channel = event.get("channel")
    user = event.get("user")
    logger.debug(f"Received {message} in {channel} from {user}")
    result = client.conversations_info(channel=channel)
    channel_name = result.get("channel").get("name_normalized")
    # Get the message from the event
    if channel_name != "all-ai-tools-testing":
        logger.warning(f"Received new_message event from channel {channel_name}, not processing")
        return
    if not message:
        logger.warning("No message found in the event")
        return
    logger.info(f"Received new_message event from channel {channel_name}: {message}")
    

    agent_run = create_agent_run(message)
    logger.info(f"Agent run created: {agent_run}")
    last_ai_message = [msg for msg in agent_run["messages"] if msg["type"] == "ai"][-1]
    say(thread_ts=event.get("ts"), text=f"{last_ai_message['content']}")