#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}
CODE_ONLY=${2:-false}

echo "Deploying Slack Bot to $ENVIRONMENT environment"

# Load environment variables
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Run Python deployment script
if [ "$CODE_ONLY" = "true" ]; then
    python scripts/deploy.py --env $ENVIRONMENT --code-only
else
    python scripts/deploy.py --env $ENVIRONMENT
fi