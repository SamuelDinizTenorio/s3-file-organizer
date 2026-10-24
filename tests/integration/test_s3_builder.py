"""Integration tests for S3Builder using LocalStack S3."""

import uuid
from pathlib import Path

import pytest
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError

from s3_file_organizer.s3_builder import S3Builder


class TestCreateBucketIntegration:
    """Group integration tests for S3Builder.create_bucket."""

    def test_create_bucket_success_integration(
        self, integration_s3_builder: S3Builder
    ) -> None:
        """Verify creating a new valid bucket succeeds and exists in S3."""
        bucket_name = f"my-bucket-{uuid.uuid4().hex[:8]}"

        result = integration_s3_builder.create_bucket(
            bucket_name=bucket_name,
        )

        assert result is True

        response = integration_s3_builder.s3_client.list_buckets()
        bucket_names = [bucket["Name"] for bucket in response.get("Buckets", [])]
        assert bucket_name in bucket_names

    def test_create_bucket_already_owned_by_you_integration(
        self, integration_s3_builder: S3Builder
    ) -> None:
        """Verify creating a bucket that already exists for the same
        owner returns success idempotently.
        """
        bucket_name = f"meu-bucket-de-teste-{uuid.uuid4().hex[:8]}"

        integration_s3_builder.create_bucket(bucket_name)
        result = integration_s3_builder.create_bucket(bucket_name)

        assert result is True

        response = integration_s3_builder.s3_client.list_buckets()
        bucket_names = [bucket["Name"] for bucket in response.get("Buckets", [])]
        assert bucket_name in bucket_names
        assert bucket_names.count(bucket_name) == 1

    @pytest.mark.parametrize(
        "invalid_name",
        [
            "My_Bucket",
            "my_bucket_underscore",
            "my..bucket",
            "ab",
            "-mybucket",
        ],
    )
    def test_create_bucket_invalid_names_integration(
        self, integration_s3_builder: S3Builder, invalid_name: str
    ) -> None:
        """Verify creating a bucket with invalid naming conventions
        raises ClientError.
        """
        with pytest.raises(ClientError) as exc_info:
            integration_s3_builder.create_bucket(bucket_name=invalid_name)

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
        integration_s3_builder: S3Builder,
        test_bucket: str,
        tmp_path: Path,
        key: str,
        content: str,
    ) -> None:
        """Verify uploading files with various key patterns
        (prefixes, spaces) succeeds.
        """
        file_path = tmp_path / "temp_file.txt"
        file_path.write_text(content)

        result = integration_s3_builder.upload_file(
            filename=str(file_path), bucket=test_bucket, key=key
        )

        assert result is True

        obj = integration_s3_builder.s3_client.head_object(Bucket=test_bucket, Key=key)
        assert obj["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_upload_file_bucket_not_found_integration(
        self, integration_s3_builder: S3Builder, tmp_path: Path
    ) -> None:
        """Verify uploading to a non-existent bucket raises S3UploadFailedError."""
        bucket_name = f"non-existent-bucket-{uuid.uuid4().hex[:8]}"
        key: str = "test_file.txt"
        file_path = tmp_path / "test_file.txt"
        file_path.write_text("Hello, LocalStack!")

        with pytest.raises(S3UploadFailedError) as exc_info:
            integration_s3_builder.upload_file(
                filename=str(file_path),
                bucket=bucket_name,
                key=key,
            )

        assert "NoSuchBucket" in str(exc_info.value)

    def test_upload_file_file_not_found_integration(
        self, integration_s3_builder: S3Builder, test_bucket: str
    ) -> None:
        """Verify uploading a non-existent local file raises FileNotFoundError."""
        file_path: str = "non_existent_local_file.txt"
        key: str = "test_file.txt"

        with pytest.raises(FileNotFoundError):
            integration_s3_builder.upload_file(
                filename=str(file_path), bucket=test_bucket, key=key
            )


