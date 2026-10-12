"""Configuration module for environment settings and logging initialization.

This module loads environment variables from a .env file, provides fallback
defaults for LocalStack AWS S3 development, and configures centralized application
logging to output to both standard console streams and persistent log files.
"""

import logging
import os

from dotenv import load_dotenv

# Load environment variables from .env file if available
load_dotenv()

# ==============================================================================
# AWS & LocalStack Connection Credentials / Endpoints
# ==============================================================================
AWS_ENDPOINT_URL: str = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

# Default relative filepath for output logs
LOG_DIR = "logs"
LOG_FILE_PATH: str = os.path.join(LOG_DIR, "s3_file_organizer.log")


def setup_logging(log_file: str = LOG_FILE_PATH) -> None:
    """Configures the root logger across the entire application ecosystem.

    Sets up a unified logging format, automatically creates missing target parent
    directories if a nested filepath is provided, and attaches two distinct output
    handlers:
    1. A `FileHandler` to record persistent log output on disk with UTF-8 encoding.
    2. A `StreamHandler` to emit log records in real time to the terminal (sys.stderr).

    Args:
        log_file (str, optional): Filepath where the output log file will be saved.
            If a nested directory path is supplied, parent folders are automatically
            created. Defaults to `LOG_FILE_PATH` ("logs/s3_file_organizer.log").

    Returns:
        None
    """
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
