"""
Custom exceptions for the YouTube Documentation Agent.
"""

class YTDocAgentError(Exception):
    """Base exception for all YouTube Doc Agent errors."""
    pass


class TranscriptNotAvailableError(YTDocAgentError):
    """Raised when no transcript (neither API nor Whisper fallback) is available."""
    pass


class DocumentFetchError(YTDocAgentError):
    """Raised when fetching an external document fails."""
    pass


class LLMCallError(YTDocAgentError):
    """Raised when an LLM call fails after retries."""
    pass


class CacheCorruptError(YTDocAgentError):
    """Raised when cache files are corrupted."""
    pass


class InvalidURLError(YTDocAgentError):
    """Raised when the provided YouTube URL is invalid."""
    pass
