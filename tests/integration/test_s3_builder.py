from typing import Generator

import pytest
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
    """tests for the create bucket method

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
