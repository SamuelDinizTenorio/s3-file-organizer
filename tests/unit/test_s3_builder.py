import logging
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
            # Case 1: Default values
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
            # Case 2: Overwriting all parameters
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
            # Case 3: Overwriting only the region and the endpoint (partial)
            (
                {
                    "endpoint_url": "http://s3.local:4566",
                    "region": "sa-east-1",
                },
                {
                    "service_name": "s3",
                    "endpoint_url": "http://s3.local:4566",
                    "aws_access_key_id": "test",
                    "aws_secret_access_key": "test",
                    "region_name": "sa-east-1",
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

    @pytest.mark.parametrize(
        "exception_instance, match_pattern, expected_log_msg",
        [
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "AccessDenied",
                            "Message": "Access Denied",
                        }
                    },
                    "CreateClient",
                ),
                "Access Denied",
                "Failed in create S3 client: An error occurred (AccessDenied) "
                "when calling the CreateClient operation: Access Denied",
            ),
            (
                Exception("Generic error"),
                "Generic error",
                "Unexpected error while initializing S3Builder: Generic error",
            ),
        ],
    )
    def test_s3_builder_init_errors(
        self,
        mock_boto_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        exception_instance: Exception,
        match_pattern: str,
        expected_log_msg: str,
    ) -> None:
        # Arrange
        mock_boto_client.side_effect = exception_instance

        expected_log: tuple[str, int, str] = (
            "s3_builder",
            logging.ERROR,
            expected_log_msg,
        )

        # Act & Assert
        with pytest.raises(type(exception_instance), match=match_pattern):
            S3Builder()

        mock_boto_client.assert_called_once()
        assert expected_log in caplog.record_tuples


class TestCreateBucket:
    """Group tests for S3Builder.create_bucket."""

    @pytest.mark.parametrize(
        "side_effect, expected_log_level, expected_log_msg",
        [
            (
                None,
                logging.INFO,
                "Successfully created bucket my-bucket",
            ),
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "BucketAlreadyOwnedByYou",
                            "Message": "Bucket Already Owned By You",
                        }
                    },
                    "CreateBucket",
                ),
                logging.WARNING,
                "Bucket my-bucket is already owned by you: "
                "An error occurred (BucketAlreadyOwnedByYou) "
                "when calling the CreateBucket operation: "
                "Bucket Already Owned By You",
            ),
        ],
    )
    def test_create_bucket_success_and_warnings(
        self,
        s3_builder: S3Builder,
        caplog: pytest.LogCaptureFixture,
        side_effect: Exception | None,
        expected_log_level: int,
        expected_log_msg: str,
    ) -> None:
        # Arrange
        caplog.set_level(logging.INFO)
        bucket_name: str = "my-bucket"
        mock_s3 = cast(MagicMock, s3_builder.s3)
        mock_s3.create_bucket.side_effect = side_effect

        expected_log: tuple[str, int, str] = (
            "s3_builder",
            expected_log_level,
            expected_log_msg,
        )

        # Act
        result = s3_builder.create_bucket(bucket_name=bucket_name)

        # Assert
        mock_s3.create_bucket.assert_called_once_with(Bucket=bucket_name)
        assert result is True
        assert expected_log in caplog.record_tuples

    @pytest.mark.parametrize(
        "exception_instance, match_pattern, expected_log_msg",
        [
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "AccessDenied",
                            "Message": "Access Denied",
                        }
                    },
                    "CreateBucket",
                ),
                "Access Denied",
                "Failed to create bucket my-bucket due to S3 API error: "
                "An error occurred (AccessDenied) "
                "when calling the CreateBucket operation: Access Denied",
            ),
            (
                Exception("Unexpected error"),
                "Unexpected error",
                "An unexpected error occurred while creating bucket my-bucket: "
                "Unexpected error",
            ),
        ],
    )
    def test_create_bucket_errors(
        self,
        s3_builder: S3Builder,
        caplog: pytest.LogCaptureFixture,
        exception_instance: Exception,
        match_pattern: str,
        expected_log_msg: str,
    ) -> None:
        # Arrange
        bucket_name: str = "my-bucket"
        mock_s3 = cast(MagicMock, s3_builder.s3)
        mock_s3.create_bucket.side_effect = exception_instance

        expected_log: tuple[str, int, str] = (
            "s3_builder",
            logging.ERROR,
            expected_log_msg,
        )

        # Act & Assert
        with pytest.raises(type(exception_instance), match=match_pattern):
            s3_builder.create_bucket(bucket_name=bucket_name)

        mock_s3.create_bucket.assert_called_once_with(Bucket=bucket_name)
        assert expected_log in caplog.record_tuples


