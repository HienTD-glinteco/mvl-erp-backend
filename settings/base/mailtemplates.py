"""Mail template settings."""

import os
from pathlib import Path

from .base import BASE_DIR, config

# Mail template directory
MAIL_TEMPLATE_DIR = config(
    "MAIL_TEMPLATE_DIR",
    default=str(Path(BASE_DIR) / "templates" / "mail"),
)

# Ensure directory exists
os.makedirs(MAIL_TEMPLATE_DIR, exist_ok=True)

# Mail sending configuration
MAIL_SEND_CHUNK_SIZE = config("MAIL_SEND_CHUNK_SIZE", default=10, cast=int)
MAIL_SEND_SLEEP_BETWEEN_CHUNKS = config("MAIL_SEND_SLEEP_BETWEEN_CHUNKS", default=1.0, cast=float)
MAIL_SEND_MAX_ATTEMPTS = config("MAIL_SEND_MAX_ATTEMPTS", default=3, cast=int)
