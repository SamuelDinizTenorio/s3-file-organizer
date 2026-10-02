import logging
from pathlib import Path

from botocore.exceptions import ClientError
from mypy_boto3_s3.type_defs import ObjectTypeDef

from s3_builder import S3Builder

logger = logging.getLogger(__name__)

# Default mapping of extensions to destination folders
DEFAULT_EXTENSION_RULES: dict[str, str] = {
    ".pdf": "documents/",
    ".doc": "documents/",
    ".docx": "documents/",
    ".txt": "documents/",
    ".csv": "data/",
    ".json": "data/",
    ".xlsx": "data/",
    ".png": "images/",
    ".jpg": "images/",
    ".jpeg": "images/",
    ".zip": "archives/",
    ".gz": "archives/",
}


class FileOrganizer:
    """Orchestrates file organization within S3 buckets based on extension rules."""

    def __init__(
        self,
        s3_builder: S3Builder,
        extension_rules: dict[str, str] | None = None,
    ) -> None:
        """Initialize FileOrganizer with an S3Builder instance and
        optional routing rules.

        Args:
            s3_builder (S3Builder): Configured S3 utility instance.
            extension_rules (dict[str, str] | None): Mapping of extensions
            to folder prefixes.
        """
        self.s3_builder = s3_builder
        self.extension_rules = extension_rules or DEFAULT_EXTENSION_RULES

    def get_target_prefix(self, source_key: str) -> str | None:
        """Determine destination folder prefix based on file extension."""
        ext: str = Path(source_key).suffix.lower()
        return self.extension_rules.get(ext)

    def resolve_destination_key(self, source_key: str, target_prefix: str) -> str:
        """Construct destination key placing the source filename under target_prefix."""
        filename: str = Path(source_key).name
        clean_prefix = target_prefix.strip("/")
        dest_key: str = f"{clean_prefix}/{filename}"
        return dest_key if clean_prefix else filename

    def organize_bucket(
        self,
        bucket: str,
        source_prefix: str = "",
        uncategorized_prefix: str | None = "others/",
    ) -> dict[str, int]:
        """Scan S3 bucket prefix and move files into categorized folders.

        Args:
            bucket (str): Name of the target S3 bucket.
            source_prefix (str): Folder prefix to scan (default: root of bucket).
            uncategorized_prefix (str | None): Fallback folder for unmapped extensions.

        Returns:
            dict[str, int]: Execution summary with counts of moved, skipped,
            and failed files.
        """
        objects: list[ObjectTypeDef] = self.s3_builder.list_objects(
            bucket=bucket,
            prefix=source_prefix,
        )
        stats = {"moved": 0, "skipped": 0, "failed": 0}

        for obj in objects:
            source_key = obj.get("Key")

            if not source_key or source_key.endswith("/"):
                stats["skipped"] += 1
                continue

            target_prefix = self.get_target_prefix(source_key) or uncategorized_prefix

            if not target_prefix:
                logger.info(
                    "Skipping %s: no category rule matched and no fallback defined",
                    source_key,
                )
                stats["skipped"] += 1
                continue

            dest_key = self.resolve_destination_key(
                source_key=source_key,
                target_prefix=target_prefix,
            )

            if source_key == dest_key:
                logger.debug(
                    "Skipping %s: object is already in target path %s",
                    source_key,
                    dest_key,
                )
                stats["skipped"] += 1
                continue

            try:
                self.s3_builder.move_object(
                    source_bucket=bucket,
                    source_key=source_key,
                    dest_bucket=bucket,
                    dest_key=dest_key,
                )
                stats["moved"] += 1
            except (ClientError, Exception) as ex:
                logger.error(
                    "Failed to organize object %s -> %s: %s",
                    source_key,
                    dest_key,
                    ex,
                )
                stats["failed"] += 1
                continue

        logger.info("Organization completed for bucket '%s': %s", bucket, stats)
        return stats
