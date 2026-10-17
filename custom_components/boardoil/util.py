"""Helpers for BoardOil."""

from slugify import slugify


def create_unique_id(client_id: int, username: str) -> str:
    """Create a unique ID from the account ID and username."""
    return slugify(f"{client_id}-{username}")
