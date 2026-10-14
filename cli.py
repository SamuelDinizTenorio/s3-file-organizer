"""Command Line Interface (CLI) module for automated S3 file organization.

This module parses command-line arguments, executes the S3 object routing pipeline
via `FileOrganizer`, and handles execution log persistence by uploading local log files
to a dedicated S3 bucket structured by year and month.
"""

import argparse
import logging

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_ENDPOINT_URL,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    setup_logging,
)
from file_organizer import FileOrganizer
from s3_builder import S3Builder
from utils import upload_log_to_s3

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parses and validates command-line arguments for the CLI application.

    Returns:
        argparse.Namespace: Namespace object containing parsed CLI flags.
    """
    parser = argparse.ArgumentParser(
        description="Automated S3 File Organizer CLI - "
        "Routes files based on extension rules.",
    )

    parser.add_argument(
        "-b",
        "--bucket",
        type=str,
        required=True,
        help="Target S3 bucket name to process.",
    )

    parser.add_argument(
        "-s",
        "--source-prefix",
        type=str,
        required=False,
        help="Optional S3 source prefix (folder) to filter object processing.",
    )

    parser.add_argument(
        "-u",
        "--uncategorized-prefix",
        type=str,
        required=False,
        help="Optional destination prefix for files with unmapped extensions.",
    )

    return parser.parse_args()


def main() -> None:
    """CLI execution entry point.

    Captures command-line arguments, initializes application logging, executes the
    bucket organization routine, and guarantees log persistence to S3 upon termination.
    """
    args: argparse.Namespace = parse_arguments()
    setup_logging()

    s3_builder = S3Builder(
        endpoint_url=AWS_ENDPOINT_URL,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )

    organizer = FileOrganizer(s3_builder=s3_builder)

    try:
        logger.info(
            "Starting organization process for bucket '%s'...",
            args.bucket,
        )
        stats = organizer.organize_bucket(
            bucket=args.bucket,
            source_prefix=args.source_prefix,
            uncategorized_prefix=args.uncategorized_prefix,
        )
        logger.info(
            "Organization process complete. Summary: %s",
            stats,
        )

    except Exception as ex:
        logger.error(
            "Error encountered during bucket organization: %s",
            ex,
        )

    finally:
        upload_log_to_s3(
            s3_builder=s3_builder,
            log_bucket="my-logs-localstack",
        )


if __name__ == "__main__":
    main()
