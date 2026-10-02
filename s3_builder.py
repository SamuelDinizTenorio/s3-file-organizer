import logging

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError
from mypy_boto3_s3 import S3Client
from mypy_boto3_s3.type_defs import CopySourceTypeDef, ObjectTypeDef

logger = logging.getLogger(__name__)


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
            self.s3_client: S3Client = boto3.client(
                service_name="s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region,
            )
        except ClientError as ex:
            logger.exception("Failed in create S3 client: %s", ex)
            raise
        except Exception as ex:
            logger.exception("Unexpected error while initializing S3Builder: %s", ex)
            raise

    def create_bucket(self, bucket_name: str) -> bool:
        """Create an S3 bucket.

        Args:
            bucket_name (str): Name of the target S3 bucket that will be created.

        Returns:
            bool: True if the bucket was created successfully.

        Raises:
            ClientError: If an error occurs during interaction with S3 API.
            Exception: If an unexpected error occurs while creating the bucket.
        """
        try:
            self.s3_client.create_bucket(Bucket=bucket_name)
            logger.info("Successfully created bucket %s", bucket_name)
            return True
        except ClientError as ex:
            error_code = ex.response["Error"]["Code"]
            if error_code == "BucketAlreadyOwnedByYou":
                logger.warning("Bucket %s is already owned by you: %s", bucket_name, ex)
                return True
            logger.exception(
                "Failed to create bucket %s due to S3 API error: %s",
                bucket_name,
                ex,
            )
            raise
        except Exception as ex:
            logger.exception(
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
            S3UploadFailedError: If the upload operation fails.
            FileNotFoundError: If the local file is not found.
            Exception: If an unexpected error occurs while uploading file.
        """
        try:
            self.s3_client.upload_file(Filename=filename, Bucket=bucket, Key=key)
            logger.info("Successfully uploaded %s to %s/%s", filename, bucket, key)
            return True
        except (ClientError, S3UploadFailedError) as ex:
            logger.exception(
                "Failed to upload the file %s to %s/%s due to S3 API error: %s",
                filename,
                bucket,
                key,
                ex,
            )
            raise
        except FileNotFoundError:
            logger.exception("Local file not found: %s", filename)
            raise
        except Exception as ex:
            logger.exception(
                "An unexpected error occurred while uploading file %s to %s/%s: %s",
                filename,
                bucket,
                key,
                ex,
            )
            raise

    def list_objects(self, bucket: str, prefix: str = "") -> list[ObjectTypeDef]:
        """List objects in an S3 bucket with an optional prefix.

        Args:
            bucket (str): Name of the S3 bucket.
            prefix (str, optional): Key prefix to filter objects. Defaults to "".

        Returns:
            list[dict[str, Any]]: List of dictionary metadata representing S3 objects.

        Raises:
            ClientError: If an error occurs during interaction with S3 API.
            Exception: If an unexpected error occurs while listing objects.
        """
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            objects: list[ObjectTypeDef] = []

            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if "Contents" in page:
                    objects.extend(page["Contents"])

            logger.info(
                "Successfully listed %d object(s) in bucket '%s' with prefix '%s'",
                len(objects),
                bucket,
                prefix,
            )
            return objects
        except ClientError as ex:
            logger.exception(
                "Failed to list objects in bucket %s due to S3 API error: %s",
                bucket,
                ex,
            )
            raise
        except Exception as ex:
            logger.exception(
                "An unexpected error occurred while listing objects in bucket %s: %s",
                bucket,
                ex,
            )
            raise

    def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> bool:
        """Copy an object from a source S3 location to a destination S3 location.

        Args:
            source_bucket (str): Name of the source S3 bucket.
            source_key (str): S3 key of the source object.
            dest_bucket (str): Name of the destination S3 bucket.
            dest_key (str): S3 key for the copied object in the destination bucket.

        Returns:
            bool: True if the object was copied successfully.

        Raises:
            ClientError: If an error occurs during interaction with S3 API.
            Exception: If an unexpected error occurs while copying object.
        """
        copy_source: CopySourceTypeDef = {"Bucket": source_bucket, "Key": source_key}
        try:
            self.s3_client.copy_object(
                CopySource=copy_source, Bucket=dest_bucket, Key=dest_key
            )
            logger.info(
                "Successfully copied %s/%s to %s/%s",
                source_bucket,
                source_key,
                dest_bucket,
                dest_key,
            )
            return True
        except ClientError as ex:
            logger.exception(
                "Failed to copy object %s/%s to %s/%s due to S3 API error: %s",
                source_bucket,
                source_key,
                dest_bucket,
                dest_key,
                ex,
            )
            raise
        except Exception as ex:
            logger.exception(
                "An unexpected error occurred while copying %s/%s to %s/%s: %s",
                source_bucket,
                source_key,
                dest_bucket,
                dest_key,
                ex,
            )
            raise

    def delete_object(self, bucket: str, key: str) -> bool:
        """Delete an object from an S3 bucket.

        Args:
            bucket (str): Name of the S3 bucket.
            key (str): S3 object key to delete.

        Returns:
            bool: True if the object was deleted successfully.

        Raises:
            ClientError: If an error occurs during interaction with S3 API.
            Exception: If an unexpected error occurs while deleting the object.
        """
        try:
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            logger.info(
                "The object %s/%s was successfully deleted",
                bucket,
                key,
            )
            return True
        except ClientError as ex:
            logger.exception(
                "Failed to delete object %s/%s due to S3 API error: %s",
                bucket,
                key,
                ex,
            )
            raise
        except Exception as ex:
            logger.exception(
                "An unexpected error occurred while deleting the object %s/%s: %s",
                bucket,
                key,
                ex,
            )
            raise

    def move_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> bool:
        """Move an object from a source S3 location to a destination S3 location.

        Args:
            source_bucket (str): Name of the source S3 bucket.
            source_key (str): S3 key of the source object.
            dest_bucket (str): Name of the destination S3 bucket.
            dest_key (str): S3 key for the moved object in the destination bucket.

        Returns:
            bool: True if the object was moved successfully.

        Raises:
            ClientError: If an error occurs during interaction with S3 API.
            Exception: If an unexpected error occurs while moving object.
        """
        try:
            self.copy_object(
                source_bucket=source_bucket,
                source_key=source_key,
                dest_bucket=dest_bucket,
                dest_key=dest_key,
            )
            self.delete_object(bucket=source_bucket, key=source_key)

            logger.info(
                "Successfully moved object %s/%s to %s/%s",
                source_bucket,
                source_key,
                dest_bucket,
                dest_key,
            )
            return True
        except ClientError as ex:
            logger.exception(
                "Failed to move object %s/%s to %s/%s due to S3 API error: %s",
                source_bucket,
                source_key,
                dest_bucket,
                dest_key,
                ex,
            )
            raise
        except Exception as ex:
            logger.exception(
                "An unexpected error occurred while moving %s/%s to %s/%s: %s",
                source_bucket,
                source_key,
                dest_bucket,
                dest_key,
                ex,
            )
            raise
