from pathlib import Path
from typing import Generator

import pytest
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError

from s3_builder import S3Builder


@pytest.fixture
def s3_builder() -> Generator[S3Builder, None, None]:
    # Setup
    builder_instance = S3Builder(
        endpoint_url="http://localhost:4566",
        access_key_id="test",
        secret_access_key="test",
        region="us-east-1",
    )

    yield builder_instance

    response = builder_instance.s3.list_buckets()

    # Teardown
    for bucket in response.get("Buckets", []):
        s3 = builder_instance.s3
        objects = s3.list_objects_v2(Bucket=bucket["Name"])

        for obj in objects.get("Contents", []):
            s3.delete_object(Bucket=bucket["Name"], Key=obj["Key"])

        s3.delete_bucket(Bucket=bucket["Name"])


class TestCreateBucketIntegration:
    """Group integration tests for S3Builder.create_bucket."""

    def test_create_bucket_success_integration(self, s3_builder: S3Builder) -> None:
        # Arrange
        bucket_name = "my-bucket"

        # Act
        result = s3_builder.create_bucket(bucket_name=bucket_name)

        # Assert
        assert result is True

        response = s3_builder.s3.list_buckets()
        bucket_names = [bucket["Name"] for bucket in response.get("Buckets", [])]
        assert bucket_name in bucket_names

    def test_create_bucket_already_owned_by_you_integration(
        self, s3_builder: S3Builder
    ) -> None:
        # Arrange
        bucket_name = "meu-bucket-de-teste"

        # Act
        s3_builder.create_bucket(bucket_name)
        result = s3_builder.create_bucket(bucket_name)

        # Assert
        assert result is True

        response = s3_builder.s3.list_buckets()
        bucket_names = [bucket["Name"] for bucket in response.get("Buckets", [])]
        assert bucket_name in bucket_names
        assert bucket_names.count(bucket_name) == 1

    @pytest.mark.parametrize(
        "invalid_name",
        [
            "My_Bucket",  # Contains uppercase letters (must be lowercase)
            "my_bucket_underscore",  # Contains underscores
            "my..bucket",  # Contains consecutive periods
            "ab",  # Less than 3 characters long
            "-mybucket",  # Starts with a hyphen
        ],
    )
    def test_create_bucket_invalid_names_integration(
        self, s3_builder: S3Builder, invalid_name: str
    ) -> None:
        # Act & Assert
        with pytest.raises(ClientError) as exc_info:
            s3_builder.create_bucket(bucket_name=invalid_name)

        assert exc_info.value.response["Error"]["Code"] in (
            "InvalidBucketName",
            "InvalidBucketNameException",
        )


class TestUploadFileIntegration:
    """Group integration tests for S3Builder.upload_file."""

    @pytest.mark.parametrize(
        "key, content",
        [
            ("test_file.txt", "Hello, LocalStack!"),
            ("documents/2026/report.pdf", "PDF Content Stream"),
            ("folder/subfolder/file with spaces.txt", "Content with spaces"),
        ],
    )
    def test_upload_file_success_variations_integration(
        self,
        s3_builder: S3Builder,
        tmp_path: Path,
        key: str,
        content: str,
    ) -> None:
        # Arrange
        bucket_name: str = "upload-bucket-test"
        s3_builder.create_bucket(bucket_name)

        file_path = tmp_path / "temp_file.txt"
        file_path.write_text(content)

        # Act
        result = s3_builder.upload_file(
            filename=str(file_path), bucket=bucket_name, key=key
        )

        # Assert
        assert result is True

        obj = s3_builder.s3.head_object(Bucket=bucket_name, Key=key)
        assert obj["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_upload_file_bucket_not_found_integration(
        self, s3_builder: S3Builder, tmp_path: Path
    ) -> None:
        # Arrange
        bucket_name: str = "non-existent-bucket"
        key: str = "test_file.txt"
        file_path = tmp_path / "test_file.txt"
        file_path.write_text("Hello, LocalStack!")

        # Act & Assert
        with pytest.raises(S3UploadFailedError) as exc_info:
            s3_builder.upload_file(filename=str(file_path), bucket=bucket_name, key=key)

        assert "NoSuchBucket" in str(exc_info.value)

    def test_upload_file_file_not_found_integration(
        self, s3_builder: S3Builder
    ) -> None:
        # Arrange
        file_path: str = "non_existent_local_file.txt"
        bucket_name: str = "upload-bucket-test"
        key: str = "test_file.txt"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            s3_builder.upload_file(filename=str(file_path), bucket=bucket_name, key=key)


