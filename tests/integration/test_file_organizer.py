from file_organizer import FileOrganizer
from s3_builder import S3Builder


class TestFileOrganizerHelpersIntegration:
    """Integration tests for FileOrganizer helper methods using a real
    S3Builder instance.
    """

    def test_get_target_prefix_integration(
        self, integration_file_organizer: FileOrganizer
    ) -> None:
        """Verify get_target_prefix logic when integrated with a live
        S3Builder instance.
        """
        # Standard extension routing
        assert (
            integration_file_organizer.get_target_prefix("incoming/report.pdf")
            == "documents/"
        )
        assert (
            integration_file_organizer.get_target_prefix("raw_data/metrics.csv")
            == "data/"
        )

        # Case-insensitivity verification
        assert (
            integration_file_organizer.get_target_prefix("uploads/PHOTO.JPEG")
            == "images/"
        )

        # Unmapped extension and extensionless keys
        assert integration_file_organizer.get_target_prefix("binaries/app.exe") is None
        assert integration_file_organizer.get_target_prefix("DOCKERFILE") is None

    def test_get_target_prefix_with_custom_rules_integration(
        self, integration_s3_builder: S3Builder
    ) -> None:
        """Verify get_target_prefix respects custom mapping rules in
        integrated setup.
        """
        custom_rules = {".log": "logs/", ".py": "scripts/"}
        organizer = FileOrganizer(
            s3_builder=integration_s3_builder,
            extension_rules=custom_rules,
        )

        assert organizer.get_target_prefix("app.log") == "logs/"
        assert organizer.get_target_prefix("main.py") == "scripts/"
        assert organizer.get_target_prefix("report.pdf") is None

    def test_resolve_destination_key_integration(
        self, integration_file_organizer: FileOrganizer
    ) -> None:
        """Verify resolve_destination_key path formatting with a real
        S3Builder instance.
        """

        # Standard destination construction
        dest = integration_file_organizer.resolve_destination_key(
            source_key="incoming/subfolder/invoice.pdf",
            target_prefix="documents/",
        )
        assert dest == "documents/invoice.pdf"

        # Redundant slash sanitization
        dest_clean = integration_file_organizer.resolve_destination_key(
            source_key="staging/data.json",
            target_prefix="//data///",
        )
        assert dest_clean == "data/data.json"

        # Empty/root prefix handling
        root_dest = integration_file_organizer.resolve_destination_key(
            source_key="staging/file.txt",
            target_prefix="/",
        )
        assert root_dest == "file.txt"


