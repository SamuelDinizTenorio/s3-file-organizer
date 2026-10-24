"""Command Line Interface (CLI) module for automated S3 file organization.

This module parses command-line arguments, executes the S3 object routing pipeline
via `FileOrganizer`, and handles execution log persistence by uploading local log files
to a dedicated S3 bucket structured by year and month.
"""

import argparse
import logging
import sys
from importlib.metadata import PackageNotFoundError, version

from s3_file_organizer.config import (
    AWS_ACCESS_KEY_ID,
    AWS_ENDPOINT_URL,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    setup_logging,
)
from s3_file_organizer.file_organizer import FileOrganizer
from s3_file_organizer.rules import EXTENSION_RULES
from s3_file_organizer.s3_builder import S3Builder
from s3_file_organizer.utils import upload_log_to_s3

logger = logging.getLogger(__name__)

FALLBACK_VERSION = "0.1.0"


def parse_arguments() -> argparse.Namespace:
    """Parses and validates command-line arguments for the CLI application.

    Returns:
        argparse.Namespace: Namespace object containing parsed CLI flags.
    """
    parser = argparse.ArgumentParser(
        description="Automated S3 File Organizer CLI - "
        "Routes files based on extension rules.",
    )

    try:
        app_version = version("s3-file-organizer")
    except PackageNotFoundError:
        logger.warning(
            "Package 's3-file-organizer' not found in environment metadata."
            + "Falling back to default version '%s'.",
            FALLBACK_VERSION,
        )
        app_version = FALLBACK_VERSION

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {app_version}",
        help="Show program's version number and exit.",
    )

    parser.add_argument(
        "-b",
        "--bucket",
        type=str,
        required=False,
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

    parser.add_argument(
        "-r",
        "--rules",
        action="store_true",
        help="Display all configured extension routing rules and exit.",
    )

    parser.add_argument(
        "-l",
        "--log-bucket",
        type=str,
        default="my-logs-localstack",
        help="Target S3 bucket for execution logs (default: my-logs-localstack).",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate file organization without making any changes in S3.",
    )

    return parser.parse_args()


def display_rules() -> None:
    """Prints the active extension routing rules in a readable format."""
    print("\n📦 Active Extension Routing Rules:")
    print("-" * 40)
    for category, extensions in EXTENSION_RULES.items():
        ext_list = ", ".join(extensions)
        print(f"  • {category.upper()}: [{ext_list}]")
    print("-" * 40 + "\n")


def main() -> None:
    """CLI execution entry point.

    Captures command-line arguments, initializes application logging, executes the
    bucket organization routine, and guarantees log persistence to S3 upon termination.
    """
    args: argparse.Namespace = parse_arguments()

    if args.rules:
        display_rules()
        sys.exit(0)

    if not args.bucket:
        print(
            "Error: the following arguments are required: -b/--bucket "
            + "(unless using --rules)"
        )
        sys.exit(1)

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
            dry_run=args.dry_run,
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
            log_bucket=args.log_bucket,
        )


if __name__ == "__main__":
    main()
