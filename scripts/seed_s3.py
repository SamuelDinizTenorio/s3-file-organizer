"""Script to provision localstack S3 buckets and seed sample files for testing."""

import logging
import sys
from pathlib import Path

# Points to the 'src' folder within the project root
ROOT_DIR = Path(__file__).resolve().parent.parent / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from s3_file_organizer.config import (  # noqa: E402
    AWS_ACCESS_KEY_ID,
    AWS_ENDPOINT_URL,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    setup_logging,
)
from s3_file_organizer.s3_builder import S3Builder  # noqa: E402

setup_logging()
logger = logging.getLogger(__name__)

s3_builder = S3Builder(
    endpoint_url=AWS_ENDPOINT_URL,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

BUCKET_NAME = "my-bucket-test"
LOG_BUCKET_NAME = "my-logs-localstack"


def seed_environment() -> None:
    """Creates test buckets and uploads sample files for local organization pipeline."""
    # 1. Creates the necessary buckets
    for bucket in [BUCKET_NAME, LOG_BUCKET_NAME]:
        try:
            s3_builder.s3_client.head_bucket(Bucket=bucket)
            logger.info(f"Bucket '{bucket}' it already exists.")
        except Exception:
            s3_builder.create_bucket(bucket_name=bucket)

    # 2. Creates temporary test files locally.
    sample_files = {
        "inbox/document.pdf": "Simulated content of a PDF file.",
        "inbox/file.txt": "Simulated content of a TXT file.",
        "inbox/report.csv": "id,name,value\n1,Product A,100",
        "inbox/file.xyz": "Unmapped extension content.",
    }

    # 3. Uploads directly to the test bucket.
    for key, content in sample_files.items():
        s3_builder.s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=content.encode("utf-8"),
        )
        logger.info("Test file sent: s3://%s/%s", BUCKET_NAME, key)

    logger.info("Local environment successfully populated! Ready to test cli.py.")


if __name__ == "__main__":
    seed_environment()
