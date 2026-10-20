"""Routing rules module mapping file extensions to destination S3 folders.

This module defines the global extension-to-category mapping used by both
the core file organization pipeline and the Streamlit interface.
"""

EXTENSION_RULES: dict[str, list[str]] = {
    "documents": [".pdf", ".docx", ".txt", ".doc"],
    "data": [".csv", ".xlsx", ".json"],
    "images": [".png", ".jpg", ".jpeg"],
}
