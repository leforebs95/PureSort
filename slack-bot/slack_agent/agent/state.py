from typing import Literal
from langgraph.prebuilt.chat_agent_executor import AgentState


class SlackAgentState(AgentState):
    """
    State for the Slack agent.
    """
    slack_message: str
    message_classification: Literal["documentation", "bug", "feature_request"] = None