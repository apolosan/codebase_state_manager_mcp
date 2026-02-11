"""Utilities for branch name handling."""

import re

MAX_BRANCH_NAME_LENGTH = 255


def sanitize_branch_name(branch_name: str) -> str:
    """Sanitize branch name for safe storage.

    Args:
        branch_name: Raw branch name from git.

    Returns:
        Sanitized branch name safe for storage.
    """
    if not branch_name:
        return ""

    # Replace slashes with underscores
    sanitized = branch_name.replace("/", "_")

    # Remove or replace problematic characters
    # Keep alphanumeric, hyphen, underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "", sanitized)

    # Truncate if too long
    if len(sanitized) > MAX_BRANCH_NAME_LENGTH:
        sanitized = sanitized[:MAX_BRANCH_NAME_LENGTH]

    return sanitized
