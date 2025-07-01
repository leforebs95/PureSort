#!/bin/bash
# scripts/setup-aws-account.sh
# One-time setup script for AWS account prerequisites

set -e

echo "Setting up AWS account prerequisites for Slack Bot..."

# Check if we're authenticated
aws sts get-caller-identity > /dev/null || {
    echo "Error: AWS CLI not configured or not authenticated"
    exit 1
}

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)

echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"

# Check if API Gateway CloudWatch role exists
echo "Checking for API Gateway CloudWatch role..."
if aws iam get-role --role-name ApiGatewayCloudWatchRole >/dev/null 2>&1; then
    echo "✓ ApiGatewayCloudWatchRole already exists"
else
    echo "Creating ApiGatewayCloudWatchRole..."
    
    aws iam create-role \
        --role-name ApiGatewayCloudWatchRole \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "apigateway.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }' > /dev/null
    
    aws iam attach-role-policy \
        --role-name ApiGatewayCloudWatchRole \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs
    
    echo "✓ Created ApiGatewayCloudWatchRole"
fi

# Set the role in API Gateway account settings
echo "Configuring API Gateway account settings..."
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/ApiGatewayCloudWatchRole"
aws apigateway update-account \
    --patch-operations "[{\"op\":\"replace\",\"path\":\"/cloudwatchRoleArn\",\"value\":\"${ROLE_ARN}\"}]" > /dev/null

echo "✓ API Gateway CloudWatch logging configured"
echo ""
echo "Account setup complete! You can now deploy your Slack Bot stacks."