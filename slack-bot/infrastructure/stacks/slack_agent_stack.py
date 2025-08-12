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
)
from constructs import Construct

class SlackAgentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, environment: str = "dev", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Reference existing ECR Repository
        self.ecr_repository = ecr.Repository.from_repository_name(
            self, "SlackAgentRepository",
            repository_name=f"puresort-slack-agent-{environment}"
        )
        
        # Lambda execution role
        lambda_role = iam.Role(
            self, "SlackAgentLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Create log group for Lambda function
        log_group = logs.LogGroup(
            self, "SlackAgentLogGroup",
            log_group_name=f"/aws/lambda/puresort-slack-agent-{environment}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Lambda function using your preloaded ECR container image
        self.lambda_function = _lambda.DockerImageFunction(
            self, "SlackAgentFunction",
            function_name=f"puresort-slack-agent-{environment}",
            code=_lambda.DockerImageCode.from_ecr(
                repository=self.ecr_repository,
                tag="latest"
            ),
            role=lambda_role,
            timeout=Duration.seconds(300),
            memory_size=1024,
            environment={
                "ENVIRONMENT": environment.upper(),
                "LOG_LEVEL": "INFO" if environment == "prod" else "DEBUG",
            },
            log_group=log_group,
        )
        
        # API Gateway for Slack webhooks
        self.api_gateway = apigw.RestApi(
            self, "SlackAgentApi",
            rest_api_name=f"puresort-slack-agent-{environment}",
            description="API Gateway for Slack Agent webhook endpoints"
        )
        
        # Lambda integration
        lambda_integration = apigw.LambdaIntegration(self.lambda_function)
        
        # Slack webhook endpoints
        slack_resource = self.api_gateway.root.add_resource("slack")
        events_resource = slack_resource.add_resource("events")
        events_resource.add_method("POST", lambda_integration)
        
        # Outputs
        CfnOutput(
            self, "ECRRepositoryURI",
            value=self.ecr_repository.repository_uri,
            description="ECR Repository URI for Docker images"
        )
        
        CfnOutput(
            self, "LambdaFunctionName",
            value=self.lambda_function.function_name,
            description="Lambda Function Name"
        )
        
        CfnOutput(
            self, "ApiGatewayUrl",
            value=f"{self.api_gateway.url}slack/events",
            description="Slack webhook URL for Events API"
        )