#!/bin/bash

# Slack Bot AWS Deployment Script with ECR Container Images
set -e

# Configuration
STACK_NAME="slack-bot-puresort"
REGION="us-west-1"
ENVIRONMENT="prod"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Check if required tools are installed
check_requirements() {
    print_status "Checking requirements..."
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi
    
    print_status "Requirements check passed."
}

# Load environment variables
load_env() {
    if [ -f ".env" ]; then
        print_status "Loading environment variables from .env file..."
        export $(grep -v '^#' .env | xargs)
    else
        print_warning ".env file not found. Make sure environment variables are set."
    fi
}

# Validate required environment variables
validate_env() {
    print_status "Validating environment variables..."
    
    if [ -z "$SLACK_BOT_TOKEN" ]; then
        print_error "SLACK_BOT_TOKEN is not set"
        exit 1
    fi
    
    if [ -z "$SLACK_SIGNING_SECRET" ]; then
        print_error "SLACK_SIGNING_SECRET is not set"
        exit 1
    fi
    
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        print_error "ANTHROPIC_API_KEY is not set"
        exit 1
    fi
    
    print_status "Environment variables validated."
}

# Get AWS Account ID
get_aws_account_id() {
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    if [ $? -ne 0 ]; then
        print_error "Failed to get AWS Account ID. Check your AWS credentials."
        exit 1
    fi
    print_info "AWS Account ID: $AWS_ACCOUNT_ID"
}

# Deploy CloudFormation stack (creates ECR repository)
deploy_infrastructure() {
    print_status "Deploying CloudFormation infrastructure..."
    
    aws cloudformation deploy \
        --template-file cloudformation.yaml \
        --stack-name $STACK_NAME \
        --parameter-overrides \
            Environment=$ENVIRONMENT \
            SlackBotToken="$SLACK_BOT_TOKEN" \
            SlackSigningSecret="$SLACK_SIGNING_SECRET" \
            AnthropicApiKey="$ANTHROPIC_API_KEY" \
            ImageTag="$IMAGE_TAG" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $REGION
    
    print_status "CloudFormation infrastructure deployed successfully."
}

