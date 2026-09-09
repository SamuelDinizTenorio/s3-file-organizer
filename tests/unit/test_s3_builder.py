from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from s3_builder import S3Builder


@pytest.fixture
def mock_boto_client():
    """Fixture to mock boto3.client for S3Builder initialization."""
    with patch("s3_builder.boto3.client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_client


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
        self, mock_boto_client: MagicMock, kwargs: dict, expected_args: dict
    ):
        S3Builder(**kwargs)
        mock_boto_client.assert_called_once_with(**expected_args)

    def test_s3_builder_init_client_error(self, mock_boto_client: MagicMock):
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

    def test_s3_builder_init_generic_exception(self, mock_boto_client: MagicMock):
        # Arrange
        mock_boto_client.side_effect = Exception("Generic error")

        # Act & Assert
        with pytest.raises(Exception, match="Generic error"):
            S3Builder()


class TestCreateBucket:
    """Group tests for S3Builder.create_bucket."""

    def test_create_bucket_success(self, mock_boto_client: MagicMock):
        # Arrange
        builder = S3Builder()
        mock_instance = mock_boto_client.return_value

        # act
        result = builder.create_bucket(bucket_name="my-bucket")

        # assert
        mock_instance.create_bucket.assert_called_once_with(Bucket="my-bucket")
        assert result is True

    def test_create_bucket_already_owned_you(self, mock_boto_client: MagicMock):
        # Arrange
        builder = S3Builder()
        mock_instance = mock_boto_client.return_value
        error_response: Any = {
            "Error": {
                "Code": "BucketAlreadyOwnedByYou",
                "Message": "Bucket Already Owned By You",
            }
        }
        mock_instance.create_bucket.side_effect = ClientError(
            error_response=error_response, operation_name="CreateBucket"
        )

        # Act
        result = builder.create_bucket("my-bucket")

        # act and assert
        assert result is True

    def test_create_bucket_raises_client_error(self, mock_boto_client: MagicMock):
        # Arrange
        builder = S3Builder()
        mock_instance = mock_boto_client.return_value
        error_response: Any = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "Access Denied",
            }
        }
        mock_instance.create_bucket.side_effect = ClientError(
            error_response=error_response, operation_name="CreateBucket"
        )

        # Act & Assert
        with pytest.raises(ClientError):
            builder.create_bucket("my-bucket")
