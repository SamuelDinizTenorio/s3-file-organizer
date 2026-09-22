from typing import Any, Generator, cast
from unittest.mock import MagicMock, patch

import pytest
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError

from s3_builder import S3Builder


@pytest.fixture
def mock_boto_client() -> Generator[MagicMock, None, None]:
    """Fixture to mock boto3.client for S3Builder initialization."""
    with patch("s3_builder.boto3.client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.fixture
def s3_builder(mock_boto_client: MagicMock) -> S3Builder:
    return S3Builder()


class TestInit:
    """Group tests for S3Builder.__init__."""

    @pytest.mark.parametrize(
        "kwargs, expected_args",
        [
            (
                {},
                {
                    "service_name": "s3",
                    "endpoint_url": "http://localhost:4566",
                    "aws_access_key_id": "test",
                    "aws_secret_access_key": "test",
                    "region_name": "us-east-1",
                },
            ),
            (
                {
                    "endpoint_url": "https://localhost:4566",
                    "access_key_id": "test123",
                    "secret_access_key": "test123",
                    "region": "us-east-2",
                },
                {
                    "service_name": "s3",
                    "endpoint_url": "https://localhost:4566",
                    "aws_access_key_id": "test123",
                    "aws_secret_access_key": "test123",
                    "region_name": "us-east-2",
                },
            ),
        ],
    )
    def test_s3_builder_init_success(
        self,
        mock_boto_client: MagicMock,
        kwargs: dict[str, Any],
        expected_args: dict[str, Any],
    ) -> None:
        S3Builder(**kwargs)
        mock_boto_client.assert_called_once_with(**expected_args)

    def test_s3_builder_init_client_error(self, mock_boto_client: MagicMock) -> None:
        # Arrange
        error_response: Any = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "Access Denied",
            }
        }
        mock_boto_client.side_effect = ClientError(
            error_response=error_response, operation_name="CreateClient"
        )

        # Act & Assert
        with pytest.raises(ClientError):
            S3Builder()

    def test_s3_builder_init_generic_exception(
        self, mock_boto_client: MagicMock
    ) -> None:
        # Arrange
        mock_boto_client.side_effect = Exception("Generic error")

        # Act & Assert
        with pytest.raises(Exception, match="Generic error"):
            S3Builder()


class TestCreateBucket:
    """Group tests for S3Builder.create_bucket."""

    def test_create_bucket_success(self, s3_builder: S3Builder) -> None:
        # Arrange
        bucket_name: str = "my-bucket"
        mock_s3 = cast(MagicMock, s3_builder.s3)

        # Act
        result = s3_builder.create_bucket(bucket_name=bucket_name)

        # Assert
        mock_s3.create_bucket.assert_called_once_with(Bucket=bucket_name)
        assert result is True

    def test_create_bucket_already_owned_you(self, s3_builder: S3Builder) -> None:
        # Arrange
        bucket_name: str = "my-bucket"
        mock_s3 = cast(MagicMock, s3_builder.s3)
        error_response: Any = {
            "Error": {
                "Code": "BucketAlreadyOwnedByYou",
                "Message": "Bucket Already Owned By You",
            }
        }
        mock_s3.create_bucket.side_effect = ClientError(
            error_response=error_response, operation_name="CreateBucket"
        )

        # Act
        result = s3_builder.create_bucket(bucket_name=bucket_name)

        # Assert
        assert result is True

    def test_create_bucket_raises_client_error(self, s3_builder: S3Builder) -> None:
        # Arrange
        bucket_name: str = "my-bucket"
        mock_s3 = cast(MagicMock, s3_builder.s3)
        error_response: Any = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "Access Denied",
            }
        }
        mock_s3.create_bucket.side_effect = ClientError(
            error_response=error_response, operation_name="CreateBucket"
        )

        # Act & Assert
        with pytest.raises(ClientError):
            s3_builder.create_bucket(bucket_name=bucket_name)


class TestUploadFile:
    """Group tests for S3Builder.upload_file."""

    def test_upload_file_success(self, s3_builder: S3Builder) -> None:
        # Arrange
        filename: str = "my-file"
        bucket: str = "my-bucket"
        key: str = "my-key"
        mock_s3 = cast(MagicMock, s3_builder.s3)

        # Act
        result = s3_builder.upload_file(filename=filename, bucket=bucket, key=key)

        # Assert
        mock_s3.upload_file.assert_called_once_with(
            Filename=filename, Bucket=bucket, Key=key
        )
        assert result is True

    def test_upload_file_client_error(self, s3_builder: S3Builder) -> None:
        # Arrange
        filename: str = "my-file"
        bucket: str = "my-bucket"
        key: str = "my-key"
        mock_s3 = cast(MagicMock, s3_builder.s3)
        error_response: Any = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "Access Denied",
            }
        }
        mock_s3.upload_file.side_effect = ClientError(
            error_response=error_response, operation_name="UploadFile"
        )

        # Act & Assert
        with pytest.raises(ClientError):
            s3_builder.upload_file(filename=filename, bucket=bucket, key=key)

    def test_upload_file_bucket_not_found(self, s3_builder: S3Builder) -> None:
        # Arrange
        filename: str = "my-file"
        bucket: str = "my-bucket"
        key: str = "my-key"

        mock_s3 = cast(MagicMock, s3_builder.s3)
        mock_s3.upload_file.side_effect = S3UploadFailedError()

        # Act & Assert
        with pytest.raises(S3UploadFailedError):
            s3_builder.upload_file(filename=filename, bucket=bucket, key=key)
