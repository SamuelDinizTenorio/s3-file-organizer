"""Pytest configuration and shared test fixtures module for integration tests.

This module defines reusable test fixtures for S3Builder and FileOrganizer
integration test suites, providing real AWS client connections against a
LocalStack S3 instance and managing temporary bucket lifecycles.
"""

import os
import uuid
from typing import Generator

import pytest

from file_organizer import FileOrganizer
from s3_builder import S3Builder


@pytest.fixture(scope="module")
def integration_s3_builder() -> S3Builder:
    """Provide a real S3Builder instance connected to LocalStack S3.

    Uses the `AWS_ENDPOINT_URL` environment variable if set (useful for CI/CD
    environments), falling back to `http://localhost:4566`.

    Returns:
        S3Builder: A real S3Builder instance targeting LocalStack S3.
    """
    endpoint_url = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    return S3Builder(
        endpoint_url=endpoint_url,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )


@pytest.fixture
def test_bucket(integration_s3_builder: S3Builder) -> Generator[str, None, None]:
    """Create an isolated, uniquely named S3 bucket for each integration test.

    Purges all contained S3 objects and deletes the bucket during fixture teardown
    to prevent resource leaks between test executions.

    Yields:
        Generator[str, None, None]: The generated unique S3 bucket name.
    """
    bucket_name = f"test-bucket-{uuid.uuid4().hex[:8]}"

    # Setup
    integration_s3_builder.create_bucket(bucket_name=bucket_name)

    yield bucket_name

    # Teardown: empties objects before deleting the bucket
    try:
        objects = integration_s3_builder.list_objects(bucket=bucket_name)
        for obj in objects:
            key = obj.get("Key")
            if key:
                integration_s3_builder.delete_object(
                    bucket=bucket_name,
                    key=key,
                )
    except Exception:
        pass
    finally:
        try:
            integration_s3_builder.s3_client.delete_bucket(Bucket=bucket_name)
        except Exception:
            pass


@pytest.fixture
def integration_file_organizer(integration_s3_builder: S3Builder) -> FileOrganizer:
    """Provide a FileOrganizer instance backed by a real S3Builder connected
    to LocalStack.

    Returns:
        FileOrganizer: A FileOrganizer instance configured for integration testing.
    """
    return FileOrganizer(s3_builder=integration_s3_builder)
