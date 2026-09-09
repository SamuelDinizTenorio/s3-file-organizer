import logging

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_s3 import S3Client

logger = logging.getLogger("main")


class S3Builder:
    """Builder utility for provisioning AWS S3."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:4566",
        access_key_id: str = "test",
        secret_access_key: str = "test",
        region: str = "us-east-1",
    ) -> None:
        try:
            self.s3: S3Client = boto3.client(
                service_name="s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region,
            )
        except ClientError as ex:
            logger.warning("Failed in create S3 client: %s", ex)
            raise
        except Exception as ex:
            logger.warning("Unexpected error while initializing S3Builder: %s", ex)
            raise

    def create_bucket(self, bucket_name: str) -> bool:
        """Create an S3 bucket."""
        try:
            self.s3.create_bucket(Bucket=bucket_name)
            logger.info("The bucket %s created with sucessfull", bucket_name)
            return True
        except ClientError as ex:
            error_code = ex.response["Error"]["Code"]
            if error_code == "BucketAlreadyOwnedByYou":
                logger.warning(
                    "The bucket %s already Owned By You: %s", bucket_name, ex
                )
                return True
            logger.warning("An unexpected error while create the bucket: %s", ex)
            raise
