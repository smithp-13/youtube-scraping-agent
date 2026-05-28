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
    LANGFUSE_SECRET_KEY,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_BASE_URL,
    LANGFUSE_CACHE_TTL_SECONDS,
)


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
        """Lazily initialize the Langfuse client on first use."""
        if self._init_attempted:
            return
        self._init_attempted = True

        if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
            logger.error(
                "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set in .env. "
                "Prompts cannot be loaded without Langfuse credentials."
            )
            return

        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_BASE_URL,  # SDK param is 'host', env var is LANGFUSE_BASE_URL
            )
            self._langfuse_available = True
            logger.info(
                f"Langfuse client initialized — host={LANGFUSE_BASE_URL}"
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize Langfuse client: {e}. "
                "Prompts cannot be loaded."
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

        # ── Try with production label first ──────────────────────────────
        try:
            prompt_obj = self._client.get_prompt(
                name,
                label=label or "production",
                cache_ttl_seconds=ttl,
            )
            compiled = prompt_obj.compile(**variables)
            logger.debug(f"Prompt '{name}' fetched from Langfuse (label=production).")
            return compiled, prompt_obj
        except Exception as e:
            logger.debug(
                f"Langfuse production-label fetch failed for '{name}': {e}. "
                "Retrying with version=1..."
            )

        # ── Retry with version=1 (for prompts without production label) ──
        try:
            prompt_obj = self._client.get_prompt(
                name,
                version=1,
                cache_ttl_seconds=ttl,
            )
            compiled = prompt_obj.compile(**variables)
            logger.info(
                f"Prompt '{name}' fetched from Langfuse (version=1). "
                "Consider setting the 'production' label in the Langfuse dashboard."
            )
            return compiled, prompt_obj
        except Exception as e:
            raise RuntimeError(
                f"Failed to fetch prompt '{name}' from Langfuse: {e}. "
                f"Ensure the prompt exists in your Langfuse project at {LANGFUSE_BASE_URL}"
            ) from e


# ── Module-level singleton ───────────────────────────────────────────────
prompt_loader = PromptLoader()
