from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_lambda as _lambda,
    aws_ecr as ecr,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_logs as logs,
    aws_ssm as ssm,
    aws_s3 as s3,
)
from constructs import Construct
import os

class SlackBotStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, environment: str = "dev", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.environment = environment
        
        # ECR Repository - retained on deletion to preserve images
        self.ecr_repository = ecr.Repository(
            self, "SlackBotRepository",
            repository_name=f"puresort-slack-bot-{environment}",
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
        
        # S3 Bucket for file storage (if needed)
        self.s3_bucket = s3.Bucket(
            self, "SlackBotBucket",
            bucket_name=f"puresort-slack-bot-{environment}-{self.account}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN
        )
        
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
                        # SSM Parameter access for secrets
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ssm:GetParameter",
                                "ssm:GetParameters",
                            ],
                            resources=[
                                f"arn:aws:ssm:{self.region}:{self.account}:parameter/{environment}/slack-bot/*"
                            ]
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
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
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
        
        # Create SSM parameters for secrets (if environment variables are provided)
        self._create_ssm_parameters()
        
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
    
    def _create_ssm_parameters(self):
        """Create SSM parameters for secrets if environment variables exist"""
        secrets = {
            "SLACK_BOT_TOKEN": "bot-token",
            "SLACK_SIGNING_SECRET": "signing-secret", 
            "ANTHROPIC_API_TOKEN": "anthropic-api-key"
        }
        
        for env_var, param_name in secrets.items():
            value = os.environ.get(env_var)
            if value:
                ssm.StringParameter(
                    self, f"SlackBot{param_name.replace('-', '').title()}",
                    parameter_name=f"/{self.environment}/slack-bot/{param_name}",
                    string_value=value,
                    type=ssm.ParameterType.SECURE_STRING,
                    description=f"Slack Bot {param_name.replace('-', ' ').title()}",
                )