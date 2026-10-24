"""Unit tests for the S3Builder class."""

import logging
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError
from mypy_boto3_s3.type_defs import ObjectTypeDef

from s3_file_organizer.s3_builder import S3Builder


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
                    "aws_access_key_id": "test123",
                    "aws_secret_access_key": "test123",
                    "region_name": "us-east-2",
                },
                {
                    "service_name": "s3",
                    "endpoint_url": "https://localhost:4566",
                    "aws_access_key_id": "test123",
                    "aws_secret_access_key": "test123",
                    "region_name": "us-east-2",
                },
            ),
            (
                {
                    "endpoint_url": "http://s3.local:4566",
                    "region_name": "sa-east-1",
                },
                {
                    "service_name": "s3",
                    "endpoint_url": "http://s3.local:4566",
                    "aws_access_key_id": "test",
                    "aws_secret_access_key": "test",
                    "region_name": "sa-east-1",
                },
            ),
        ],
    )
    def test_s3_builder_init_success(
        self,
        mock_boto_client: MagicMock,
        kwargs: dict[str, Any],
        expected_args: dict[str, Any],
    ) -> None:
        S3Builder(**kwargs)
        mock_boto_client.assert_called_once_with(**expected_args)

    @pytest.mark.parametrize(
        "exception_instance, match_pattern, expected_log_msg",
        [
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "AccessDenied",
                            "Message": "Access Denied",
                        }
                    },
                    "CreateClient",
                ),
                "Access Denied",
                "Failed in create S3 client: An error occurred (AccessDenied) "
                "when calling the CreateClient operation: Access Denied",
            ),
            (
                Exception("Generic error"),
                "Generic error",
                "Unexpected error while initializing S3Builder: Generic error",
            ),
        ],
    )
    def test_s3_builder_init_errors(
        self,
        mock_boto_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        exception_instance: Exception,
        match_pattern: str,
        expected_log_msg: str,
    ) -> None:
        mock_boto_client.side_effect = exception_instance

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            logging.ERROR,
            expected_log_msg,
        )

        with pytest.raises(type(exception_instance), match=match_pattern):
            S3Builder()

        mock_boto_client.assert_called_once()
        assert expected_log in caplog.record_tuples


class TestCreateBucket:
    """Group tests for S3Builder.create_bucket."""

    @pytest.mark.parametrize(
        "side_effect, expected_log_level, expected_log_msg",
        [
            (
                None,
                logging.INFO,
                "Successfully created bucket my-bucket",
            ),
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "BucketAlreadyOwnedByYou",
                            "Message": "Bucket Already Owned By You",
                        }
                    },
                    "CreateBucket",
                ),
                logging.WARNING,
                "Bucket my-bucket is already owned by you: "
                "An error occurred (BucketAlreadyOwnedByYou) "
                "when calling the CreateBucket operation: "
                "Bucket Already Owned By You",
            ),
        ],
    )
    def test_create_bucket_success_and_warnings(
        self,
        s3_builder: S3Builder,
        mock_s3_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        side_effect: Exception | None,
        expected_log_level: int,
        expected_log_msg: str,
    ) -> None:
        caplog.set_level(logging.INFO)
        bucket_name: str = "my-bucket"
        mock_s3_client.create_bucket.side_effect = side_effect

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            expected_log_level,
            expected_log_msg,
        )

        result = s3_builder.create_bucket(bucket_name=bucket_name)

        mock_s3_client.create_bucket.assert_called_once_with(Bucket=bucket_name)
        assert result is True
        assert expected_log in caplog.record_tuples

    @pytest.mark.parametrize(
        "exception_instance, match_pattern, expected_log_msg",
        [
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "AccessDenied",
                            "Message": "Access Denied",
                        }
                    },
                    "CreateBucket",
                ),
                "Access Denied",
                "Failed to create bucket my-bucket due to S3 API error: "
                "An error occurred (AccessDenied) "
                "when calling the CreateBucket operation: Access Denied",
            ),
            (
                Exception("Unexpected error"),
                "Unexpected error",
                "An unexpected error occurred while creating bucket my-bucket: "
                "Unexpected error",
            ),
        ],
    )
    def test_create_bucket_errors(
        self,
        s3_builder: S3Builder,
        mock_s3_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        exception_instance: Exception,
        match_pattern: str,
        expected_log_msg: str,
    ) -> None:
        bucket_name: str = "my-bucket"
        mock_s3_client.create_bucket.side_effect = exception_instance

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            logging.ERROR,
            expected_log_msg,
        )

        with pytest.raises(type(exception_instance), match=match_pattern):
            s3_builder.create_bucket(bucket_name=bucket_name)

        mock_s3_client.create_bucket.assert_called_once_with(Bucket=bucket_name)
        assert expected_log in caplog.record_tuples


