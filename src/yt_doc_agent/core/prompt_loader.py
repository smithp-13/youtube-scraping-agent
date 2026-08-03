"""
Langfuse Prompt Loader — fetches prompts exclusively from Langfuse cloud.

Usage:
    from yt_doc_agent.core.prompt_loader import prompt_loader

    prompt = prompt_loader.get_prompt("chapter_architect", {
        "video_title": "My Video",
        "duration": "15m 30s",
        ...
    })

Design:
    1. On first call, initializes a Langfuse client using config keys.
    2. get_prompt(name, variables) fetches from Langfuse → compiles with variables.
    3. Prompts in Langfuse use {{variable}} syntax; the SDK's .compile() handles substitution.
    4. No local fallback — if Langfuse is not configured or fails, an error is raised.
"""

from typing import Optional, Tuple, Any
from loguru import logger

from yt_doc_agent.core.config import (
    LANGFUSE_BASE_URL,
    LANGFUSE_CACHE_TTL_SECONDS,
)
from yt_doc_agent.core.langfuse_client import get_langfuse_client


class PromptLoader:
    """
    Singleton-style prompt loader.
    Fetches prompts exclusively from Langfuse cloud.
    """

    def __init__(self) -> None:
        self._client = None
        self._langfuse_available = False
        self._init_attempted = False

    def _ensure_client(self) -> None:
        """Lazily initialize the shared Langfuse client on first use."""
        if self._init_attempted:
            return
        self._init_attempted = True

        self._client = get_langfuse_client()
        self._langfuse_available = self._client is not None

        if not self._langfuse_available:
            logger.error(
                "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set in .env. "
                "Prompts cannot be loaded without Langfuse credentials."
            )

    def get_prompt(
        self,
        name: str,
        variables: dict[str, str],
        *,
        label: Optional[str] = None,
        cache_ttl_seconds: Optional[int] = None,
    ) -> Tuple[str, Any]:
        """
        Fetch a prompt by name from Langfuse, compile it with the given
        variables, and return the final string alongside the prompt object.

        Args:
            name: Langfuse prompt name (e.g. "chapter_architect").
            variables: Dict of variable name → value to inject into the prompt.
            label: Optional Langfuse label (default: tries "production", then version=1).
            cache_ttl_seconds: Override cache TTL for this call.

        Returns:
            A tuple of (compiled_prompt_string, prompt_obj).

        Raises:
            RuntimeError: If Langfuse is not configured or the prompt cannot be fetched.
        """
        self._ensure_client()

        if not self._langfuse_available or not self._client:
            raise RuntimeError(
                "Langfuse client is not available. "
                "Check LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_BASE_URL in .env"
            )

        ttl = cache_ttl_seconds if cache_ttl_seconds is not None else LANGFUSE_CACHE_TTL_SECONDS

        # Try the requested/production label first, then fall back to version=1
        # (for prompts that haven't had a label assigned yet).
        attempts = [
            {"label": label or "production"},
            {"version": 1},
        ]

        last_error: Optional[Exception] = None
        for i, kwargs in enumerate(attempts):
            try:
                prompt_obj = self._client.get_prompt(name, cache_ttl_seconds=ttl, **kwargs)
                compiled = prompt_obj.compile(**variables)
                if i == 0:
                    logger.debug(f"Prompt '{name}' fetched from Langfuse ({kwargs}).")
                else:
                    logger.info(
                        f"Prompt '{name}' fetched from Langfuse ({kwargs}). "
                        "Consider setting the 'production' label in the Langfuse dashboard."
                    )
                return compiled, prompt_obj
            except Exception as e:
                last_error = e
                logger.debug(f"Langfuse fetch failed for '{name}' with {kwargs}: {e}.")

        raise RuntimeError(
            f"Failed to fetch prompt '{name}' from Langfuse: {last_error}. "
            f"Ensure the prompt exists in your Langfuse project at {LANGFUSE_BASE_URL}"
        ) from last_error


# ── Module-level singleton ───────────────────────────────────────────────
prompt_loader = PromptLoader()