# Get ECR repository URI
get_ecr_repository() {
    ECR_REPOSITORY_URI=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryURI`].OutputValue' \
        --output text)
    
    if [ -z "$ECR_REPOSITORY_URI" ]; then
        print_error "Failed to get ECR repository URI from CloudFormation stack."
        exit 1
    fi
    
    print_info "ECR Repository URI: $ECR_REPOSITORY_URI"
}

# Login to ECR
ecr_login() {
    print_status "Logging into ECR..."
    
    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REPOSITORY_URI
    
    if [ $? -ne 0 ]; then
        print_error "Failed to login to ECR."
        exit 1
    fi
    
    print_status "Successfully logged into ECR."
}

# Build Docker image
build_docker_image() {
    print_status "Building Docker image for linux/amd64 platform..."
    
    # Use the Lambda-specific Dockerfile with explicit platform targeting
    docker build --platform linux/amd64 --provenance=false -f Dockerfile.lambda -t slack-bot:$IMAGE_TAG .
    
    if [ $? -ne 0 ]; then
        print_error "Failed to build Docker image."
        exit 1
    fi
    
    # Tag for ECR
    docker tag slack-bot:$IMAGE_TAG $ECR_REPOSITORY_URI:$IMAGE_TAG
    docker tag slack-bot:$IMAGE_TAG $ECR_REPOSITORY_URI:latest
    
    print_status "Docker image built and tagged successfully for linux/amd64."
}

# Push Docker image to ECR
push_docker_image() {
    print_status "Pushing Docker image to ECR..."
    
    docker push $ECR_REPOSITORY_URI:$IMAGE_TAG
    docker push $ECR_REPOSITORY_URI:latest
    
    if [ $? -ne 0 ]; then
        print_error "Failed to push Docker image to ECR."
        exit 1
    fi
    
    print_status "Docker image pushed to ECR successfully."
}

# Update Lambda function with new image
update_lambda_function() {
    print_status "Updating Lambda function with new container image..."
    
    FUNCTION_NAME=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
        --output text)
    
    # Update function code with new image
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --image-uri $ECR_REPOSITORY_URI:$IMAGE_TAG \
        --region $REGION \
        --output table
    
    # Wait for update to complete
    print_status "Waiting for Lambda function update to complete..."
    aws lambda wait function-updated \
        --function-name $FUNCTION_NAME \
        --region $REGION
    
    print_status "Lambda function updated successfully."
}

# Get API Gateway URL and display summary
get_deployment_summary() {
    print_status "Getting deployment summary..."
    
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text)
    
    echo ""
    print_status "Deployment completed successfully!"
    echo ""
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│                    DEPLOYMENT SUMMARY                       │"
    echo "├─────────────────────────────────────────────────────────────┤"
    echo "│ Stack Name: $STACK_NAME"
    echo "│ Region: $REGION"
    echo "│ Environment: $ENVIRONMENT"
    echo "│ Image Tag: $IMAGE_TAG"
    echo "│"
    echo "│ ECR Repository:"
    echo "│ $ECR_REPOSITORY_URI"
    echo "│"
    echo "│ API Gateway URL:"
    echo "│ $API_URL"
    echo "│"
    echo "│ Next Steps:"
    echo "│ 1. Update your Slack app's Request URL to the API Gateway URL above"
    echo "│ 2. Test the bot in your Slack workspace"
    echo "│ 3. Monitor logs in CloudWatch"
    echo "│ 4. View container insights in ECR"
    echo "└─────────────────────────────────────────────────────────────┘"
    echo ""
}

# Cleanup function
cleanup() {
    print_status "Cleaning up local Docker images..."
    
    # Remove local images to save space
    docker rmi slack-bot:$IMAGE_TAG 2>/dev/null || true
    docker rmi $ECR_REPOSITORY_URI:$IMAGE_TAG 2>/dev/null || true
    docker rmi $ECR_REPOSITORY_URI:latest 2>/dev/null || true
    
    print_status "Cleanup completed."
}

# Create initial infrastructure (ECR repo only)
create_initial_infrastructure() {
    print_status "Creating initial infrastructure (ECR repository)..."
    
    # Deploy stack with a placeholder image first
    aws cloudformation deploy \
        --template-file cloudformation.yaml \
        --stack-name $STACK_NAME \
        --parameter-overrides \
            Environment=$ENVIRONMENT \
            SlackBotToken="$SLACK_BOT_TOKEN" \
            SlackSigningSecret="$SLACK_SIGNING_SECRET" \
            AnthropicApiKey="$ANTHROPIC_API_KEY" \
            ImageTag="placeholder" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $REGION \
        --no-execute-changeset 2>/dev/null || true
    
    # Check if ECR repository exists, if not create it separately
    REPO_NAME="${STACK_NAME}-slack-bot"
    aws ecr describe-repositories --repository-names $REPO_NAME --region $REGION 2>/dev/null || {
        print_status "Creating ECR repository..."
        aws ecr create-repository --repository-name $REPO_NAME --region $REGION
    }
}

# Full deployment function
deploy() {
    print_status "Starting full deployment process..."
    
    check_requirements
    load_env
    validate_env
    get_aws_account_id
    
    # First, ensure ECR repository exists
    create_initial_infrastructure
    
    # Get ECR repository URI (create if doesn't exist)
    ECR_REPOSITORY_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${STACK_NAME}-slack-bot"
    
    ecr_login
    build_docker_image
    push_docker_image
    deploy_infrastructure
    get_deployment_summary
    cleanup
}

# Update code only (build and push new image, update Lambda)
update_code() {
    print_status "Updating Lambda code with new container image..."
    
    check_requirements
    load_env
    get_aws_account_id
    get_ecr_repository
    ecr_login
    build_docker_image
    push_docker_image
    update_lambda_function
    get_deployment_summary
    cleanup
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        deploy
        ;;
    "update-code")
        update_code
        ;;
    "build-only")
        print_status "Building Docker image only..."
        check_requirements
        load_env
        get_aws_account_id
        get_ecr_repository
        ecr_login
        build_docker_image
        push_docker_image
        cleanup
        ;;
    "cleanup")
        cleanup
        ;;
    "delete-stack")
        print_warning "Deleting CloudFormation stack: $STACK_NAME"
        print_warning "This will also delete the ECR repository and all images!"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Delete all images in ECR repository first
            aws ecr list-images --repository-name "${STACK_NAME}-slack-bot" --region $REGION --query 'imageIds[*]' --output json | \
            jq '.[] | select(.imageTag != null) | {imageTag: .imageTag}' | \
            aws ecr batch-delete-image --repository-name "${STACK_NAME}-slack-bot" --region $REGION --image-ids file:///dev/stdin 2>/dev/null || true
            
            aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION
            print_status "Stack deletion initiated."
        else
            print_status "Stack deletion cancelled."
        fi
        ;;
    *)
        echo "Usage: $0 [deploy|update-code|build-only|cleanup|delete-stack]"
        echo ""
        echo "Commands:"
        echo "  deploy       - Full deployment with infrastructure and container (default)"
        echo "  update-code  - Build and push new container image, update Lambda function"
        echo "  build-only   - Build and push container image only"
        echo "  cleanup      - Clean up local Docker images"
        echo "  delete-stack - Delete the CloudFormation stack and ECR repository"
        echo ""
        echo "Environment Variables:"
        echo "  IMAGE_TAG    - Docker image tag (default: timestamp)"
        echo "  STACK_NAME   - CloudFormation stack name (default: slack-bot-puresort)"
        echo "  REGION       - AWS region (default: us-east-1)"
        echo "  ENVIRONMENT  - Deployment environment (default: prod)"
        exit 1
        ;;
esac