"""Unit tests for the CLI module (cli.py)."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from s3_file_organizer import cli


class TestCliArgumentParser:
    """Unit tests for command-line argument parsing."""

    def test_parse_arguments_required_and_optional_flags(self) -> None:
        """Verify that required and optional CLI arguments are parsed correctly."""
        test_args = [
            "cli.py",
            "-b",
            "my-target-bucket",
            "-s",
            "inbox/",
            "-u",
            "others/",
        ]
        with patch.object(sys, "argv", test_args):
            args = cli.parse_arguments()

        assert args.bucket == "my-target-bucket"
        assert args.source_prefix == "inbox/"
        assert args.uncategorized_prefix == "others/"

    def test_parse_arguments_missing_bucket_raises_system_exit(self) -> None:
        """Verify that omitting the required bucket flag (-b/--bucket)
        exits the program.
        """
        test_args = ["cli.py"]
        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit):
            cli.parse_arguments()

    def test_parse_arguments_only_required_bucket(self) -> None:
        """Verify that optional arguments default to None when omitted."""
        test_args = ["cli.py", "-b", "my-target-bucket"]
        with patch.object(sys, "argv", test_args):
            args = cli.parse_arguments()

        assert args.bucket == "my-target-bucket"
        assert args.source_prefix is None
        assert args.uncategorized_prefix is None


class TestCliMainExecution:
    """Unit tests for the main execution pipeline in cli.py."""

    def test_main_happy_path(
        self,
        mock_setup_logging: MagicMock,
        mock_file_organizer_cls: MagicMock,
        mock_upload_log: MagicMock,
        mock_s3_builder: MagicMock,
    ) -> None:
        """Verify the complete successful execution flow inside main using fixtures."""
        # Arrange
        test_args = ["cli.py", "-b", "production-bucket", "-s", "incoming/"]

        with patch("s3_file_organizer.cli.S3Builder", return_value=mock_s3_builder):
            mock_organizer_instance = mock_file_organizer_cls.return_value
            mock_organizer_instance.organize_bucket.return_value = {
                "moved": 5,
                "skipped": 0,
                "failed": 0,
            }

            # Act
            with patch.object(sys, "argv", test_args):
                cli.main()

        # Assert
        mock_setup_logging.assert_called_once()
        mock_file_organizer_cls.assert_called_once()

        mock_organizer_instance.organize_bucket.assert_called_once_with(
            bucket="production-bucket",
            source_prefix="incoming/",
            uncategorized_prefix=None,
        )

        mock_upload_log.assert_called_once_with(
            s3_builder=mock_s3_builder,
            log_bucket="my-logs-localstack",
        )

    def test_main_handles_organization_exception_and_finally_runs(
        self,
        mock_setup_logging: MagicMock,
        mock_file_organizer_cls: MagicMock,
        mock_upload_log: MagicMock,
        mock_s3_builder: MagicMock,
    ) -> None:
        """Verify that exceptions during organization are caught and
        log upload still executes in finally.
        """
        # Arrange
        test_args = ["cli.py", "-b", "error-bucket"]

        # Injeta a fixture mock_s3_builder na chamada de S3Builder dentro do CLI
        with patch("s3_file_organizer.cli.S3Builder", return_value=mock_s3_builder):
            mock_organizer_instance = mock_file_organizer_cls.return_value
            mock_organizer_instance.organize_bucket.side_effect = RuntimeError(
                "S3 Network Timeout"
            )

            # Act
            with patch.object(sys, "argv", test_args):
                # Não deve propagar a exceção pois o main captura com try/except
                cli.main()

        # Assert
        mock_setup_logging.assert_called_once()
        mock_file_organizer_cls.assert_called_once()
        mock_organizer_instance.organize_bucket.assert_called_once()

        # O bloco finally deve garantir que o upload do log ocorreu mesmo após o erro,
        # utilizando o S3Builder fornecido pela fixture compartilhada.
        mock_upload_log.assert_called_once_with(
            s3_builder=mock_s3_builder,
            log_bucket="my-logs-localstack",
        )
