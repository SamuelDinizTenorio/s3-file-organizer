import logging
import os

from dotenv import load_dotenv

from s3_builder import S3Builder

load_dotenv()

AWS_ENDPOINT_URL=os.getenv('AWS_ENDPOINT_URL')
AWS_ACCESS_KEY_ID=os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY=os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION=os.getenv('AWS_REGION')

"""Basic log configuration"""
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    s3_builder = S3Builder(
        endpoint_url=AWS_ENDPOINT_URL,
        access_key_id=AWS_ACCESS_KEY_ID,
        secret_access_key=AWS_SECRET_ACCESS_KEY,
        region=AWS_REGION
    )
    logger.info("S3Builder initialized successfully: %s", s3_builder)

if __name__ == '__main__':
    main()
