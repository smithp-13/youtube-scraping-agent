"""
Shared Langfuse client singleton.

Both llm.py (tracing) and prompt_loader.py (prompt fetching) need a Langfuse
client backed by the same credentials — this module ensures they share one
connection instead of each opening its own.
"""

import atexit
from typing import Optional
from loguru import logger

from yt_doc_agent.core.config import (
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
    LANGFUSE_BASE_URL,
)

_client = None
_init_attempted = False


def get_langfuse_client() -> Optional["Langfuse"]:
    """Lazily initialize and return the shared Langfuse client, or None if unavailable."""
    global _client, _init_attempted

    if _init_attempted:
        return _client
    _init_attempted = True

    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        return None

    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_BASE_URL,
        )
        atexit.register(_client.flush)
        logger.info(f"Langfuse client initialized — host={LANGFUSE_BASE_URL}")
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse client: {e}")

    return _client