class TestListObjectsIntegration:
    """Group integration tests for S3Builder.list_objects against LocalStack."""

    @pytest.mark.parametrize(
        "created_keys, search_prefix, expected_keys, use_default_prefix",
        [
            (
                ["file1.txt", "file2.pdf", "image.png"],
                None,
                ["file1.txt", "file2.pdf", "image.png"],
                True,
            ),
            (
                ["file1.txt", "file2.pdf", "image.png"],
                "",
                ["file1.txt", "file2.pdf", "image.png"],
                False,
            ),
            (
                ["documents/report1.pdf", "documents/report2.pdf", "images/photo.png"],
                "documents/",
                ["documents/report1.pdf", "documents/report2.pdf"],
                False,
            ),
            (
                ["logs_2026_01.txt", "logs_2026_02.txt", "notes.txt"],
                "logs_2026",
                ["logs_2026_01.txt", "logs_2026_02.txt"],
                False,
            ),
            (
                ["file1.txt", "file2.txt"],
                "non_existing_folder/",
                [],
                False,
            ),
            (
                [],
                None,
                [],
                True,
            ),
        ],
    )
    def test_list_objects_success_variations_integration(
        self,
        integration_s3_builder: S3Builder,
        test_bucket: str,
        created_keys: list[str],
        search_prefix: str | None,
        expected_keys: list[str],
        use_default_prefix: bool,
    ) -> None:
        """Verify listing objects in an S3 bucket with various prefix filters and
        None handling against LocalStack.
        """
        for key in created_keys:
            integration_s3_builder.s3_client.put_object(
                Bucket=test_bucket,
                Key=key,
                Body=b"Integration test content",
            )

        if use_default_prefix:
            results = integration_s3_builder.list_objects(bucket=test_bucket)
        else:
            results = integration_s3_builder.list_objects(
                bucket=test_bucket, prefix=search_prefix
            )

        retrieved_keys = [obj["Key"] for obj in results if obj.get("Key")]
        assert sorted(retrieved_keys) == sorted(expected_keys)

    def test_list_objects_bucket_not_found_integration(
        self, integration_s3_builder: S3Builder
    ) -> None:
        """Verify listing objects from a non-existent bucket raises ClientError
        with NoSuchBucket code against LocalStack.
        """
        non_existent_bucket = f"non-existent-bucket-{uuid.uuid4().hex[:8]}"

        with pytest.raises(ClientError) as exc_info:
            integration_s3_builder.list_objects(bucket=non_existent_bucket)

        assert exc_info.value.response["Error"]["Code"] == "NoSuchBucket"


class TestCopyObjectIntegration:
    """Group integration tests for S3Builder.copy_object against LocalStack."""

    def test_copy_object_success_integration(
        self, integration_s3_builder: S3Builder, test_bucket: str
    ) -> None:
        """Verify copying an object between keys in S3 duplicates
        the content successfully.
        """
        source_key = "uploads/document.pdf"
        dest_key = "archive/2026/document.pdf"
        content = b"PDF document payload"

        integration_s3_builder.s3_client.put_object(
            Bucket=test_bucket,
            Key=source_key,
            Body=content,
        )

        result = integration_s3_builder.copy_object(
            source_bucket=test_bucket,
            source_key=source_key,
            dest_bucket=test_bucket,
            dest_key=dest_key,
        )

        assert result is True

        obj = integration_s3_builder.s3_client.get_object(
            Bucket=test_bucket, Key=dest_key
        )
        assert obj["Body"].read() == content

    def test_copy_object_source_not_found_integration(
        self, integration_s3_builder: S3Builder, test_bucket: str
    ) -> None:
        """Verify copying a non-existent source object raises
        ClientError with NoSuchKey code.
        """
        with pytest.raises(ClientError) as exc_info:
            integration_s3_builder.copy_object(
                source_bucket=test_bucket,
                source_key="non_existent_file.txt",
                dest_bucket=test_bucket,
                dest_key="destination_file.txt",
            )

        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")


