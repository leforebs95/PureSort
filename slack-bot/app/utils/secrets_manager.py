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
    
    def get_secret_value_by_name(self, secret_name: str, cache: bool = True) -> Optional[str]:
        """
        Retrieve a secret value from AWS Secrets Manager
        
        Args:
            secret_name: The name of the secret
            cache: Whether to cache the secret value in memory
            
        Returns:
            The secret value or None if not found
        """
        # Check cache first if caching is enabled
        if cache and secret_name in self._cache:
            logger.debug(f"Retrieved secret from cache: {secret_name}")
            return self._cache[secret_name]
        
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            
            # Parse the JSON secret value
            secret_data = json.loads(response['SecretString'])
            secret_value = secret_data.get('value')
            
            if secret_value and cache:
                self._cache[secret_name] = secret_value
                
            logger.debug(f"Successfully retrieved secret: {secret_name}")
            return secret_value
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'DecryptionFailureException':
                logger.error(f"Failed to decrypt secret {secret_name}: {e}")
            elif error_code == 'InternalServiceErrorException':
                logger.error(f"Internal service error retrieving secret {secret_name}: {e}")
            elif error_code == 'InvalidParameterException':
                logger.error(f"Invalid parameter for secret {secret_name}: {e}")
            elif error_code == 'InvalidRequestException':
                logger.error(f"Invalid request for secret {secret_name}: {e}")
            elif error_code == 'ResourceNotFoundException':
                logger.error(f"Secret not found {secret_name}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse secret JSON for {secret_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {secret_name}: {e}")
            return None
    
    def get_slack_bot_token(self) -> Optional[str]:
        """Get Slack Bot Token from Secrets Manager"""
        secret_name = os.environ.get('SLACK_BOT_TOKEN_SECRET_NAME')
        if not secret_name:
            logger.error("SLACK_BOT_TOKEN_SECRET_ARN environment variable not set")
            return None
        return self.get_secret_value_by_name(secret_name)
    
    def get_slack_signing_secret(self) -> Optional[str]:
        """Get Slack Signing Secret from Secrets Manager"""
        secret_name = os.environ.get('SLACK_SIGNING_SECRET_SECRET_NAME')
        if not secret_name:
            logger.error("SLACK_SIGNING_SECRET_SECRET_NAME environment variable not set")
            return None
        return self.get_secret_value_by_name(secret_name)
    
    def get_anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API Token from Secrets Manager"""
        secret_name = os.environ.get('ANTHROPIC_API_KEY_SECRET_NAME')
        if not secret_name:
            logger.error("ANTHROPIC_API_KEY_SECRET_NAME environment variable not set")
            return None
        return self.get_secret_value_by_name(secret_name)

# Global instance for easy access
secrets_manager = SecretsManager()