class TestUploadFile:
    """Group tests for S3Builder.upload_file."""

    @pytest.mark.parametrize(
        "filename, bucket, key",
        [
            ("my-file.txt", "my-bucket", "my-key.txt"),
            ("path/to/local/file.pdf", "my-bucket", "documents/file.pdf"),
            ("image.png", "other-bucket", "2026/09/image.png"),
        ],
    )
    def test_upload_file_success_variations(
        self,
        s3_builder: S3Builder,
        mock_s3_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        filename: str,
        bucket: str,
        key: str,
    ) -> None:
        caplog.set_level(logging.INFO)

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            logging.INFO,
            f"Successfully uploaded {filename} to {bucket}/{key}",
        )

        result = s3_builder.upload_file(filename=filename, bucket=bucket, key=key)

        mock_s3_client.upload_file.assert_called_once_with(
            Filename=filename, Bucket=bucket, Key=key
        )
        assert result is True
        assert expected_log in caplog.record_tuples

    @pytest.mark.parametrize(
        "exception_instance, match_pattern, expected_log_msg",
        [
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "AccessDenied",
                            "Message": "Access Denied",
                        }
                    },
                    "UploadFile",
                ),
                "Access Denied",
                "Failed to upload the file my-file to my-bucket/my-key due to "
                "S3 API error: An error occurred (AccessDenied) "
                "when calling the UploadFile operation: Access Denied",
            ),
            (
                S3UploadFailedError("Failed to upload file"),
                "Failed to upload file",
                "Failed to upload the file my-file to my-bucket/my-key due to "
                "S3 API error: Failed to upload file",
            ),
            (
                FileNotFoundError(2, "No such file or directory", "my-file"),
                "my-file",
                "Local file not found: my-file",
            ),
            (
                Exception("Unexpected upload error"),
                "Unexpected upload error",
                "An unexpected error occurred while uploading file "
                "my-file to my-bucket/my-key: Unexpected upload error",
            ),
        ],
    )
    def test_upload_file_errors(
        self,
        s3_builder: S3Builder,
        mock_s3_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        exception_instance: Exception,
        match_pattern: str,
        expected_log_msg: str,
    ) -> None:
        filename: str = "my-file"
        bucket: str = "my-bucket"
        key: str = "my-key"

        mock_s3_client.upload_file.side_effect = exception_instance

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            logging.ERROR,
            expected_log_msg,
        )

        with pytest.raises(type(exception_instance), match=match_pattern):
            s3_builder.upload_file(filename=filename, bucket=bucket, key=key)

        mock_s3_client.upload_file.assert_called_once_with(
            Filename=filename, Bucket=bucket, Key=key
        )
        assert expected_log in caplog.record_tuples


