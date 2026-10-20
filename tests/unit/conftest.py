"""Pytest configuration and shared test fixtures module.

This module defines reusable test fixtures for S3Builder, FileOrganizer,
and CLI unit test suites, providing mocked AWS SDK clients, typed dependencies,
and isolated CLI module mocks.
"""

from typing import Generator, cast
from unittest.mock import MagicMock, patch

import pytest
from s3_file_organizer.file_organizer import FileOrganizer
from s3_file_organizer.s3_builder import S3Builder

# =====================================================================
# 1. S3 Infrastructure & Low-Level Boto3 Client Mocks
# =====================================================================


@pytest.fixture
def mock_boto_client() -> Generator[MagicMock, None, None]:
    """Mock the `boto3.client` factory function for S3Builder initialization tests.

    Patches the low-level `boto3.client` invocation within the `s3_builder` module
    to prevent real AWS API calls during object construction.

    Yields:
        Generator[MagicMock, None, None]: The patched `boto3.client` mock object.
    """
    with patch("s3_file_organizer.s3_builder.boto3.client") as mock_client:
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


# =====================================================================
# 2. Business Logic Mocks & Instances (FileOrganizer & S3Builder Mocks)
# =====================================================================


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


# =====================================================================
# 3. CLI Module Mocks (Command-Line Interface patch fixtures)
# =====================================================================


@pytest.fixture
def mock_upload_log() -> Generator[MagicMock, None, None]:
    """Mock the upload_log_to_s3 utility function for CLI tests.

    Yields:
        MagicMock: The patched upload_log_to_s3 mock object.
    """
    with patch("s3_file_organizer.cli.upload_log_to_s3") as mock_patch:
        yield mock_patch


@pytest.fixture
def mock_file_organizer_cls() -> Generator[MagicMock, None, None]:
    """Mock the FileOrganizer class for CLI tests.

    Yields:
        MagicMock: The patched FileOrganizer class mock object.
    """
    with patch("s3_file_organizer.cli.FileOrganizer") as mock_patch:
        yield mock_patch


@pytest.fixture
def mock_setup_logging() -> Generator[MagicMock, None, None]:
    """Mock the setup_logging configuration function for CLI tests.

    Yields:
        MagicMock: The patched setup_logging mock object.
    """
    with patch("s3_file_organizer.cli.setup_logging") as mock_patch:
        yield mock_patch
