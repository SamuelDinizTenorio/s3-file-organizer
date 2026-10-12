"""Utility functions for logging persistence and S3 management."""

import datetime
import logging
import os

from config import LOG_FILE_PATH
from s3_builder import S3Builder

logger = logging.getLogger(__name__)


def upload_log_to_s3(s3_builder: S3Builder, log_bucket: str) -> None:
    """Uploads the local execution log file to the specified S3 log bucket.

    Organizes the S3 log storage path using a temporal virtual key hierarchy
    structured as `organizer_logs/YYYY/MM/run_YYYYMMDD_HHMMSS.log`. Creates the
    target log bucket automatically if it does not exist.

    Args:
        s3_builder (S3Builder): Initialized S3 connection builder instance.
        log_bucket (str): Target S3 bucket name dedicated to log retention.

    Returns:
        None
    """
    if not os.path.exists(LOG_FILE_PATH):
        return

    client = s3_builder.s3_client

    try:
        client.head_bucket(Bucket=log_bucket)
    except Exception:
        logger.info(
            "Log bucket '%s' not found. Creating bucket...",
            log_bucket,
        )
        client.create_bucket(Bucket=log_bucket)

    now = datetime.datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    s3_log_key = f"organizer_logs/{year}/{month}/run_{timestamp}.log"

    try:
        client.upload_file(
            Filename=LOG_FILE_PATH,
            Bucket=log_bucket,
            Key=s3_log_key,
        )
        logger.info(
            "Log file successfully uploaded to s3://%s/%s",
            log_bucket,
            s3_log_key,
        )
    except Exception as ex:
        logger.error("Failed to upload log file to S3: %s", ex)