class TestListObjects:
    """Group unit tests for S3Builder.list_objects."""

    @pytest.mark.parametrize(
        "bucket, prefix, paginator_pages, expected_keys, expected_log_msg",
        [
            (
                "my-bucket",
                None,
                [
                    {
                        "Contents": [
                            cast(ObjectTypeDef, {"Key": "file1.txt"}),
                            cast(ObjectTypeDef, {"Key": "file2.pdf"}),
                        ]
                    },
                    {
                        "Contents": [
                            cast(ObjectTypeDef, {"Key": "file3.png"}),
                        ]
                    },
                ],
                ["file1.txt", "file2.pdf", "file3.png"],
                "Successfully listed 3 object(s) in bucket 'my-bucket' "
                "(without prefix)",
            ),
            (
                "my-bucket",
                "documents/",
                [
                    {
                        "Contents": [
                            cast(ObjectTypeDef, {"Key": "documents/report.pdf"}),
                        ]
                    },
                ],
                ["documents/report.pdf"],
                "Successfully listed 1 object(s) in bucket 'my-bucket' "
                "with prefix 'documents/'",
            ),
            (
                "empty-bucket",
                None,
                [{}],
                [],
                "Successfully listed 0 object(s) in bucket 'empty-bucket' "
                "(without prefix)",
            ),
        ],
    )
    def test_list_objects_success(
        self,
        s3_builder: S3Builder,
        mock_s3_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        bucket: str,
        prefix: str | None,
        paginator_pages: object,
        expected_keys: list[str],
        expected_log_msg: str,
    ) -> None:
        """Test successful execution of list_objects across various scenarios."""
        caplog.set_level(logging.INFO)
        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = paginator_pages

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            logging.INFO,
            expected_log_msg,
        )

        kwargs = {"bucket": bucket}
        if prefix is not None:
            kwargs["prefix"] = prefix

        result = s3_builder.list_objects(**kwargs)

        mock_s3_client.get_paginator.assert_called_once_with("list_objects_v2")

        expected_paginate_kwargs = {"Bucket": bucket}
        if prefix is not None:
            expected_paginate_kwargs["Prefix"] = prefix

        mock_paginator.paginate.assert_called_once_with(**expected_paginate_kwargs)
        assert [obj["Key"] for obj in result] == expected_keys
        assert expected_log in caplog.record_tuples

    @pytest.mark.parametrize(
        "exception_instance, match_pattern, expected_log_msg",
        [
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "NoSuchBucket",
                            "Message": "The specified bucket does not exist",
                        }
                    },
                    "ListObjectsV2",
                ),
                "The specified bucket does not exist",
                "Failed to list objects in bucket my-bucket due to S3 API error: "
                "An error occurred (NoSuchBucket) when calling the ListObjectsV2 "
                "operation: The specified bucket does not exist",
            ),
            (
                Exception("Unexpected paginator failure"),
                "Unexpected paginator failure",
                "An unexpected error occurred while listing objects "
                "in bucket my-bucket: Unexpected paginator failure",
            ),
        ],
    )
    def test_list_objects_errors(
        self,
        s3_builder: S3Builder,
        mock_s3_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        exception_instance: Exception,
        match_pattern: str,
        expected_log_msg: str,
    ) -> None:
        """Test exception handling and logging behavior for list_objects failures."""
        bucket: str = "my-bucket"
        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = exception_instance

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            logging.ERROR,
            expected_log_msg,
        )

        with pytest.raises(type(exception_instance), match=match_pattern):
            s3_builder.list_objects(bucket=bucket)

        mock_s3_client.get_paginator.assert_called_once_with("list_objects_v2")
        mock_paginator.paginate.assert_called_once_with(Bucket=bucket)
        assert expected_log in caplog.record_tuples