class TestUploadFile:
    """Group tests for S3Builder.upload_file."""

    @pytest.mark.parametrize(
        "filename, bucket, key",
        [
            ("my-file.txt", "my-bucket", "my-key.txt"),
            ("path/to/local/file.pdf", "my-bucket", "documents/file.pdf"),
            ("image.png", "other-bucket", "2026/09/image.png"),
        ],
    )
    def test_upload_file_success_variations(
        self,
        s3_builder: S3Builder,
        caplog: pytest.LogCaptureFixture,
        filename: str,
        bucket: str,
        key: str,
    ) -> None:
        # Arrange
        caplog.set_level(logging.INFO)
        mock_s3 = cast(MagicMock, s3_builder.s3)

        expected_log: tuple[str, int, str] = (
            "s3_builder",
            logging.INFO,
            f"Successfully uploaded {filename} to {bucket}/{key}",
        )

        # Act
        result = s3_builder.upload_file(filename=filename, bucket=bucket, key=key)

        # Assert
        mock_s3.upload_file.assert_called_once_with(
            Filename=filename, Bucket=bucket, Key=key
        )
        assert result is True
        assert expected_log in caplog.record_tuples

    @pytest.mark.parametrize(
        "exception_instance, match_pattern, expected_log_msg",
        [
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "AccessDenied",
                            "Message": "Access Denied",
                        }
                    },
                    "UploadFile",
                ),
                "Access Denied",
                "Failed to upload the file my-file to my-bucket/my-key due to "
                "S3 API error: An error occurred (AccessDenied) "
                "when calling the UploadFile operation: Access Denied",
            ),
            (
                S3UploadFailedError("Failed to upload file"),
                "Failed to upload file",
                "Failed to upload the file my-file to my-bucket/my-key due to "
                "S3 API error: Failed to upload file",
            ),
            (
                FileNotFoundError(2, "No such file or directory", "my-file"),
                "my-file",
                "Local file not found: my-file",
            ),
            (
                Exception("Unexpected upload error"),
                "Unexpected upload error",
                "An unexpected error occurred while uploading file "
                "my-file to my-bucket/my-key: Unexpected upload error",
            ),
        ],
    )
    def test_upload_file_errors(
        self,
        s3_builder: S3Builder,
        caplog: pytest.LogCaptureFixture,
        exception_instance: Exception,
        match_pattern: str,
        expected_log_msg: str,
    ) -> None:
        # Arrange
        filename: str = "my-file"
        bucket: str = "my-bucket"
        key: str = "my-key"

        mock_s3 = cast(MagicMock, s3_builder.s3)
        mock_s3.upload_file.side_effect = exception_instance

        expected_log: tuple[str, int, str] = (
            "s3_builder",
            logging.ERROR,
            expected_log_msg,
        )

        # Act & Assert
        with pytest.raises(type(exception_instance), match=match_pattern):
            s3_builder.upload_file(filename=filename, bucket=bucket, key=key)

        mock_s3.upload_file.assert_called_once_with(
            Filename=filename, Bucket=bucket, Key=key
        )
        assert expected_log in caplog.record_tuples
