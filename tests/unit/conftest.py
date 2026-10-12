"""Pytest configuration and shared test fixtures module.

This module defines reusable test fixtures for S3Builder and FileOrganizer
unit test suites, providing mocked AWS SDK clients, typed dependencies,
and isolated target instances.
"""

from typing import Generator, cast
from unittest.mock import MagicMock, patch

import pytest

from file_organizer import FileOrganizer
from s3_builder import S3Builder


@pytest.fixture
def mock_boto_client() -> Generator[MagicMock, None, None]:
    """Mock the `boto3.client` factory function for S3Builder initialization tests.

    Patches the low-level `boto3.client` invocation within the `s3_builder` module
    to prevent real AWS API calls during object construction.

    Yields:
        Generator[MagicMock, None, None]: The patched `boto3.client` mock object.
    """
    with patch("s3_builder.boto3.client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.fixture
def s3_builder(mock_boto_client: MagicMock) -> S3Builder:
    """Provide a concrete S3Builder instance backed by a mocked boto3 client.

    Used for unit testing S3Builder's internal operational methods such as
    `create_bucket`, `upload_file`, `list_objects`, `copy_object`, etc.

    Returns:
        S3Builder: An initialized S3Builder instance with internal AWS client mocked.
    """
    return S3Builder()


@pytest.fixture
def mock_s3_client(s3_builder: S3Builder) -> MagicMock:
    """Provide the internal `s3_client` attribute pre-cast as a MagicMock.

    Eliminates repetitive `cast(MagicMock, s3_builder.s3_client)` boilerplate
    in unit test functions for strict Mypy type-checking compliance.

    Returns:
        MagicMock: The internal low-level AWS S3 client mock.
    """
    return cast(MagicMock, s3_builder.s3_client)


@pytest.fixture
def mock_s3_builder() -> MagicMock:
    """Provide a standalone MagicMock matching the S3Builder specification.

    Used to isolate dependent classes (e.g., FileOrganizer) from S3Builder
    execution logic.

    Returns:
        MagicMock: A mocked instance constrained by the S3Builder interface spec.
    """
    mock_builder = MagicMock(spec=S3Builder)
    mock_builder.s3_client = MagicMock()
    return mock_builder


@pytest.fixture
def file_organizer(mock_s3_builder: MagicMock) -> FileOrganizer:
    """Provide a FileOrganizer instance configured with a mocked S3Builder.

    Returns:
        FileOrganizer: A ready-to-test FileOrganizer instance.
    """
    return FileOrganizer(s3_builder=mock_s3_builder)