class TestOrganizeBucketIntegration:
    """Integration tests for FileOrganizer.organize_bucket executing
    real S3 operations.
    """

    def test_organize_bucket_happy_path_integration(
        self,
        integration_s3_builder: S3Builder,
        integration_file_organizer: FileOrganizer,
        test_bucket: str,
    ) -> None:
        """Verify end-to-end file organization correctly relocates objects
        and removes sources.
        """
        client = integration_s3_builder.s3_client

        # 1. Seed bucket with sample files under inbox/ prefix
        client.put_object(
            Bucket=test_bucket,
            Key="inbox/report.pdf",
            Body=b"PDF content",
        )
        client.put_object(
            Bucket=test_bucket,
            Key="inbox/metrics.csv",
            Body=b"CSV content",
        )
        client.put_object(
            Bucket=test_bucket,
            Key="inbox/photo.png",
            Body=b"PNG content",
        )

        # 2. Execute organization
        stats = integration_file_organizer.organize_bucket(
            bucket=test_bucket, source_prefix="inbox/"
        )

        # 3. Assert execution metrics
        assert stats == {"moved": 3, "skipped": 0, "failed": 0}

        # 4. Assert bucket state
        objects = integration_s3_builder.list_objects(bucket=test_bucket)
        keys = [obj["Key"] for obj in objects if obj.get("Key")]

        # Target destinations must exist
        assert "documents/report.pdf" in keys
        assert "data/metrics.csv" in keys
        assert "images/photo.png" in keys

        # Source keys must no longer exist
        assert "inbox/report.pdf" not in keys
        assert "inbox/metrics.csv" not in keys
        assert "inbox/photo.png" not in keys

    def test_organize_bucket_fallback_integration(
        self,
        integration_s3_builder: S3Builder,
        integration_file_organizer: FileOrganizer,
        test_bucket: str,
    ) -> None:
        """Verify unmapped file extensions are routed to the fallback
        folder in S3.
        """
        client = integration_s3_builder.s3_client
        client.put_object(
            Bucket=test_bucket,
            Key="inbox/app.exe",
            Body=b"binary data",
        )

        stats = integration_file_organizer.organize_bucket(
            bucket=test_bucket, uncategorized_prefix="others/"
        )

        assert stats == {"moved": 1, "skipped": 0, "failed": 0}

        objects = integration_s3_builder.list_objects(bucket=test_bucket)
        keys = [obj["Key"] for obj in objects if obj.get("Key")]

        assert "others/app.exe" in keys
        assert "inbox/app.exe" not in keys

    def test_organize_bucket_disabled_fallback_integration(
        self,
        integration_s3_builder: S3Builder,
        integration_file_organizer: FileOrganizer,
        test_bucket: str,
    ) -> None:
        """Verify unmapped files remain untouched when
        uncategorized_prefix is set to None.
        """
        client = integration_s3_builder.s3_client
        client.put_object(
            Bucket=test_bucket,
            Key="inbox/unknown.xyz",
            Body=b"raw data",
        )

        stats = integration_file_organizer.organize_bucket(
            bucket=test_bucket, uncategorized_prefix=None
        )

        assert stats == {"moved": 0, "skipped": 1, "failed": 0}

        objects = integration_s3_builder.list_objects(bucket=test_bucket)
        keys = [obj["Key"] for obj in objects if obj.get("Key")]

        # Object should remain in its original location
        assert "inbox/unknown.xyz" in keys

    def test_organize_bucket_skips_already_organized_integration(
        self,
        integration_s3_builder: S3Builder,
        integration_file_organizer: FileOrganizer,
        test_bucket: str,
    ) -> None:
        """Verify objects already present in their target prefix are skipped
        without redundant S3 moves.
        """
        client = integration_s3_builder.s3_client
        client.put_object(
            Bucket=test_bucket,
            Key="documents/existing_doc.pdf",
            Body=b"PDF data",
        )

        stats = integration_file_organizer.organize_bucket(bucket=test_bucket)

        assert stats == {"moved": 0, "skipped": 1, "failed": 0}

        objects = integration_s3_builder.list_objects(bucket=test_bucket)
        keys = [obj["Key"] for obj in objects if obj.get("Key")]

        assert "documents/existing_doc.pdf" in keys

    def test_organize_bucket_filtered_source_prefix_integration(
        self,
        integration_s3_builder: S3Builder,
        integration_file_organizer: FileOrganizer,
        test_bucket: str,
    ) -> None:
        """Verify organizing with source_prefix restricts scanning exclusively
        to that prefix.
        """
        client = integration_s3_builder.s3_client
        client.put_object(Bucket=test_bucket, Key="inbox/file1.pdf", Body=b"data 1")
        client.put_object(Bucket=test_bucket, Key="archive/file2.pdf", Body=b"data 2")

        stats = integration_file_organizer.organize_bucket(
            bucket=test_bucket, source_prefix="inbox/"
        )

        assert stats == {"moved": 1, "skipped": 0, "failed": 0}

        objects = integration_s3_builder.list_objects(bucket=test_bucket)
        keys = [obj["Key"] for obj in objects if obj.get("Key")]

        # inbox/file1.pdf was organized into documents/
        assert "documents/file1.pdf" in keys
        assert "inbox/file1.pdf" not in keys

        # archive/file2.pdf was ignored because it wasn't under inbox/
        assert "archive/file2.pdf" in keys
