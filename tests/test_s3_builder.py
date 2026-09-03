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
        error_response = {"Error": {"Code": "500", "Message": "Error"}}
        mock_boto_client.side_effect = ClientError(
            error_response=error_response, operation_name="CreateClient"
        )

        with pytest.raises(ClientError):
            S3Builder()

    def test_s3_builder_init_generic_exception(self, mock_boto_client: MagicMock):
        mock_boto_client.side_effect = Exception("Generic error")

        with pytest.raises(Exception, match="Generic error"):
            S3Builder()
