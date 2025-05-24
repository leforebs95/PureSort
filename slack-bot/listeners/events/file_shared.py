import logging
from slack_bolt import Say
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

def file_shared_callback(event: dict, say: Say, client: WebClient, logger: logging.Logger):
    """
    Handle file_shared events from Slack.
    Retrieves and returns information about shared files.
    """
    try:
        logger.info(f"Received file_shared event: {event}")
        # Get the file ID from the event
        file_id = event.get("file_id")
        if not file_id:
            logger.warning("No file_id found in the event")
            return

        # Get file information using files.info API
        file_info = client.files_info(file=file_id)
        logger.debug(f"File info response: {file_info}")
        
        if not file_info["ok"]:
            logger.error(f"Failed to get file info: {file_info.get('error')}")
            return

        file = file_info["file"]
        logger.debug(f"File data: {file}")
        
        
        # Create a message with file information
        payload = {
            "text": (
                f"📎 File details:\n"
                f"• Name: {file.get('name', 'N/A')}\n"
                f"• Type: {file.get('filetype', 'N/A')}\n"
                f"• Size: {file.get('size', 0) / 1024:.1f} KB\n"
                f"• Uploaded by: <@{file.get('user', 'N/A')}>\n"
            ),
            "channel": event.get("channel_id"),
            "thread_ts": event.get("event_ts")
        }
        
        # Send the message to the channel
        logger.info(f"Sending message to channel: {payload.get('channel')} and thread_ts: {payload.get('thread_ts')}")
        say(**payload)
        
    except SlackApiError as e:
        logger.error(f"Error handling file_shared event: {e}")
        say(f":warning: Error retrieving file information: {e.response['error']}")
    except Exception as e:
        logger.error(f"Unexpected error in file_shared_callback: {e}")
        say(":warning: An unexpected error occurred while processing the file share.")