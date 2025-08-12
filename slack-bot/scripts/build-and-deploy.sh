#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}
COMPONENT=${2:-bot}
CODE_ONLY=${3:-false}

echo "Deploying Slack $COMPONENT to $ENVIRONMENT environment"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root directory
cd "$PROJECT_ROOT"

# Load environment variables
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Run Python deployment script with correct path
if [ "$CODE_ONLY" = "true" ]; then
    python scripts/deploy.py --env $ENVIRONMENT --component $COMPONENT --code-only
else
    python scripts/deploy.py --env $ENVIRONMENT --component $COMPONENT
fi