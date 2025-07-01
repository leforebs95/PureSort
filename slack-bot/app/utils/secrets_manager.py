import os
import json
import boto3
import logging
from typing import Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class SecretsManager:
    """Utility class for managing AWS Secrets Manager operations"""
    
    def __init__(self):
        self.secrets_client = boto3.client('secretsmanager')
        self._cache = {}  # Simple in-memory cache for secrets
    
    def get_secret_value(self, secret_arn: str, cache: bool = True) -> Optional[str]:
        """
        Retrieve a secret value from AWS Secrets Manager
        
        Args:
            secret_arn: The ARN of the secret
            cache: Whether to cache the secret value in memory
            
        Returns:
            The secret value or None if not found
        """
        # Check cache first if caching is enabled
        if cache and secret_arn in self._cache:
            logger.debug(f"Retrieved secret from cache: {secret_arn}")
            return self._cache[secret_arn]
        
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            
            # Parse the JSON secret value
            secret_data = json.loads(response['SecretString'])
            secret_value = secret_data.get('value')
            
            if secret_value and cache:
                self._cache[secret_arn] = secret_value
                
            logger.debug(f"Successfully retrieved secret: {secret_arn}")
            return secret_value
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'DecryptionFailureException':
                logger.error(f"Failed to decrypt secret {secret_arn}: {e}")
            elif error_code == 'InternalServiceErrorException':
                logger.error(f"Internal service error retrieving secret {secret_arn}: {e}")
            elif error_code == 'InvalidParameterException':
                logger.error(f"Invalid parameter for secret {secret_arn}: {e}")
            elif error_code == 'InvalidRequestException':
                logger.error(f"Invalid request for secret {secret_arn}: {e}")
            elif error_code == 'ResourceNotFoundException':
                logger.error(f"Secret not found {secret_arn}: {e}")
            else:
                logger.error(f"Unknown error retrieving secret {secret_arn}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse secret JSON for {secret_arn}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {secret_arn}: {e}")
            return None
    
    def get_slack_bot_token(self) -> Optional[str]:
        """Get Slack Bot Token from Secrets Manager"""
        secret_arn = os.environ.get('SLACK_BOT_TOKEN_SECRET_ARN')
        if not secret_arn:
            logger.error("SLACK_BOT_TOKEN_SECRET_ARN environment variable not set")
            return None
        return self.get_secret_value(secret_arn)
    
    def get_slack_signing_secret(self) -> Optional[str]:
        """Get Slack Signing Secret from Secrets Manager"""
        secret_arn = os.environ.get('SLACK_SIGNING_SECRET_SECRET_ARN')
        if not secret_arn:
            logger.error("SLACK_SIGNING_SECRET_SECRET_ARN environment variable not set")
            return None
        return self.get_secret_value(secret_arn)
    
    def get_anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API Token from Secrets Manager"""
        secret_arn = os.environ.get('ANTHROPIC_API_KEY_SECRET_ARN')
        if not secret_arn:
            logger.error("ANTHROPIC_API_KEY_SECRET_ARN environment variable not set")
            return None
        return self.get_secret_value(secret_arn)

# Global instance for easy access
secrets_manager = SecretsManager()