class TestDeleteObjectIntegration:
    """Group integration tests for S3Builder.delete_object against LocalStack."""

    def test_delete_object_success_integration(
        self, integration_s3_builder: S3Builder, test_bucket: str
    ) -> None:
        """Verify deleting an existing object removes it from the S3 bucket."""
        key = "documents/file_to_delete.pdf"
        integration_s3_builder.s3_client.put_object(
            Bucket=test_bucket,
            Key=key,
            Body=b"Content to be deleted",
        )

        result = integration_s3_builder.delete_object(bucket=test_bucket, key=key)

        assert result is True

        with pytest.raises(ClientError) as exc_info:
            integration_s3_builder.s3_client.get_object(
                Bucket=test_bucket,
                Key=key,
            )

        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")

    def test_delete_non_existent_object_idempotency_integration(
        self, integration_s3_builder: S3Builder, test_bucket: str
    ) -> None:
        """Verify deleting a non-existent object succeeds idempotently
        in S3 (204 No Content).
        """
        non_existent_key = "folder/missing_file.txt"

        result = integration_s3_builder.delete_object(
            bucket=test_bucket, key=non_existent_key
        )

        assert result is True

    def test_delete_object_bucket_not_found_integration(
        self, integration_s3_builder: S3Builder
    ) -> None:
        """Verify deleting an object from a non-existent bucket raises
        ClientError with NoSuchBucket code.
        """
        non_existent_bucket = f"non-existent-bucket-{uuid.uuid4().hex[:8]}"

        with pytest.raises(ClientError) as exc_info:
            integration_s3_builder.delete_object(
                bucket=non_existent_bucket, key="any_file.txt"
            )

        assert exc_info.value.response["Error"]["Code"] == "NoSuchBucket"


class TestMoveObjectIntegration:
    """Group integration tests for S3Builder.move_object against LocalStack."""

    @pytest.mark.parametrize(
        "source_prefix, source_key, dest_prefix, dest_key, file_content",
        [
            (
                "same-bucket",
                "inbox/document.pdf",
                "same-bucket",
                "processed/document.pdf",
                b"PDF document payload",
            ),
            (
                "source-bucket",
                "raw/data.csv",
                "dest-bucket",
                "archive/data.csv",
                b"id,name\n1,Alice",
            ),
            (
                "rename-bucket",
                "temp_report.txt",
                "rename-bucket",
                "final_report_2026.txt",
                b"Annual report summary content",
            ),
        ],
    )
    def test_move_object_success_variations_integration(
        self,
        integration_s3_builder: S3Builder,
        source_prefix: str,
        source_key: str,
        dest_prefix: str,
        dest_key: str,
        file_content: bytes,
    ) -> None:
        """Verify moving objects in S3 across various bucket and key scenarios."""
        source_bucket = f"{source_prefix}-{uuid.uuid4().hex[:8]}"
        dest_bucket = (
            source_bucket
            if source_prefix == dest_prefix
            else f"{dest_prefix}-{uuid.uuid4().hex[:8]}"
        )

        integration_s3_builder.create_bucket(source_bucket)
        if source_bucket != dest_bucket:
            integration_s3_builder.create_bucket(dest_bucket)

        integration_s3_builder.s3_client.put_object(
            Bucket=source_bucket,
            Key=source_key,
            Body=file_content,
        )

        result = integration_s3_builder.move_object(
            source_bucket=source_bucket,
            source_key=source_key,
            dest_bucket=dest_bucket,
            dest_key=dest_key,
        )

        assert result is True

        with pytest.raises(ClientError) as exc_info:
            integration_s3_builder.s3_client.get_object(
                Bucket=source_bucket, Key=source_key
            )
        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")

        dest_obj = integration_s3_builder.s3_client.get_object(
            Bucket=dest_bucket, Key=dest_key
        )
        assert dest_obj["Body"].read() == file_content

    def test_move_object_source_not_found_integration(
        self, integration_s3_builder: S3Builder, test_bucket: str
    ) -> None:
        """Verify moving a non-existent source object raises ClientError
        without creating destination file.
        """
        non_existent_key = "missing_file.txt"
        dest_key = "destination.txt"

        with pytest.raises(ClientError) as exc_info:
            integration_s3_builder.move_object(
                source_bucket=test_bucket,
                source_key=non_existent_key,
                dest_bucket=test_bucket,
                dest_key=dest_key,
            )

        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")

        with pytest.raises(ClientError) as exc_info_dest:
            integration_s3_builder.s3_client.get_object(
                Bucket=test_bucket, Key=dest_key
            )
        assert exc_info_dest.value.response["Error"]["Code"] in ("NoSuchKey", "404")
