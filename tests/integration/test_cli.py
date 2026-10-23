"""Integration tests for the CLI module (cli.py) against LocalStack."""

import sys
from unittest.mock import patch

import pytest
from s3_file_organizer import cli
from s3_file_organizer.s3_builder import S3Builder


class TestCliIntegration:
    """Integration test suite for cli.main execution against LocalStack."""

    def test_cli_main_success_integration(
        self,
        integration_s3_builder: S3Builder,
        test_bucket: str,
        log_bucket: str,
    ) -> None:
        """Verify end-to-end execution of cli.main using LocalStack resources."""
        # Sends test files to the isolated bucket
        sample_files = {
            "inbox/integration_doc.pdf": b"PDF content",
            "inbox/integration_file.xyz": b"Unmapped content",
        }
        for key, content in sample_files.items():
            integration_s3_builder.s3_client.put_object(
                Bucket=test_bucket, Key=key, Body=content
            )

        test_args = [
            "cli.py",
            "-b",
            test_bucket,
            "-s",
            "inbox/",
            "-u",
            "custom-others/",
        ]

        with patch.object(sys, "argv", test_args):
            cli.main()

        # Validations of organized files
        objects_in_bucket = integration_s3_builder.list_objects(bucket=test_bucket)
        keys = [obj["Key"] for obj in objects_in_bucket]

        assert "documents/integration_doc.pdf" in keys
        assert "custom-others/integration_file.xyz" in keys

        # Validates log transmission using the log_bucket fixture.
        log_objects = integration_s3_builder.list_objects(bucket=log_bucket)
        assert len(log_objects) > 0

    def test_cli_main_with_long_flags_integration(
        self,
        integration_s3_builder: S3Builder,
        test_bucket: str,
        log_bucket: str,
    ) -> None:
        """Verify end-to-end CLI execution using long-form arguments
        (--bucket, --source-prefix).
        """
        # Send test file to inbox inbox/
        integration_s3_builder.s3_client.put_object(
            Bucket=test_bucket,
            Key="inbox/long_flag_doc.pdf",
            Body=b"PDF content via long flags",
        )

        # Simulates the call using exclusively the full flags.
        test_args = [
            "cli.py",
            "--bucket",
            test_bucket,
            "--source-prefix",
            "inbox/",
        ]

        with patch.object(sys, "argv", test_args):
            cli.main()

        # Validations of organized files
        objects = integration_s3_builder.list_objects(bucket=test_bucket)
        keys = [obj["Key"] for obj in objects]

        assert "inbox/long_flag_doc.pdf" not in keys
        assert "documents/long_flag_doc.pdf" in keys

        # Validates log submission
        log_objects = integration_s3_builder.list_objects(bucket=log_bucket)
        assert len(log_objects) > 0

    def test_cli_main_error_handling_integration(
        self,
        integration_s3_builder: S3Builder,
        log_bucket: str,
    ) -> None:
        """Verify that CLI handles non-existent buckets gracefully and
        persists logs in finally.
        """
        non_existent_bucket = "non-existent-bucket-12345"
        test_args = ["cli.py", "-b", non_existent_bucket]

        with patch.object(sys, "argv", test_args):
            cli.main()

        # Ensures that the error log was generated and sent to S3
        # even after the failure.
        log_objects = integration_s3_builder.list_objects(bucket=log_bucket)
        assert len(log_objects) > 0

    def test_cli_main_rules_flag_integration(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that --rules prints extension routing rules
        and exits cleanly with 0.
        """
        test_args = ["cli.py", "--rules"]

        with (
            patch.object(sys, "argv", test_args),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Active Extension Routing Rules" in captured.out

    def test_cli_main_missing_bucket_integration(self) -> None:
        """Verify that executing main without a bucket or
        --rules exits with status 1.
        """
        test_args = ["cli.py"]

        with (
            patch.object(sys, "argv", test_args),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli.main()

        assert exc_info.value.code == 1

    def test_cli_main_custom_log_bucket_integration(
        self,
        integration_s3_builder: S3Builder,
        test_bucket: str,
    ) -> None:
        """Verify end-to-end CLI execution using a custom --log-bucket
        against LocalStack.
        """
        custom_log_bucket = "my-custom-audit-bucket-test"

        test_args = [
            "cli.py",
            "-b",
            test_bucket,
            "--log-bucket",
            custom_log_bucket,
        ]

        with patch.object(sys, "argv", test_args):
            cli.main()

        # Verify that the logs were successfully sent to the custom bucket in LocalStack
        log_objects = integration_s3_builder.list_objects(bucket=custom_log_bucket)
        assert len(log_objects) > 0

        # Verify that the temporal structure (year/month) has been respected within
        # the custom bucket.
        keys = [obj["Key"] for obj in log_objects]
        assert any("organizer_logs/" in key for key in keys)
