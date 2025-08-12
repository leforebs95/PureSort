import json
import logging
from typing import Dict, Any
from agent.graph import slack_agent

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function for the Slack Agent
    """
    try:
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        # Handle API Gateway events
        if 'httpMethod' in event:
            return handle_api_gateway_event(event, context)
        
        # Handle direct invocation
        return handle_direct_invocation(event, context)
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }

def handle_api_gateway_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle API Gateway HTTP events (Slack webhooks)
    """
    try:
        # Parse the request body
        body = json.loads(event.get('body', '{}'))
        
        # Handle Slack URL verification challenge
        if body.get('type') == 'url_verification':
            return {
                'statusCode': 200,
                'body': body.get('challenge', '')
            }
        
        # Handle Slack events
        if body.get('type') == 'event_callback':
            slack_event = body.get('event', {})
            
            # Skip bot messages to avoid loops
            if slack_event.get('bot_id'):
                return {
                    'statusCode': 200,
                    'body': json.dumps({'status': 'ignored_bot_message'})
                }
            
            # Process the message with the agent
            message = slack_event.get('text', '')
            if message:
                response = process_message_with_agent(message)
                logger.info(f"Agent response: {response}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'success'})
        }
        
    except Exception as e:
        logger.error(f"Error handling API Gateway event: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Bad request'})
        }

def handle_direct_invocation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle direct Lambda invocation
    """
    try:
        message = event.get('message', '')
        if not message:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Message is required'})
            }
        
        response = process_message_with_agent(message)
        
        return {
            'statusCode': 200,
            'body': json.dumps({'response': response})
        }
        
    except Exception as e:
        logger.error(f"Error handling direct invocation: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def process_message_with_agent(message: str) -> str:
    """
    Process a message using the Slack agent
    """
    try:
        # Initialize the agent state
        initial_state = {
            "slack_message": message,
            "messages": [],
            "message_classification": None
        }
        
        # Run the agent
        result = slack_agent.invoke(initial_state)
        
        # Extract the response from the agent
        final_messages = result.get("messages", [])
        if final_messages and hasattr(final_messages[-1], 'content'):
            return final_messages[-1].content
        
        return "I processed your message successfully."
        
    except Exception as e:
        logger.error(f"Error processing message with agent: {str(e)}")
        return f"Sorry, I encountered an error processing your message: {str(e)}"

def main():
    """
    Local testing function
    """
    test_event = {
        'message': 'How do I use the search API?'
    }
    
    result = lambda_handler(test_event, None)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
