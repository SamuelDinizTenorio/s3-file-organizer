from pathlib import Path
from typing import Generator

import pytest
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError

from s3_builder import S3Builder


@pytest.fixture
def s3_builder() -> Generator[S3Builder, None, None]:
    # Setup
    builder_instance = S3Builder(
        endpoint_url="http://localhost:4566",
        access_key_id="test",
        secret_access_key="test",
        region="us-east-1",
    )

    yield builder_instance

    response = builder_instance.s3.list_buckets()

    # Teardown
    for bucket in response.get("Buckets", []):
        s3 = builder_instance.s3
        objects = s3.list_objects_v2(Bucket=bucket["Name"])

        for obj in objects.get("Contents", []):
            s3.delete_object(Bucket=bucket["Name"], Key=obj["Key"])

        s3.delete_bucket(Bucket=bucket["Name"])


class TestCreateBucket:
    """Group tests for S3Builder.create_bucket

    Architecture Note:
        The case 'BucketAlreadyExists' (when another AWS account owns the bucket)
        it is not validated with LocalStack (Community). This case validation is
        covered by unit tests using mocks.
    """

    def test_create_bucket_success(self, s3_builder: S3Builder) -> None:
        # Arrange
        bucket_name = "my-bucket"

        # Act
        result = s3_builder.create_bucket(bucket_name=bucket_name)

        # Assert
        assert result is True

        response = s3_builder.s3.list_buckets()
        bucket_names = [bucket["Name"] for bucket in response.get("Buckets", [])]
        assert bucket_name in bucket_names

    def test_create_bucket_already_owned_by_you(self, s3_builder: S3Builder) -> None:
        # Arrange
        bucket_name = "meu-bucket-de-teste"

        # Act
        s3_builder.create_bucket(bucket_name)
        result = s3_builder.create_bucket(bucket_name)

        # Assert
        assert result is True

        response = s3_builder.s3.list_buckets()
        bucket_names = [bucket["Name"] for bucket in response.get("Buckets", [])]
        assert bucket_name in bucket_names
        assert bucket_names.count(bucket_name) == 1

    def test_create_bucket_invalid_name(self, s3_builder: S3Builder) -> None:
        # Arrange
        invalid_name = "My_Bucket"

        # Act & Assert
        with pytest.raises(ClientError) as exc_info:
            s3_builder.create_bucket(bucket_name=invalid_name)

        assert exc_info.value.response["Error"]["Code"] == "InvalidBucketName"


class TestUploadFile:
    """Group tests for S3Builder.upload_file."""

    def test_upload_file_success(self, s3_builder: S3Builder, tmp_path: Path) -> None:
        # Arrange: Create the bucket and a local temporary file.
        bucket_name: str = "upload-bucket-test"
        key: str = "test_file.txt"
        s3_builder.create_bucket(bucket_name)

        file_path = tmp_path / "test_file.txt"
        file_path.write_text("Hello, LocalStack!")

        # Act: Upload the file
        result = s3_builder.upload_file(
            filename=str(file_path), bucket=bucket_name, key=key
        )

        # Assert: Validate the `True` return value and confirm with `head_object`
        assert result is True

        obj = s3_builder.s3.head_object(Bucket=bucket_name, Key=key)
        assert obj["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_upload_file_bucket_not_found(
        self, s3_builder: S3Builder, tmp_path: Path
    ) -> None:
        # Arrange
        bucket_name: str = "upload-bucket-test"
        key: str = "test_file.txt"
        file_path = tmp_path / "test_file.txt"
        file_path.write_text("Hello, LocalStack!")

        # Act & Assert
        with pytest.raises(S3UploadFailedError) as exc_info:
            s3_builder.upload_file(filename=str(file_path), bucket=bucket_name, key=key)

        assert "NoSuchBucket" in str(exc_info.value)

    def test_upload_file_file_not_found(self, s3_builder: S3Builder) -> None:
        # Arrange
        file_path: str = "test_file.txt"
        bucket_name: str = "upload-bucket-test"
        key: str = "test_file.txt"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            s3_builder.upload_file(filename=str(file_path), bucket=bucket_name, key=key)