class TestCopyObject:
    """Group unit tests for S3Builder.copy_object."""

    @pytest.mark.parametrize(
        "source_bucket, source_key, dest_bucket, dest_key",
        [
            ("my-bucket", "file.txt", "my-bucket", "documents/file.txt"),
            ("source-bucket", "raw/data.csv", "target-bucket", "processed/data.csv"),
        ],
    )
    def test_copy_object_success(
        self,
        s3_builder: S3Builder,
        mock_s3_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> None:
        """Test successful execution of copy_object across various scenarios."""
        caplog.set_level(logging.INFO)

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            logging.INFO,
            f"Successfully copied {source_bucket}/{source_key} to "
            f"{dest_bucket}/{dest_key}",
        )

        result = s3_builder.copy_object(
            source_bucket=source_bucket,
            source_key=source_key,
            dest_bucket=dest_bucket,
            dest_key=dest_key,
        )

        mock_s3_client.copy_object.assert_called_once_with(
            CopySource={"Bucket": source_bucket, "Key": source_key},
            Bucket=dest_bucket,
            Key=dest_key,
        )
        assert result is True
        assert expected_log in caplog.record_tuples

    @pytest.mark.parametrize(
        "exception_instance, match_pattern, expected_log_msg",
        [
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "NoSuchKey",
                            "Message": "The specified key does not exist",
                        }
                    },
                    "CopyObject",
                ),
                "The specified key does not exist",
                "Failed to copy object source-bkt/src-key to dest-bkt/dst-key "
                "due to S3 API error: An error occurred (NoSuchKey) when calling "
                "the CopyObject operation: The specified key does not exist",
            ),
            (
                Exception("Unexpected S3 error"),
                "Unexpected S3 error",
                "An unexpected error occurred while copying "
                "source-bkt/src-key to dest-bkt/dst-key: Unexpected S3 error",
            ),
        ],
    )
    def test_copy_object_errors(
        self,
        s3_builder: S3Builder,
        mock_s3_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        exception_instance: Exception,
        match_pattern: str,
        expected_log_msg: str,
    ) -> None:
        """Test exception handling and logging behavior for copy_object failures."""
        source_bucket = "source-bkt"
        source_key = "src-key"
        dest_bucket = "dest-bkt"
        dest_key = "dst-key"

        mock_s3_client.copy_object.side_effect = exception_instance

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            logging.ERROR,
            expected_log_msg,
        )

        with pytest.raises(type(exception_instance), match=match_pattern):
            s3_builder.copy_object(
                source_bucket=source_bucket,
                source_key=source_key,
                dest_bucket=dest_bucket,
                dest_key=dest_key,
            )

        mock_s3_client.copy_object.assert_called_once_with(
            CopySource={"Bucket": source_bucket, "Key": source_key},
            Bucket=dest_bucket,
            Key=dest_key,
        )
        assert expected_log in caplog.record_tuples


class TestDeleteObject:
    """Group unit tests for S3Builder.delete_object."""

    @pytest.mark.parametrize(
        "bucket, key",
        [
            ("my-bucket", "file.txt"),
            ("my-bucket", "documents/report.pdf"),
            ("archive-bucket", "2026/logs/app.log"),
        ],
    )
    def test_delete_object_success(
        self,
        s3_builder: S3Builder,
        mock_s3_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        bucket: str,
        key: str,
    ) -> None:
        """Test successful execution of delete_object across various bucket
        and key variations.
        """
        caplog.set_level(logging.INFO)

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            logging.INFO,
            f"The object {bucket}/{key} was successfully deleted",
        )

        result = s3_builder.delete_object(bucket=bucket, key=key)

        mock_s3_client.delete_object.assert_called_once_with(Bucket=bucket, Key=key)
        assert result is True
        assert expected_log in caplog.record_tuples

    @pytest.mark.parametrize(
        "exception_instance, match_pattern, expected_log_msg",
        [
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "AccessDenied",
                            "Message": "Access Denied",
                        }
                    },
                    "DeleteObject",
                ),
                "Access Denied",
                "Failed to delete object my-bucket/my-key due to S3 API error: "
                "An error occurred (AccessDenied) when calling the "
                "DeleteObject operation: Access Denied",
            ),
            (
                Exception("Unexpected deletion error"),
                "Unexpected deletion error",
                "An unexpected error occurred while deleting the object "
                "my-bucket/my-key: Unexpected deletion error",
            ),
        ],
    )
    def test_delete_object_errors(
        self,
        s3_builder: S3Builder,
        mock_s3_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
        exception_instance: Exception,
        match_pattern: str,
        expected_log_msg: str,
    ) -> None:
        """Test exception handling and logging behavior for delete_object failures."""
        bucket = "my-bucket"
        key = "my-key"

        mock_s3_client.delete_object.side_effect = exception_instance

        expected_log: tuple[str, int, str] = (
            "s3_file_organizer.s3_builder",
            logging.ERROR,
            expected_log_msg,
        )

        with pytest.raises(type(exception_instance), match=match_pattern):
            s3_builder.delete_object(bucket=bucket, key=key)

        mock_s3_client.delete_object.assert_called_once_with(Bucket=bucket, Key=key)
        assert expected_log in caplog.record_tuples


