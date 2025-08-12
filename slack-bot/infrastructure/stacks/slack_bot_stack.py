from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    SecretValue,
    aws_lambda as _lambda,
    aws_ecr as ecr,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
    aws_s3 as s3,
)
from constructs import Construct
import os
import json
from dotenv import load_dotenv

load_dotenv()

class SlackBotStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, environment: str = "dev", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self._environment = environment
        
        # ECR Repository - get existing or create new with conditional logic
        self.ecr_repository = self._get_or_create_ecr_repository()
        
        # S3 Bucket - get existing or create new with conditional logic
        self.s3_bucket = self._get_or_create_s3_bucket()
        
        # Secrets - get existing or create new with conditional logic
        self.secrets = self._get_or_create_secrets()
        
        # Lambda execution role
        lambda_role = iam.Role(
            self, "SlackBotLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "SlackBotPolicy": iam.PolicyDocument(
                    statements=[
                        # Secrets Manager access
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "secretsmanager:GetSecretValue",
                            ],
                            resources=[f"{secret.secret_arn}*" for secret in self.secrets.values()]
                        ),
                        # S3 access for file storage
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                            ],
                            resources=[f"{self.s3_bucket.bucket_arn}/*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["s3:ListBucket"],
                            resources=[self.s3_bucket.bucket_arn]
                        )
                    ]
                )
            }
        )
        
        # Create log group for Lambda function
        log_group = logs.LogGroup(
            self, "SlackBotLogGroup",
            log_group_name=f"/aws/lambda/puresort-slack-bot-{environment}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Lambda function using your existing code
        self.lambda_function = _lambda.Function(
            self, "SlackBotFunction",
            function_name=f"puresort-slack-bot-{environment}",
            code=_lambda.Code.from_ecr_image(
                repository=self.ecr_repository,
                tag_or_digest="latest"
            ),
            handler=_lambda.Handler.FROM_IMAGE,
            runtime=_lambda.Runtime.FROM_IMAGE,
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "ENVIRONMENT": "PROD" if environment == "prod" else "DEV",
                "S3_BUCKET_NAME": self.s3_bucket.bucket_name,
                "LOG_LEVEL": "INFO" if environment == "prod" else "DEBUG",
                # Add secret ARNs as environment variables for easy access
                "SLACK_BOT_TOKEN_SECRET_NAME": f"{self._environment}/slack-bot/slack-bot-token",
                "SLACK_SIGNING_SECRET_SECRET_NAME": f"{self._environment}/slack-bot/slack-signing-secret", 
                "ANTHROPIC_API_KEY_SECRET_NAME": f"{self._environment}/slack-bot/anthropic-api-key",
            },
            log_group=log_group,
            reserved_concurrent_executions=10 if environment == "prod" else 5,
        )
        
        # API Gateway for Slack webhooks
        self.api_gateway = apigw.RestApi(
            self, "SlackBotApi",
            rest_api_name=f"puresort-slack-bot-{environment}",
            description="API Gateway for Slack Bot webhook endpoints",
            deploy_options=apigw.StageOptions(
                stage_name=environment,
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=environment != "prod",
            ),
        )
        
        # Lambda integration
        lambda_integration = apigw.LambdaIntegration(
            self.lambda_function,
            proxy=True,
            integration_responses=[
                apigw.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        # Slack webhook endpoints
        slack_resource = self.api_gateway.root.add_resource("slack")
        events_resource = slack_resource.add_resource("events")
        events_resource.add_method(
            "POST", 
            lambda_integration,
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )
        
        # Outputs
        CfnOutput(
            self, "ECRRepositoryURI",
            value=self.ecr_repository.repository_uri,
            description="ECR Repository URI for Docker images",
            export_name=f"{environment}-slack-bot-ecr-uri"
        )
        
        CfnOutput(
            self, "LambdaFunctionName",
            value=self.lambda_function.function_name,
            description="Lambda Function Name",
            export_name=f"{environment}-slack-bot-lambda-name"
        )
        
        CfnOutput(
            self, "ApiGatewayUrl",
            value=f"{self.api_gateway.url}slack/events",
            description="Slack webhook URL for Events API",
            export_name=f"{environment}-slack-bot-webhook-url"
        )
        
        CfnOutput(
            self, "S3BucketName",
            value=self.s3_bucket.bucket_name,
            description="S3 Bucket for file storage",
            export_name=f"{environment}-slack-bot-s3-bucket"
        )

        # Output secret ARNs for reference
        for secret_name, secret in self.secrets.items():
            CfnOutput(
                self, f"{secret_name.replace('_', '')}SecretArn",
                value=secret.secret_arn,
                description=f"Secret ARN for {secret_name}",
                export_name=f"{environment}-slack-bot-{secret_name.lower().replace('_', '-')}-secret-arn"
            )

    def _get_or_create_ecr_repository(self):
        """Get existing ECR repository or create new one"""
        repository_name = f"puresort-slack-bot-{self._environment}"
        
        try:
            # Try to reference existing repository
            print(f"Attempting to reference existing ECR repository: {repository_name}")
            repository = ecr.Repository.from_repository_name(
                self, "ExistingSlackBotRepository",
                repository_name=repository_name
            )
            print(f"Successfully referenced existing ECR repository: {repository_name}")
            return repository
            
        except Exception as e:
            # Create new repository if it doesn't exist
            print(f"ECR repository {repository_name} not found, creating new one. Error: {str(e)}")
            
            repository = ecr.Repository(
                self, "SlackBotRepository",
                repository_name=repository_name,
                image_scan_on_push=True,
                lifecycle_rules=[
                    ecr.LifecycleRule(
                        description="Keep only 10 most recent images",
                        max_image_count=10,
                        tag_status=ecr.TagStatus.ANY,
                    ),
                    ecr.LifecycleRule(
                        description="Delete untagged images after 7 days",
                        max_image_age=Duration.days(7),
                        tag_status=ecr.TagStatus.UNTAGGED,
                    )
                ],
                removal_policy=RemovalPolicy.RETAIN
            )
            
            print(f"Created new ECR repository: {repository_name}")
            return repository

    def _get_or_create_s3_bucket(self):
        """Get existing S3 bucket or create new one"""
        bucket_name = f"puresort-slack-bot-{self._environment}-{self.account}"
        
        try:
            # Try to reference existing bucket
            print(f"Attempting to reference existing S3 bucket: {bucket_name}")
            bucket = s3.Bucket.from_bucket_name(
                self, "ExistingSlackBotBucket",
                bucket_name=bucket_name
            )
            print(f"Successfully referenced existing S3 bucket: {bucket_name}")
            return bucket
            
        except Exception as e:
            # Create new bucket if it doesn't exist
            print(f"S3 bucket {bucket_name} not found, creating new one. Error: {str(e)}")
            
            bucket = s3.Bucket(
                self, "SlackBotBucket",
                bucket_name=bucket_name,
                versioned=True,
                encryption=s3.BucketEncryption.S3_MANAGED,
                public_read_access=False,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                removal_policy=RemovalPolicy.RETAIN
            )
            
            print(f"Created new S3 bucket: {bucket_name}")
            return bucket
        
    def _get_or_create_secrets(self) -> dict:
        """Get existing secrets or create new ones using conditional logic"""
        
        secrets_config = {
            "SLACK_BOT_TOKEN": "slack-bot-token",
            "SLACK_SIGNING_SECRET": "slack-signing-secret", 
            "ANTHROPIC_API_KEY": "anthropic-api-key"
        }
        
        secrets = {}
        
        for env_var, secret_name in secrets_config.items():
            secrets[env_var] = self._get_or_create_secret(env_var, secret_name)
        
        return secrets
    
    def _secret_exists(self, secret_name: str) -> bool:
        """Check if a secret actually exists in AWS Secrets Manager"""
        try:
            print(f"Checking if secret exists: {secret_name}")
            import boto3
            secrets_client = boto3.client('secretsmanager')
            secrets_client.describe_secret(SecretId=secret_name)
            print(f"✓ Secret exists: {secret_name}")
            return True
        except Exception as e:
            if hasattr(e, 'response') and e.response.get('Error', {}).get('Code') == 'ResourceNotFoundException':
                print(f"✗ Secret not found: {secret_name}")
                return False
            else:
                print(f"Error checking secret existence for {secret_name}: {e}")
                # If we can't determine, assume it doesn't exist and try to create
                return False

    def _get_or_create_secret(self, env_var: str, secret_name: str) -> secretsmanager.Secret:
        """Get existing secret or create new one"""
        secret_full_name = f"{self._environment}/slack-bot/{secret_name}"
        if self._secret_exists(secret_full_name):
            # Secret exists, create reference
            return secretsmanager.Secret.from_secret_name_v2(
                self, f"Existing{env_var.replace('_', '').title()}Secret",
                secret_name=secret_full_name
            )
        else:
            # Secret doesn't exist, create it
            local_value = os.environ.get(env_var)
            if not local_value:
                raise ValueError(f"Environment variable {env_var} is required for creating new secret")
            
            return secretsmanager.Secret(
                self, f"SlackBot{env_var.replace('_', '').title()}Secret",
                secret_name=secret_full_name,
                description=f"Slack Bot {secret_name.replace('-', ' ').title()} for {self._environment} environment",
                secret_string_value=SecretValue.unsafe_plain_text(
                    json.dumps({"value": local_value})
                ),
                removal_policy=RemovalPolicy.RETAIN
            )