"""Unit tests for utility functions in utils.py."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from utils import upload_log_to_s3


class TestUploadLogToS3:
    """Unit tests for the upload_log_to_s3 utility function."""

    def test_upload_log_file_not_found_returns_early(
        self, mock_s3_builder: MagicMock
    ) -> None:
        """Ensure no S3 actions are performed if the local log file does not exist."""
        with patch("utils.os.path.exists", return_value=False):
            upload_log_to_s3(s3_builder=mock_s3_builder, log_bucket="logs-bucket")

        # Assert no client method was invoked
        mock_s3_builder.s3_client.head_bucket.assert_not_called()
        mock_s3_builder.s3_client.create_bucket.assert_not_called()
        mock_s3_builder.s3_client.upload_file.assert_not_called()

    def test_upload_log_bucket_already_exists(
        self, mock_s3_builder: MagicMock, tmp_path: Path
    ) -> None:
        """Ensure log is uploaded directly when the target log bucket already exists."""
        # Arrange: creates a local temporary log file
        log_file = tmp_path / "app.log"
        log_file.write_text("Execution log sample content")

        mock_client = mock_s3_builder.s3_client

        # Simulates the existence of the bucket
        mock_client.head_bucket.return_value = {}

        # Mock datetime to ensure consistency in the S3 path format
        with (
            patch("utils.LOG_FILE_PATH", str(log_file)),
            patch("utils.datetime") as mock_datetime,
        ):
            mock_datetime.datetime.now.return_value.strftime.side_effect = lambda fmt: (
                "2026" if fmt == "%Y" else ("10" if fmt == "%m" else "20261012_120000")
            )

            # Act
            upload_log_to_s3(
                s3_builder=mock_s3_builder,
                log_bucket="logs-bucket",
            )

        # Assert
        mock_client.head_bucket.assert_called_once_with(Bucket="logs-bucket")
        mock_client.create_bucket.assert_not_called()
        mock_client.upload_file.assert_called_once()

        # Validates the structure of the arguments passed during the upload
        _, kwargs = mock_client.upload_file.call_args
        assert kwargs["Bucket"] == "logs-bucket"
        assert kwargs["Filename"] == str(log_file)
        assert "organizer_logs/2026/10/run_" in kwargs["Key"]

    def test_upload_log_bucket_created_if_missing(
        self, mock_s3_builder: MagicMock, tmp_path: Path
    ) -> None:
        """Ensure target log bucket is provisioned automatically when
        head_bucket raises an error.
        """
        # Arrange
        log_file = tmp_path / "app.log"
        log_file.write_text("Execution log sample content")

        mock_client = mock_s3_builder.s3_client
        # Simulates that the bucket does not exist (raising a botocore ClientError)
        mock_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket"
        )

        with patch("utils.LOG_FILE_PATH", str(log_file)):
            # Act
            upload_log_to_s3(s3_builder=mock_s3_builder, log_bucket="logs-bucket")

        # Assert
        mock_client.head_bucket.assert_called_once_with(Bucket="logs-bucket")
        mock_client.create_bucket.assert_called_once_with(Bucket="logs-bucket")
        mock_client.upload_file.assert_called_once()

    def test_upload_log_handles_upload_error(
        self,
        mock_s3_builder: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Ensure runtime errors during upload are safely caught and
        logged as errors.
        """
        # Arrange
        caplog.set_level(logging.ERROR)
        log_file = tmp_path / "app.log"
        log_file.write_text("Execution log sample content")

        mock_client = mock_s3_builder.s3_client
        mock_client.head_bucket.return_value = {}
        mock_client.upload_file.side_effect = RuntimeError("S3 Connection Lost")

        with patch("utils.LOG_FILE_PATH", str(log_file)):
            # Act
            upload_log_to_s3(s3_builder=mock_s3_builder, log_bucket="logs-bucket")

        # Assert
        assert "Failed to upload log file to S3: S3 Connection Lost" in caplog.text
        mock_client.upload_file.assert_called_once()
