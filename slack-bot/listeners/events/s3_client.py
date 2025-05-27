import boto3
from botocore.exceptions import ClientError
import logging

class S3Client:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.logger = logging.getLogger(__name__)

    def upload_file(self, file_path, bucket, object_name=None):
        """Upload a file to an S3 bucket
        
        Args:
            file_path (str): Path to file to upload
            bucket (str): Bucket to upload to
            object_name (str): S3 object name. If not specified file_path is used
            
        Returns:
            bool: True if file was uploaded, else False
        """
        if object_name is None:
            object_name = file_path

        try:
            self.s3_client.upload_file(file_path, bucket, object_name)
        except ClientError as e:
            self.logger.error(e)
            return False
        return True

    def list_objects(self, bucket, prefix=''):
        """List objects in an S3 bucket
        
        Args:
            bucket (str): Bucket to list objects from
            prefix (str): Only fetch objects whose key starts with this prefix
            
        Returns:
            list: List of object keys, empty list if error occurs
        """
        try:
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            return [obj['Key'] for obj in response.get('Contents', [])]
        except ClientError as e:
            self.logger.error(e)
            return []