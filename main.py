import logging
import os

from dotenv import load_dotenv

from s3_builder import S3Builder

load_dotenv()

AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

"""Basic log configuration"""
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main() -> None:
    s3_builder = S3Builder(
        endpoint_url=AWS_ENDPOINT_URL,
        access_key_id=AWS_ACCESS_KEY_ID,
        secret_access_key=AWS_SECRET_ACCESS_KEY,
        region=AWS_REGION,
    )
    logger.info("S3Builder initialized successfully: %s", s3_builder)


if __name__ == "__main__":
    main()
