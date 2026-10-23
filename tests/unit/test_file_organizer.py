from unittest.mock import MagicMock, call

import pytest
from mypy_boto3_s3.type_defs import ObjectTypeDef

from s3_file_organizer.file_organizer import FileOrganizer
from s3_file_organizer.s3_builder import S3Builder


class TestFileOrganizerInit:
    """Unit tests for the FileOrganizer.__init__ method."""

    def test_init_with_default_rules(self, s3_builder: S3Builder) -> None:
        """Ensure default rules are loaded and mapped into extension_map when
        extension_rules is None.
        """
        organizer = FileOrganizer(s3_builder=s3_builder)

        assert organizer.s3_builder == s3_builder
        assert organizer.extension_map.get(".pdf") == "documents"
        assert organizer.extension_map.get(".csv") == "data"
        assert organizer.extension_map.get(".png") == "images"

    def test_init_with_custom_rules(self, s3_builder: S3Builder) -> None:
        """Ensure custom rules override the default extension mapping dictionary."""
        custom_rules = {
            "custom_docs": [".pdf"],
            "custom_data": [".csv"],
        }
        organizer = FileOrganizer(s3_builder=s3_builder, extension_rules=custom_rules)

        assert organizer.s3_builder == s3_builder
        assert organizer.extension_map.get(".pdf") == "custom_docs"
        assert organizer.extension_map.get(".csv") == "custom_data"


class TestGetTargetPrefix:
    """Unit tests for the get_target_prefix method."""

    @pytest.mark.parametrize(
        "source_key, expected_prefix",
        [
            ("record.pdf", "documents"),
            ("inbox/subfolder/RECORD.PDF", "documents"),  # Uppercase extension
            ("data.csv", "data"),
            ("photo.PNG", "images"),  # Uppercase extension
            ("document.txt", "documents"),  # Extensão mapeada válida
            ("unknown_file.xyz", None),  # Unmapped extension
            ("README", None),  # No extension
            ("inbox/.gitignore", None),  # Hidden file without valid extension
        ],
    )
    def test_get_target_prefix(
        self,
        file_organizer: FileOrganizer,
        source_key: str,
        expected_prefix: str | None,
    ) -> None:
        """Validate destination folder resolution based on extension
        and case insensitivity.
        """
        assert file_organizer.get_target_prefix(source_key) == expected_prefix


class TestResolveDestinationKey:
    """Unit tests for the resolve_destination_key method."""

    @pytest.mark.parametrize(
        "source_key, target_prefix, expected_destination",
        [
            # Standard prefix with trailing slash
            ("inbox/fatura.pdf", "documents/", "documents/fatura.pdf"),
            # Prefix without trailing slash (should handle and prevent double slashes)
            ("inbox/fatura.pdf", "documents", "documents/fatura.pdf"),
            # Prefix with leading and trailing slash
            ("inbox/sub/fatura.pdf", "/documents/", "documents/fatura.pdf"),
            # Empty prefix (should place only the filename at the root)
            ("inbox/dados.csv", "", "dados.csv"),
            # Prefix containing only a slash
            ("inbox/dados.csv", "/", "dados.csv"),
        ],
    )
    def test_resolve_destination_key(
        self,
        file_organizer: FileOrganizer,
        source_key: str,
        target_prefix: str,
        expected_destination: str,
    ) -> None:
        """Validate S3 destination key construction handling prefix
        formatting variations.
        """
        result = file_organizer.resolve_destination_key(
            source_key=source_key,
            target_prefix=target_prefix,
        )
        assert result == expected_destination


