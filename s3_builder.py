import logging

import boto3
from boto3.exceptions import S3UploadFailedError
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
        """Initialize the S3Builder client.

        Args:
            endpoint_url (str): Target URL for the S3 service
                (e.g., LocalStack endpoint).
            access_key_id (str): AWS access key ID.
            secret_access_key (str): AWS secret access key.
            region (str): AWS region name.

        Raises:
            ClientError: If an error occurs while creating the S3 client.
            Exception: For any other unexpected errors during initialization.
        """
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
        """Create an S3 bucket.

        Args:
            bucket_name (str): Name of the target S3 bucket that will be created.

        Returns:
            bool: True if the bucket was created successfully.

        Raises:
            ClientError: If an error occurs during interaction with S3 API.
        """
        try:
            self.s3.create_bucket(Bucket=bucket_name)
            logger.info("Successfully created bucket %s", bucket_name)
            return True
        except ClientError as ex:
            error_code = ex.response["Error"]["Code"]
            if error_code == "BucketAlreadyOwnedByYou":
                logger.warning("Bucket %s is already owned by you: %s", bucket_name, ex)
                return True
            logger.warning(
                "An unexpected error occurred while creating bucket %s: %s",
                bucket_name,
                ex,
            )
            raise

    def upload_file(self, filename: str, bucket: str, key: str) -> bool:
        """Upload a local file to an S3 bucket.

        Args:
            filename (str): Path to the local file to upload.
            bucket (str): Name of the target S3 bucket.
            key (str): S3 object key (path/filename in the bucket).

        Returns:
            bool: True if the file was uploaded successfully.

        Raises:
            ClientError: If an error occurs during interaction with S3 API.
            Exception: If an unexpected error occurs while uploading file.
        """
        try:
            self.s3.upload_file(Filename=filename, Bucket=bucket, Key=key)
            logger.info("Successfully uploaded %s to %s/%s", filename, bucket, key)
            return True
        except (ClientError, S3UploadFailedError) as ex:
            logger.warning("An unexpected error while upload the file: %s", ex)
            raise
        except FileNotFoundError:
            logger.warning("Local file not found: %s", filename)
            raise
        except Exception as ex:
            logger.warning(
                "An unexpected error occurred while uploading file %s to %s/%s: %s",
                filename,
                bucket,
                key,
                ex,
            )
            raise
