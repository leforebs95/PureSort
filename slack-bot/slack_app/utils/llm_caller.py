import os
import re
import logging
from dotenv import load_dotenv
from typing import List, Dict

import anthropic
from .secrets_manager import secrets_manager

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_CONTENT = """
You're an assistant in a Slack workspace.
Users in the workspace will ask you to help them write something or to think better about a specific topic.
You'll respond to those questions in a professional way.
When you include markdown text, convert them to Slack compatible ones.
When a prompt has Slack's special syntax like <@USER_ID> or <#CHANNEL_ID>, you must keep them as-is in your response.
"""

def get_anthropic_client():
    """Get Anthropic client with API key from appropriate source"""
    environment = os.environ.get("ENVIRONMENT", "DEV").upper()
    
    if environment == "PROD":
        # Production: Use AWS Secrets Manager
        api_key = secrets_manager.get_anthropic_api_key()
        if not api_key:
            raise ValueError("Failed to retrieve Anthropic API key from Secrets Manager")
    else:
        # Development: Use environment variables (fallback to Secrets Manager if available)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        
        # Fallback to Secrets Manager if environment variable is not set
        if not api_key and os.environ.get("ANTHROPIC_API_KEY_SECRET_ARN"):
            logger.info("Falling back to Secrets Manager for Anthropic API key")
            api_key = secrets_manager.get_anthropic_api_key()
        
        if not api_key:
            raise ValueError("Failed to retrieve Anthropic API key from environment variables or Secrets Manager")
    
    return anthropic.Anthropic(api_key=api_key)

def call_llm(
    messages_in_thread: List[Dict[str, str]],
    system_content: str = DEFAULT_SYSTEM_CONTENT,
) -> str:
    try:
        client = get_anthropic_client()
    except ValueError as e:
        logger.error(f"Failed to initialize Anthropic client: {e}")
        return "I'm sorry, but I'm having trouble connecting to my AI service. Please try again later."
    
    # Convert messages to Claude's format
    messages = []
    for msg in messages_in_thread:
        if msg["role"] == "system":
            continue  # Skip system messages as they're handled differently
        messages.append({
            "role": "user" if msg["role"] == "user" else "assistant",
            "content": msg["content"]
        })
    
    try:
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=4096,
            system=system_content,
            messages=messages
        )
        logger.debug(f"Anthropic API response: {response}")
        return markdown_to_slack(response.content[0].text)
    except Exception as e:
        logger.error(f"Error calling Anthropic API: {e}")
        return "I'm sorry, but I encountered an error while processing your request. Please try again later."

# Conversion from OpenAI markdown to Slack mrkdwn
# See also: https://api.slack.com/reference/surfaces/formatting#basics
def markdown_to_slack(content: str) -> str:
    # Split the input string into parts based on code blocks and inline code
    parts = re.split(r"(?s)(```.+?```|`[^`\n]+?`)", content)

    # Apply the bold, italic, and strikethrough formatting to text not within code
    result = ""
    for part in parts:
        if part.startswith("```") or part.startswith("`"):
            result += part
        else:
            for o, n in [
                (
                    r"\*\*\*(?!\s)([^\*\n]+?)(?<!\s)\*\*\*",
                    r"_*\1*_",
                ),  # ***bold italic*** to *_bold italic_*
                (
                    r"(?<![\*_])\*(?!\s)([^\*\n]+?)(?<!\s)\*(?![\*_])",
                    r"_\1_",
                ),  # *italic* to _italic_
                (r"\*\*(?!\s)([^\*\n]+?)(?<!\s)\*\*", r"*\1*"),  # **bold** to *bold*
                (r"__(?!\s)([^_\n]+?)(?<!\s)__", r"*\1*"),  # __bold__ to *bold*
                (r"~~(?!\s)([^~\n]+?)(?<!\s)~~", r"~\1~"),  # ~~strike~~ to ~strike~
            ]:
                part = re.sub(o, n, part)
            result += part
    return result