class TestMoveObject:
    """Group unit tests for S3Builder.move_object."""

    @pytest.mark.parametrize(
        "source_bucket, source_key, dest_bucket, dest_key",
        [
            ("my-bucket", "inbox/file.txt", "my-bucket", "processed/file.txt"),
            ("source-bucket", "raw/data.csv", "dest-bucket", "archive/data.csv"),
        ],
    )
    def test_move_object_success(
        self,
        s3_builder: S3Builder,
        caplog: pytest.LogCaptureFixture,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> None:
        """Test successful execution of move_object across
        various bucket combinations.
        """
        caplog.set_level(logging.INFO)

        with (
            patch.object(s3_builder, "copy_object", return_value=True) as mock_copy,
            patch.object(s3_builder, "delete_object", return_value=True) as mock_delete,
        ):
            expected_log: tuple[str, int, str] = (
                "s3_file_organizer.s3_builder",
                logging.INFO,
                f"Successfully moved object {source_bucket}/{source_key} "
                f"to {dest_bucket}/{dest_key}",
            )

            result = s3_builder.move_object(
                source_bucket=source_bucket,
                source_key=source_key,
                dest_bucket=dest_bucket,
                dest_key=dest_key,
            )

            mock_copy.assert_called_once_with(
                source_bucket=source_bucket,
                source_key=source_key,
                dest_bucket=dest_bucket,
                dest_key=dest_key,
            )
            mock_delete.assert_called_once_with(bucket=source_bucket, key=source_key)
            assert result is True
            assert expected_log in caplog.record_tuples

    @pytest.mark.parametrize(
        "exception_instance, failing_step, match_pattern, expected_log_msg",
        [
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "NoSuchKey",
                            "Message": "The specified key does not exist",
                        }
                    },
                    "CopyObject",
                ),
                "copy",
                "The specified key does not exist",
                "Failed to move object src-bkt/src-key to dst-bkt/dst-key "
                "due to S3 API error: An error occurred (NoSuchKey) when calling "
                "the CopyObject operation: The specified key does not exist",
            ),
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "AccessDenied",
                            "Message": "Access Denied",
                        }
                    },
                    "DeleteObject",
                ),
                "delete",
                "Access Denied",
                "Failed to move object src-bkt/src-key to dst-bkt/dst-key "
                "due to S3 API error: An error occurred (AccessDenied) when calling "
                "the DeleteObject operation: Access Denied",
            ),
            (
                Exception("Unexpected error during move"),
                "copy",
                "Unexpected error during move",
                "An unexpected error occurred while moving "
                "src-bkt/src-key to dst-bkt/dst-key: Unexpected error during move",
            ),
        ],
    )
    def test_move_object_errors(
        self,
        s3_builder: S3Builder,
        caplog: pytest.LogCaptureFixture,
        exception_instance: Exception,
        failing_step: str,
        match_pattern: str,
        expected_log_msg: str,
    ) -> None:
        """Test exception handling and short-circuit logic for move_object failures."""
        source_bucket = "src-bkt"
        source_key = "src-key"
        dest_bucket = "dst-bkt"
        dest_key = "dst-key"

        copy_kwargs: dict[str, Any] = {}
        delete_kwargs: dict[str, Any] = {}

        if failing_step == "copy":
            copy_kwargs["side_effect"] = exception_instance
            delete_kwargs["return_value"] = True
        else:
            copy_kwargs["return_value"] = True
            delete_kwargs["side_effect"] = exception_instance

        with (
            patch.object(s3_builder, "copy_object", **copy_kwargs) as mock_copy,
            patch.object(s3_builder, "delete_object", **delete_kwargs) as mock_delete,
        ):
            expected_log: tuple[str, int, str] = (
                "s3_file_organizer.s3_builder",
                logging.ERROR,
                expected_log_msg,
            )

            with pytest.raises(type(exception_instance), match=match_pattern):
                s3_builder.move_object(
                    source_bucket=source_bucket,
                    source_key=source_key,
                    dest_bucket=dest_bucket,
                    dest_key=dest_key,
                )

            mock_copy.assert_called_once_with(
                source_bucket=source_bucket,
                source_key=source_key,
                dest_bucket=dest_bucket,
                dest_key=dest_key,
            )

            if failing_step == "copy":
                mock_delete.assert_not_called()
            else:
                mock_delete.assert_called_once_with(
                    bucket=source_bucket, key=source_key
                )

            assert expected_log in caplog.record_tuples