class TestListObjectsIntegration:
    """Group integration tests for S3Builder.list_objects against LocalStack."""

    @pytest.mark.parametrize(
        "created_keys, search_prefix, expected_keys",
        [
            # Case 1: List all objects when no prefix is provided
            (
                ["file1.txt", "file2.pdf", "image.png"],
                "",
                ["file1.txt", "file2.pdf", "image.png"],
            ),
            # Case 2: Filter objects by folder-like prefix
            (
                ["documents/report1.pdf", "documents/report2.pdf", "images/photo.png"],
                "documents/",
                ["documents/report1.pdf", "documents/report2.pdf"],
            ),
            # Case 3: Filter by partial filename prefix
            (
                ["logs_2026_01.txt", "logs_2026_02.txt", "notes.txt"],
                "logs_2026",
                ["logs_2026_01.txt", "logs_2026_02.txt"],
            ),
            # Case 4: Search with a prefix that matches no objects
            (
                ["file1.txt", "file2.txt"],
                "non_existing_folder/",
                [],
            ),
            # Case 5: Empty bucket listing
            (
                [],
                "",
                [],
            ),
        ],
    )
    def test_list_objects_success_variations_integration(
        self,
        s3_builder: S3Builder,
        created_keys: list[str],
        search_prefix: str,
        expected_keys: list[str],
    ) -> None:
        """
        Test listing objects in a real S3 bucket with different prefixes
        and file structures.
        """
        # Arrange
        bucket_name = "list-objects-integration-bucket"
        s3_builder.create_bucket(bucket_name)

        # Upload dummy objects to LocalStack
        for key in created_keys:
            s3_builder.s3.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=b"Integration test content",
            )

        # Act
        results = s3_builder.list_objects(bucket=bucket_name, prefix=search_prefix)

        # Assert
        retrieved_keys = [obj["Key"] for obj in results]
        assert sorted(retrieved_keys) == sorted(expected_keys)

    def test_list_objects_bucket_not_found_integration(
        self, s3_builder: S3Builder
    ) -> None:
        """Test listing objects from a non-existent bucket raises ClientError."""
        # Arrange
        non_existent_bucket = "non-existent-bucket-for-list"

        # Act & Assert
        with pytest.raises(ClientError) as exc_info:
            s3_builder.list_objects(bucket=non_existent_bucket)

        assert exc_info.value.response["Error"]["Code"] == "NoSuchBucket"


class TestCopyObjectIntegration:
    """Group integration tests for S3Builder.copy_object against LocalStack."""

    def test_copy_object_success_integration(self, s3_builder: S3Builder) -> None:
        """Test copying an object between different keys in LocalStack."""
        # Arrange
        bucket_name = "copy-integration-bucket"
        s3_builder.create_bucket(bucket_name)

        source_key = "uploads/document.pdf"
        dest_key = "archive/2026/document.pdf"
        content = b"PDF document payload"

        # Put source object directly in S3
        s3_builder.s3.put_object(
            Bucket=bucket_name,
            Key=source_key,
            Body=content,
        )

        # Act
        result = s3_builder.copy_object(
            source_bucket=bucket_name,
            source_key=source_key,
            dest_bucket=bucket_name,
            dest_key=dest_key,
        )

        # Assert
        assert result is True

        # Verify that the copied object exists and contains the expected content
        obj = s3_builder.s3.get_object(Bucket=bucket_name, Key=dest_key)
        assert obj["Body"].read() == content

    def test_copy_object_source_not_found_integration(
        self, s3_builder: S3Builder
    ) -> None:
        """Test copying a non-existent object raises ClientError."""
        # Arrange
        bucket_name = "copy-error-bucket"
        s3_builder.create_bucket(bucket_name)

        # Act & Assert
        with pytest.raises(ClientError) as exc_info:
            s3_builder.copy_object(
                source_bucket=bucket_name,
                source_key="non_existent_file.txt",
                dest_bucket=bucket_name,
                dest_key="destination_file.txt",
            )

        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")