class TestOrganizeBucket:
    """Unit tests for FileOrganizer.organize_bucket method covering
    batch execution flows.
    """

    def test_organize_bucket_happy_path(
        self,
        file_organizer: FileOrganizer,
        mock_s3_builder: MagicMock,
    ) -> None:
        """Verify that all recognized files in the bucket are
        correctly routed and moved.
        """
        mock_s3_builder.list_objects.return_value = [
            {"Key": "inbox/report.pdf"},
            {"Key": "inbox/data.csv"},
            {"Key": "inbox/photo.png"},
        ]

        stats = file_organizer.organize_bucket(
            bucket="my-bucket", source_prefix="inbox/"
        )

        # Assert execution statistics
        assert stats == {"moved": 3, "skipped": 0, "failed": 0}

        # Assert correct listing arguments
        mock_s3_builder.list_objects.assert_called_once_with(
            bucket="my-bucket", prefix="inbox/"
        )

        # Assert exact sequential S3 move invocations
        assert mock_s3_builder.move_object.call_count == 3
        mock_s3_builder.move_object.assert_has_calls(
            [
                call(
                    source_bucket="my-bucket",
                    source_key="inbox/report.pdf",
                    dest_bucket="my-bucket",
                    dest_key="documents/report.pdf",
                ),
                call(
                    source_bucket="my-bucket",
                    source_key="inbox/data.csv",
                    dest_bucket="my-bucket",
                    dest_key="data/data.csv",
                ),
                call(
                    source_bucket="my-bucket",
                    source_key="inbox/photo.png",
                    dest_bucket="my-bucket",
                    dest_key="images/photo.png",
                ),
            ],
            any_order=False,
        )

    def test_organize_bucket_unmapped_extension_with_default_fallback(
        self,
        file_organizer: FileOrganizer,
        mock_s3_builder: MagicMock,
    ) -> None:
        """Verify that files with unmapped extensions are routed to
        the default fallback folder.
        """
        mock_s3_builder.list_objects.return_value = [{"Key": "archive.xyz"}]

        stats = file_organizer.organize_bucket(
            bucket="my-bucket", uncategorized_prefix="others/"
        )

        assert stats == {"moved": 1, "skipped": 0, "failed": 0}
        mock_s3_builder.move_object.assert_called_once_with(
            source_bucket="my-bucket",
            source_key="archive.xyz",
            dest_bucket="my-bucket",
            dest_key="others/archive.xyz",
        )

    def test_organize_bucket_unmapped_extension_without_fallback(
        self,
        file_organizer: FileOrganizer,
        mock_s3_builder: MagicMock,
    ) -> None:
        """Verify that unmapped files are skipped when uncategorized_prefix
        is explicitly set to None.
        """
        mock_s3_builder.list_objects.return_value = [{"Key": "unknown.xyz"}]

        stats = file_organizer.organize_bucket(
            bucket="my-bucket", uncategorized_prefix=None
        )

        assert stats == {"moved": 0, "skipped": 1, "failed": 0}
        mock_s3_builder.move_object.assert_not_called()

    def test_organize_bucket_skips_already_organized_files(
        self,
        file_organizer: FileOrganizer,
        mock_s3_builder: MagicMock,
    ) -> None:
        """Verify that files already residing in their target paths are skipped
        without redundant moves.
        """
        mock_s3_builder.list_objects.return_value = [
            {"Key": "documents/report.pdf"},
            {"Key": "data/metrics.csv"},
        ]

        stats = file_organizer.organize_bucket(bucket="my-bucket")

        assert stats == {"moved": 0, "skipped": 2, "failed": 0}
        mock_s3_builder.move_object.assert_not_called()

    @pytest.mark.parametrize(
        "invalid_object",
        [
            {"Key": "inbox/"},  # Directory marker key
            {"Key": ""},  # Empty string key
            {},  # Missing Key entry
        ],
    )
    def test_organize_bucket_skips_invalid_keys_and_directories(
        self,
        file_organizer: FileOrganizer,
        mock_s3_builder: MagicMock,
        invalid_object: ObjectTypeDef,
    ) -> None:
        """Verify that directory markers and missing/empty keys are
        safely skipped.
        """
        mock_s3_builder.list_objects.return_value = [invalid_object]

        stats = file_organizer.organize_bucket(bucket="my-bucket")

        assert stats == {"moved": 0, "skipped": 1, "failed": 0}
        mock_s3_builder.move_object.assert_not_called()

    def test_organize_bucket_batch_resilience_on_error(
        self,
        file_organizer: FileOrganizer,
        mock_s3_builder: MagicMock,
    ) -> None:
        """Verify batch processing continues even when an individual move
        operation raises an error.
        """
        mock_s3_builder.list_objects.return_value = [
            {"Key": "doc1.pdf"},
            {"Key": "doc2.pdf"},
            {"Key": "doc3.pdf"},
        ]

        # Simulate success for file 1, exception for file 2, success for file 3
        mock_s3_builder.move_object.side_effect = [
            None,
            RuntimeError("S3 Connection Interrupted"),
            None,
        ]

        stats = file_organizer.organize_bucket(bucket="my-bucket")

        # Verify execution continues past errors and metrics accurately record state
        assert stats == {"moved": 2, "skipped": 0, "failed": 1}
        assert mock_s3_builder.move_object.call_count == 3

    def test_organize_bucket_empty_bucket(
        self,
        file_organizer: FileOrganizer,
        mock_s3_builder: MagicMock,
    ) -> None:
        """Verify graceful return when list_objects yields no objects."""
        mock_s3_builder.list_objects.return_value = []

        stats = file_organizer.organize_bucket(bucket="my-bucket")

        assert stats == {"moved": 0, "skipped": 0, "failed": 0}
        mock_s3_builder.move_object.assert_not_called()
