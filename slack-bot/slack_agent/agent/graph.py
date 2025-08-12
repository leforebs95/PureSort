from typing import List, Literal

from dotenv import load_dotenv

from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent

from agent.state import SlackAgentState
from agent.types import MessageClassification
from agent.tools import (
    search_documentation,
    create_feature_request,
    file_bug_report,
)

load_dotenv()

prompt_instructions = {
    "documentation": "Questions about the product, different apis, or existing features.",
    "bug": "Issues with the product, different apis, or existing features.",
    "feature_request": "Suggestions for new features or improvements.",
}

classify_system_message = """
< Role >
You are a helpful assistant on a slack channel. You are a top-notch customer support agent. Your job is to classify incoming messages from user to assist them.
</ Role >

< Instructions >

Classify the below message into one of these categories:

1. documentation - The message is about documentation.
2. bug - The message is about a bug.
3. feature_request - The message is about a feature request.

</ Instructions >

< Rules >
Messages that are about documentation:
{triage_docs}

Messages that are about a bug:
{triage_bug}

Messages that are about a feature request:
{triage_feature_request}
</ Rules >

< Few shot examples >
{examples}
</ Few shot examples >
"""

def classify_message(state: SlackAgentState) -> Command[Literal["documentation_agent", "bug_agent", "feature_request_agent", "__end__"]]:
    """
    Classify the message into a category.
    """
    system_prompt = classify_system_message.format(
        triage_docs=prompt_instructions["documentation"],
        triage_bug=prompt_instructions["bug"],
        triage_feature_request=prompt_instructions["feature_request"],
        examples=None,
    )
    user_prompt = """
    Classify the following message:
    {message}
    """
    user_prompt = user_prompt.format(message=state["slack_message"])
    llm = init_chat_model(
        model="anthropic:claude-3-5-sonnet-20240620",
    ).with_structured_output(MessageClassification)

    result = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )

    if result.category == "documentation":
        goto = "documentation_agent"
        update = {
            "messages": [HumanMessage(content=f"Search for documentation regarding: {state['slack_message']}")],
            "message_classification": result.category,
        }
    elif result.category == "bug":
        goto = "bug_agent"
        update = {
            "messages": [HumanMessage(content=f"File a bug report regarding: {state['slack_message']}")],
            "message_classification": result.category,
        }
    elif result.category == "feature_request":
        goto = "feature_request_agent"
        update = {
            "messages": [HumanMessage(content=f"Suggest a feature regarding: {state['slack_message']}")],
            "message_classification": result.category,
        }
    else:
        raise ValueError(f"Invalid classification: {result.classification}")

    return Command(goto=goto, update=update)

def create_prompt(state: SlackAgentState) -> List[BaseMessage]:
    """
    Create a prompt for the agent.
    """
    context_injection = {
        "documentation": "searches for documentation relevant to a message from a slack channel.",
        "bug": "files a bug report regarding a message from a slack channel.",
        "feature_request": "suggests a feature regarding a message from a slack channel.",
    }
    context_injection = context_injection[state["message_classification"]]
    return [
        SystemMessage(content=f"You are a helpful assistant that {context_injection} to a message from a slack channel.")
    ] + state["messages"]

documentation_agent = create_react_agent(
    "anthropic:claude-sonnet-4-20250514",
    prompt=create_prompt,
    tools=[search_documentation],
    state_schema=SlackAgentState,
)

bug_agent = create_react_agent(
    "anthropic:claude-sonnet-4-20250514",
    prompt=create_prompt,
    tools=[file_bug_report],
    state_schema=SlackAgentState,
)

feature_request_agent = create_react_agent(
    "anthropic:claude-sonnet-4-20250514",
    prompt=create_prompt,
    tools=[create_feature_request],
    state_schema=SlackAgentState,
)


graph = StateGraph(SlackAgentState)

graph.add_node("classify_message", classify_message)
graph.add_node("documentation_agent", documentation_agent)
graph.add_node("bug_agent", bug_agent)
graph.add_node("feature_request_agent", feature_request_agent)
graph.set_entry_point("classify_message")

slack_agent = graph.compile()