class TestDeleteObjectIntegration:
    """Group integration tests for S3Builder.delete_object against LocalStack."""

    def test_delete_object_success_integration(self, s3_builder: S3Builder) -> None:
        """Test successfully deleting an existing object from an S3 bucket."""
        # Arrange
        bucket_name = "delete-integration-bucket"
        s3_builder.create_bucket(bucket_name)

        key = "documents/file_to_delete.pdf"
        s3_builder.s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=b"Content to be deleted",
        )

        # Act
        result = s3_builder.delete_object(bucket=bucket_name, key=key)

        # Assert
        assert result is True

        # Verify the object no longer exists in S3
        with pytest.raises(ClientError) as exc_info:
            s3_builder.s3.get_object(Bucket=bucket_name, Key=key)

        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")

    def test_delete_non_existent_object_idempotency_integration(
        self, s3_builder: S3Builder
    ) -> None:
        """Test deleting a non-existent object succeeds due to S3 idempotency
        (204 No Content).
        """
        # Arrange
        bucket_name = "delete-idempotent-bucket"
        s3_builder.create_bucket(bucket_name)

        non_existent_key = "folder/missing_file.txt"

        # Act
        result = s3_builder.delete_object(bucket=bucket_name, key=non_existent_key)

        # Assert
        assert result is True

    def test_delete_object_bucket_not_found_integration(
        self, s3_builder: S3Builder
    ) -> None:
        """Test deleting an object from a non-existent bucket raises ClientError."""
        # Arrange
        non_existent_bucket = "non-existent-bucket-for-delete"

        # Act & Assert
        with pytest.raises(ClientError) as exc_info:
            s3_builder.delete_object(bucket=non_existent_bucket, key="any_file.txt")

        assert exc_info.value.response["Error"]["Code"] == "NoSuchBucket"


class TestMoveObjectIntegration:
    """Group integration tests for S3Builder.move_object against LocalStack."""

    @pytest.mark.parametrize(
        "source_bucket, source_key, dest_bucket, dest_key, file_content",
        [
            # Case 1: Move within the same bucket (organizing from inbox to processed)
            (
                "same-bucket-move",
                "inbox/document.pdf",
                "same-bucket-move",
                "processed/document.pdf",
                b"PDF document payload",
            ),
            # Case 2: Move across different buckets (cross-bucket transfer)
            (
                "source-bucket-move",
                "raw/data.csv",
                "dest-bucket-move",
                "archive/data.csv",
                b"id,name\n1,Alice",
            ),
            # Case 3: Move and rename file in a single operation
            (
                "rename-bucket-move",
                "temp_report.txt",
                "rename-bucket-move",
                "final_report_2026.txt",
                b"Annual report summary content",
            ),
        ],
    )
    def test_move_object_success_variations_integration(
        self,
        s3_builder: S3Builder,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
        file_content: bytes,
    ) -> None:
        """Test moving objects in LocalStack across various bucket and key scenarios."""
        # Arrange
        s3_builder.create_bucket(source_bucket)
        if source_bucket != dest_bucket:
            s3_builder.create_bucket(dest_bucket)

        s3_builder.s3.put_object(
            Bucket=source_bucket,
            Key=source_key,
            Body=file_content,
        )

        # Act
        result = s3_builder.move_object(
            source_bucket=source_bucket,
            source_key=source_key,
            dest_bucket=dest_bucket,
            dest_key=dest_key,
        )

        # Assert
        assert result is True

        # 1. Verify source object no longer exists
        with pytest.raises(ClientError) as exc_info:
            s3_builder.s3.get_object(Bucket=source_bucket, Key=source_key)
        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")

        # 2. Verify destination object exists and matches original content
        dest_obj = s3_builder.s3.get_object(Bucket=dest_bucket, Key=dest_key)
        assert dest_obj["Body"].read() == file_content

    def test_move_object_source_not_found_integration(
        self, s3_builder: S3Builder
    ) -> None:
        """Test moving a non-existent source object raises ClientError without creating
        destination file.
        """
        # Arrange
        bucket_name = "move-error-bucket"
        s3_builder.create_bucket(bucket_name)

        non_existent_key = "missing_file.txt"
        dest_key = "destination.txt"

        # Act & Assert
        with pytest.raises(ClientError) as exc_info:
            s3_builder.move_object(
                source_bucket=bucket_name,
                source_key=non_existent_key,
                dest_bucket=bucket_name,
                dest_key=dest_key,
            )

        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")

        # Verify destination key was not created (short-circuit verification)
        with pytest.raises(ClientError) as exc_info_dest:
            s3_builder.s3.get_object(Bucket=bucket_name, Key=dest_key)
        assert exc_info_dest.value.response["Error"]["Code"] in ("NoSuchKey", "404")
