"""Unit tests for the CLI module (cli.py)."""

import sys
from importlib.metadata import PackageNotFoundError
from unittest.mock import MagicMock, patch

import pytest

from s3_file_organizer import cli
from s3_file_organizer.cli import FALLBACK_VERSION


class TestCliArgumentParser:
    """Unit tests for command-line argument parsing."""

    def test_parse_arguments_version_flag_success(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that --version displays version information and exits with code 0."""
        test_args = ["cli.py", "--version"]

        with (
            patch.object(sys, "argv", test_args),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli.parse_arguments()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        output = captured.out + captured.err

        assert cli.FALLBACK_VERSION in output or "0.1.0" in output

    def test_parse_arguments_version_fallback_on_package_not_found(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that --version falls back to the defined default version
        and logs a warning when PackageNotFoundError occurs.
        """
        test_args = ["cli.py", "--version"]

        with (
            patch.object(sys, "argv", test_args),
            patch(
                "s3_file_organizer.cli.version",
                side_effect=PackageNotFoundError,
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli.parse_arguments()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        output = captured.out + captured.err

        assert FALLBACK_VERSION in output

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
        assert args.rules is False
        assert args.dry_run is False

    def test_parse_arguments_rules_flag(self) -> None:
        """Verify that the --rules / -r flag is parsed correctly."""
        test_args = ["cli.py", "--rules"]
        with patch.object(sys, "argv", test_args):
            args = cli.parse_arguments()

        assert args.rules is True
        assert args.bucket is None

    def test_parse_arguments_dry_run_flag(self) -> None:
        """Verify that the --dry-run flag is parsed correctly."""
        test_args = ["cli.py", "-b", "my-target-bucket", "--dry-run"]
        with patch.object(sys, "argv", test_args):
            args = cli.parse_arguments()

        assert args.bucket == "my-target-bucket"
        assert args.dry_run is True

    def test_parse_arguments_bucket_not_required_at_parser_level(self) -> None:
        """Verify that omitting the bucket does not raise SystemExit at parser level
        since it's validated later in main (allowing --rules to work without a bucket).
        """
        test_args = ["cli.py"]
        with patch.object(sys, "argv", test_args):
            args = cli.parse_arguments()

        assert args.bucket is None
        assert args.rules is False

    def test_parse_arguments_missing_bucket_returns_none(self) -> None:
        """Verify that omitting the bucket flag sets bucket to None
        at the parser level (deferred validation for --rules).
        """
        test_args = ["cli.py"]
        with patch.object(sys, "argv", test_args):
            args = cli.parse_arguments()

        assert args.bucket is None

    def test_parse_arguments_only_required_bucket(self) -> None:
        """Verify that optional arguments default to None when omitted."""
        test_args = ["cli.py", "-b", "my-target-bucket"]
        with patch.object(sys, "argv", test_args):
            args = cli.parse_arguments()

        assert args.bucket == "my-target-bucket"
        assert args.source_prefix is None
        assert args.uncategorized_prefix is None

    def test_parse_arguments_log_bucket_default(self) -> None:
        """Verify that --log-bucket defaults to 'my-logs-localstack' when omitted."""
        test_args = ["cli.py", "-b", "my-target-bucket"]
        with patch.object(sys, "argv", test_args):
            args = cli.parse_arguments()

        assert args.log_bucket == "my-logs-localstack"

    def test_parse_arguments_custom_log_bucket(self) -> None:
        """Verify that --log-bucket / -l parses custom log bucket names correctly."""
        test_args_long = [
            "cli.py",
            "-b",
            "my-target-bucket",
            "--log-bucket",
            "custom-audit-logs",
        ]
        with patch.object(sys, "argv", test_args_long):
            args = cli.parse_arguments()

        assert args.log_bucket == "custom-audit-logs"

        test_args_short = [
            "cli.py",
            "-b",
            "my-target-bucket",
            "-l",
            "short-audit-logs",
        ]
        with patch.object(sys, "argv", test_args_short):
            args_short = cli.parse_arguments()

        assert args_short.log_bucket == "short-audit-logs"


class TestCliDisplayRules:
    """Unit tests for the display_rules helper function."""

    def test_display_rules_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify that display_rules prints active extension routing rules correctly."""
        # Act
        cli.display_rules()

        # Assert
        captured = capsys.readouterr()
        assert "Active Extension Routing Rules" in captured.out
        assert "DOCUMENTS" in captured.out
        assert "IMAGES" in captured.out


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
            dry_run=False,
        )

        mock_upload_log.assert_called_once_with(
            s3_builder=mock_s3_builder,
            log_bucket="my-logs-localstack",
        )

    def test_main_dry_run_execution(
        self,
        mock_setup_logging: MagicMock,
        mock_file_organizer_cls: MagicMock,
        mock_upload_log: MagicMock,
        mock_s3_builder: MagicMock,
    ) -> None:
        """Verify that passing --dry-run correctly forwards dry_run=True
        to organize_bucket.
        """
        # Arrange
        test_args = ["cli.py", "-b", "production-bucket", "--dry-run"]

        with patch("s3_file_organizer.cli.S3Builder", return_value=mock_s3_builder):
            mock_organizer_instance = mock_file_organizer_cls.return_value
            mock_organizer_instance.organize_bucket.return_value = {
                "moved": 2,
                "skipped": 0,
                "failed": 0,
            }

            # Act
            with patch.object(sys, "argv", test_args):
                cli.main()

        # Assert
        mock_organizer_instance.organize_bucket.assert_called_once_with(
            bucket="production-bucket",
            source_prefix=None,
            uncategorized_prefix=None,
            dry_run=True,
        )

    def test_main_rules_flag_execution(self) -> None:
        """Verify that passing --rules displays rules, skips pipeline,
        and exits with code 0.
        """
        # Arrange
        test_args = ["cli.py", "--rules"]

        # Act & Assert
        with (
            patch.object(sys, "argv", test_args),
            patch("s3_file_organizer.cli.display_rules") as mock_display,
        ):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()

            assert exc_info.value.code == 0
            mock_display.assert_called_once()

    def test_main_missing_bucket_exits_with_error(self) -> None:
        """Verify that missing bucket without --rules prints error
        and exits with code 1.
        """
        # Arrange
        test_args = ["cli.py"]

        # Act & Assert
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()

            assert exc_info.value.code == 1

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

        with patch("s3_file_organizer.cli.S3Builder", return_value=mock_s3_builder):
            mock_organizer_instance = mock_file_organizer_cls.return_value
            mock_organizer_instance.organize_bucket.side_effect = RuntimeError(
                "S3 Network Timeout"
            )

            # Act
            with patch.object(sys, "argv", test_args):
                cli.main()

        # Assert
        mock_setup_logging.assert_called_once()
        mock_file_organizer_cls.assert_called_once()
        mock_organizer_instance.organize_bucket.assert_called_once()

        mock_upload_log.assert_called_once_with(
            s3_builder=mock_s3_builder,
            log_bucket="my-logs-localstack",
        )

    def test_main_with_custom_log_bucket(
        self,
        mock_setup_logging: MagicMock,
        mock_file_organizer_cls: MagicMock,
        mock_upload_log: MagicMock,
        mock_s3_builder: MagicMock,
    ) -> None:
        """Verify that a custom --log-bucket is successfully forwarded
        to upload_log_to_s3.
        """
        # Arrange
        test_args = ["cli.py", "-b", "my-bucket", "-l", "my-custom-audit-bucket"]

        with patch("s3_file_organizer.cli.S3Builder", return_value=mock_s3_builder):
            mock_organizer_instance = mock_file_organizer_cls.return_value
            mock_organizer_instance.organize_bucket.return_value = {
                "moved": 1,
                "skipped": 0,
                "failed": 0,
            }

            # Act
            with patch.object(sys, "argv", test_args):
                cli.main()

        # Assert
        mock_upload_log.assert_called_once_with(
            s3_builder=mock_s3_builder,
            log_bucket="my-custom-audit-bucket",
        )
