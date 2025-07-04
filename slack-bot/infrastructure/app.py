#!/usr/bin/env python3
import os
from aws_cdk import App, Environment
from stacks.slack_bot_stack import SlackBotStack

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

app = App()

# Get AWS account and region from environment or CDK context
account = os.environ.get('CDK_DEFAULT_ACCOUNT') or app.node.try_get_context('account')
region = os.environ.get('CDK_DEFAULT_REGION') or app.node.try_get_context('region') or 'us-east-1'

env = Environment(account=account, region=region)

# Development stack
dev_stack = SlackBotStack(
    app, 
    "SlackBotDev",
    environment="dev",
    env=env,
    tags={
        "Environment": "dev",
        "Project": "PuresortSlackBot",
        "Owner": "Engineering"
    }
)

# Production stack  
prod_stack = SlackBotStack(
    app,
    "SlackBotProd", 
    environment="prod",
    env=env,
    tags={
        "Environment": "prod",
        "Project": "PuresortSlackBot", 
        "Owner": "Engineering"
    }
)

app.synth()