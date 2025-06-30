#!/usr/bin/env python3
"""
Deployment script for Puresort Slack Bot using CDK
"""
import argparse
import subprocess
import sys
import os
import json
from datetime import datetime
from pathlib import Path

class SlackBotDeployer:
    def __init__(self, environment: str = "dev"):
        self.environment = environment
        self.stack_name = f"SlackBot{environment.title()}"
        self.image_tag = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.project_root = Path(__file__).parent.parent
        
    def run_command(self, command: list, cwd: str = None) -> subprocess.CompletedProcess:
        """Run a command and handle errors"""
        print(f"Running: {' '.join(command)}")
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            sys.exit(1)
        return result
    
    def get_stack_outputs(self) -> dict:
        """Get CDK stack outputs"""
        result = self.run_command([
            "aws", "cloudformation", "describe-stacks",
            "--stack-name", self.stack_name,
            "--query", "Stacks[0].Outputs",
            "--output", "json"
        ])
        outputs = json.loads(result.stdout)
        return {output["OutputKey"]: output["OutputValue"] for output in outputs}
    
    def ecr_login(self, ecr_uri: str):
        """Login to ECR"""
        print("Logging into ECR...")
        region = ecr_uri.split('.')[3]  # Extract region from ECR URI
        
        # Get ECR login token
        result = self.run_command([
            "aws", "ecr", "get-login-password", "--region", region
        ])
        login_token = result.stdout.strip()
        
        # Docker login
        docker_login = subprocess.run([
            "docker", "login", "--username", "AWS", "--password-stdin", ecr_uri
        ], input=login_token, text=True)
        
        if docker_login.returncode != 0:
            print("Failed to login to ECR")
            sys.exit(1)
    
    def build_and_push_image(self, ecr_uri: str):
        """Build and push Docker image"""
        print(f"Building Docker image for {self.environment}...")
        
        # Build image
        self.run_command([
            "docker", "build",
            "--platform", "linux/amd64",
            "-t", f"slack-bot:{self.image_tag}",
            "-f", "app/Dockerfile",
            "./app"
        ], cwd=str(self.project_root))
        
        # Tag for ECR
        self.run_command([
            "docker", "tag", 
            f"slack-bot:{self.image_tag}",
            f"{ecr_uri}:{self.image_tag}"
        ])
        
        self.run_command([
            "docker", "tag",
            f"slack-bot:{self.image_tag}", 
            f"{ecr_uri}:latest"
        ])
        
        # Push to ECR
        print("Pushing image to ECR...")
        self.run_command(["docker", "push", f"{ecr_uri}:{self.image_tag}"])
        self.run_command(["docker", "push", f"{ecr_uri}:latest"])
    
    def deploy_infrastructure(self):
        """Deploy CDK infrastructure"""
        print(f"Deploying CDK infrastructure for {self.environment}...")
        
        # Change to infrastructure directory
        infra_dir = self.project_root / "infrastructure"
        
        # Install CDK dependencies
        # self.run_command(["pip", "install", "-r", "requirements.txt"], cwd=str(infra_dir))
        
        # CDK deploy
        self.run_command([
            "cdk", "deploy", self.stack_name,
            "--require-approval", "never"
        ], cwd=str(self.project_root))
    
    def update_lambda_function(self, ecr_uri: str, function_name: str):
        """Update Lambda function with new image"""
        print("Updating Lambda function...")
        
        self.run_command([
            "aws", "lambda", "update-function-code",
            "--function-name", function_name,
            "--image-uri", f"{ecr_uri}:latest"
        ])
        
        # Wait for update to complete
        print("Waiting for Lambda update to complete...")
        self.run_command([
            "aws", "lambda", "wait", "function-updated",
            "--function-name", function_name
        ])
    
    def full_deploy(self):
        """Full deployment: infrastructure + container"""
        print(f"Starting full deployment for {self.environment}")
        
        # Deploy infrastructure first
        self.deploy_infrastructure()
        
        # Get outputs
        outputs = self.get_stack_outputs()
        ecr_uri = outputs["ECRRepositoryURI"]
        
        # Build and push image
        self.ecr_login(ecr_uri)
        self.build_and_push_image(ecr_uri)
        
        # Update Lambda
        function_name = outputs["LambdaFunctionName"]
        self.update_lambda_function(ecr_uri, function_name)
        
        # Print summary
        self.print_deployment_summary(outputs)
    
    def code_only_deploy(self):
        """Deploy only code changes (build + push + update Lambda)"""
        print(f"Deploying code changes for {self.environment}")
        
        # Get existing stack outputs
        outputs = self.get_stack_outputs()
        ecr_uri = outputs["ECRRepositoryURI"]
        function_name = outputs["LambdaFunctionName"]
        
        # Build and push image
        self.ecr_login(ecr_uri)
        self.build_and_push_image(ecr_uri)
        
        # Update Lambda
        self.update_lambda_function(ecr_uri, function_name)
        
        print("Code deployment completed!")
    
    def print_deployment_summary(self, outputs: dict):
        """Print deployment summary"""
        print("\n" + "="*60)
        print("DEPLOYMENT SUMMARY")
        print("="*60)
        print(f"Environment: {self.environment}")
        print(f"Stack Name: {self.stack_name}")
        print(f"Image Tag: {self.image_tag}")
        print(f"ECR Repository: {outputs['ECRRepositoryURI']}")
        print(f"Lambda Function: {outputs['LambdaFunctionName']}")
        print(f"Slack Webhook URL: {outputs['ApiGatewayUrl']}")
        print(f"S3 Bucket: {outputs['S3BucketName']}")
        print("\nNext Steps:")
        print("1. Update your Slack app's Request URL to the webhook URL above")
        print("2. Test the bot in your Slack workspace")
        print("3. Monitor logs in CloudWatch")
        print("="*60)

def main():
    parser = argparse.ArgumentParser(description="Deploy Puresort Slack Bot")
    parser.add_argument("--env", choices=["dev", "prod"], default="dev", 
                       help="Environment to deploy to")
    parser.add_argument("--code-only", action="store_true",
                       help="Deploy code changes only (skip infrastructure)")
    
    args = parser.parse_args()
    
    deployer = SlackBotDeployer(args.env)
    
    if args.code_only:
        deployer.code_only_deploy()
    else:
        deployer.full_deploy()

if __name__ == "__main__":
    main()