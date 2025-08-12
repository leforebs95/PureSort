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
from typing import Literal

class SlackBotDeployer:
    def __init__(self, environment: str = "dev", component: Literal["bot", "agent"] = "bot"):
        self.environment = environment
        self.component = component  # "bot" or "agent"
        
        if component == "agent":
            self.stack_name = f"SlackAgent{environment.title()}"
        else:
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
        print(f"Logging into ECR: {ecr_uri}")
        region = ecr_uri.split('.')[3]  # Extract region from ECR URI
        registry_url = ecr_uri.split('/')[0]  # Get just the registry part
        
        print(f"Using region: {region}")
        print(f"Registry URL: {registry_url}")
        
        # Verify ECR repository exists
        repo_name = ecr_uri.split('/')[-1]
        try:
            result = self.run_command([
                "aws", "ecr", "describe-repositories",
                "--repository-names", repo_name,
                "--region", region
            ])
            print(f"✓ ECR repository {repo_name} exists")
        except:
            print(f"✗ ECR repository {repo_name} does not exist, creating it...")
            self.run_command([
                "aws", "ecr", "create-repository",
                "--repository-name", repo_name,
                "--region", region
            ])
            print(f"✓ Created ECR repository {repo_name}")
        
        # Get ECR login token
        result = self.run_command([
            "aws", "ecr", "get-login-password", "--region", region
        ])
        login_token = result.stdout.strip()
        
        # Docker login
        docker_login = subprocess.run([
            "docker", "login", "--username", "AWS", "--password-stdin", registry_url
        ], input=login_token, text=True)
        
        if docker_login.returncode != 0:
            print("Failed to login to ECR")
            sys.exit(1)
        
        print("✓ Successfully logged into ECR")
    
    def build_and_push_image(self, ecr_uri: str):
        """Build and push Docker image"""
        print(f"Building Docker image for {self.environment}...")
        
        # Build image - use component to determine build path
        if self.component == "agent":
            dockerfile_path = "slack_agent/Dockerfile"
            build_context = "./slack_agent"
        else:
            dockerfile_path = "slack_app/Dockerfile"
            build_context = "./slack_app"
            
        self.run_command([
            "docker", "build",
            "--platform", "linux/amd64",
            "--provenance=false",
            "-t", f"slack-bot:{self.image_tag}",
            "-f", dockerfile_path,
            build_context
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
        print("Updating Lambda function to use container image...")
        
        try:
            # First, update the function configuration to use Image package type
            print("Updating function configuration for container image...")
            self.run_command([
                "aws", "lambda", "update-function-configuration",
                "--function-name", function_name,
                "--package-type", "Image",
                "--code", f"ImageUri={ecr_uri}:latest"
            ])
            
            # Wait for update to complete
            print("Waiting for Lambda configuration update to complete...")
            self.run_command([
                "aws", "lambda", "wait", "function-updated",
                "--function-name", function_name
            ])
            
        except:
            # If configuration update fails, try code update (function might already be Image type)
            print("Configuration update failed, trying code update...")
            self.run_command([
                "aws", "lambda", "update-function-code",
                "--function-name", function_name,
                "--image-uri", f"{ecr_uri}:latest"
            ])
            
            # Wait for update to complete
            print("Waiting for Lambda code update to complete...")
            self.run_command([
                "aws", "lambda", "wait", "function-updated",
                "--function-name", function_name
            ])
        
        print("✓ Lambda function updated successfully")
    
    def create_placeholder_image_if_needed(self, ecr_uri: str):
        """Create a minimal placeholder image for Lambda if it doesn't exist"""
        try:
            # Check if placeholder tag exists
            repo_name = ecr_uri.split('/')[-1]
            region = ecr_uri.split('.')[3]
            
            result = subprocess.run([
                "aws", "ecr", "describe-images",
                "--repository-name", repo_name,
                "--image-ids", "imageTag=placeholder",
                "--region", region
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✓ Placeholder image already exists")
                return
                
        except:
            pass
        
        print("Creating placeholder image for Lambda...")
        
        # Create a minimal placeholder Dockerfile
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create minimal Lambda-compatible image
            dockerfile_content = """FROM public.ecr.aws/lambda/python:3.12
COPY lambda_function.py ${LAMBDA_TASK_ROOT}
CMD ["lambda_function.lambda_handler"]
"""
            
            lambda_content = """def lambda_handler(event, context):
    return {"statusCode": 200, "body": "Placeholder function"}
"""
            
            with open(os.path.join(temp_dir, "Dockerfile"), "w") as f:
                f.write(dockerfile_content)
            
            with open(os.path.join(temp_dir, "lambda_function.py"), "w") as f:
                f.write(lambda_content)
            
            # Build and push placeholder
            self.run_command([
                "docker", "build", "--platform", "linux/amd64", 
                "-t", "placeholder-lambda", "."
            ], cwd=temp_dir)
            
            self.run_command([
                "docker", "tag", "placeholder-lambda", f"{ecr_uri}:placeholder"
            ])
            
            self.run_command([
                "docker", "push", f"{ecr_uri}:placeholder"
            ])
            
            print("✓ Created and pushed placeholder image")

    def full_deploy(self):
        """Full deployment: infrastructure + container"""
        print(f"Starting full deployment for {self.environment}")
        
        # First, deploy infrastructure to create ECR repository
        print("Deploying ECR repository...")
        self.deploy_infrastructure()
        
        # Get ECR URI
        outputs = self.get_stack_outputs()
        ecr_uri = outputs["ECRRepositoryURI"]
        
        # Login and create placeholder if needed
        self.ecr_login(ecr_uri)
        self.create_placeholder_image_if_needed(ecr_uri)
        
        # Deploy full infrastructure (Lambda will use placeholder image)
        print("Deploying full infrastructure...")
        self.deploy_infrastructure()
        
        # Build and push the real application image
        print("Building and pushing application image...")
        self.build_and_push_image(ecr_uri)
        
        # Update Lambda with our actual image  
        outputs = self.get_stack_outputs()  # Refresh outputs
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
        # S3 bucket not used in simplified agent stack
        if 'S3BucketName' in outputs:
            print(f"S3 Bucket: {outputs['S3BucketName']}")
        print("\nNext Steps:")
        print("1. Update your Slack app's Request URL to the webhook URL above")
        print("2. Test the bot in your Slack workspace")
        print("3. Monitor logs in CloudWatch")
        print("="*60)

def main():
    parser = argparse.ArgumentParser(description="Deploy Puresort Slack Bot/Agent")
    parser.add_argument("--env", choices=["dev", "prod"], default="dev", 
                       help="Environment to deploy to")
    parser.add_argument("--component", choices=["bot", "agent"], default="bot",
                       help="Component to deploy (bot or agent)")
    parser.add_argument("--code-only", action="store_true",
                       help="Deploy code changes only (skip infrastructure)")
    
    args = parser.parse_args()
    
    deployer = SlackBotDeployer(args.env, args.component)
    
    if args.code_only:
        deployer.code_only_deploy()
    else:
        deployer.full_deploy()

if __name__ == "__main__":
    main()