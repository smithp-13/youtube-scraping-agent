"""
JSON-file-based cache management for processed videos.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from loguru import logger
from yt_doc_agent.core.config import CACHE_FILE


def _load_cache() -> Dict[str, Any]:
    """Load cache from disk. Return empty dict if file missing or corrupt."""
    if not os.path.exists(CACHE_FILE):
        logger.debug(f"Cache file '{CACHE_FILE}' does not exist. Starting fresh.")
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Cache file '{CACHE_FILE}' is corrupt or unreadable ({e}). Renaming and starting fresh.")
        try:
            corrupt_path = CACHE_FILE + ".corrupt"
            if os.path.exists(CACHE_FILE):
                os.rename(CACHE_FILE, corrupt_path)
                logger.info(f"Backed up corrupt cache file to '{corrupt_path}'")
        except OSError as rename_err:
            logger.error(f"Failed to back up corrupt cache file: {rename_err}")
        return {}


def _save_cache(data: Dict[str, Any]) -> None:
    """Write cache to disk."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.debug(f"Cache successfully saved to '{CACHE_FILE}'")
    except OSError as e:
        logger.error(f"Failed to save cache to disk: {e}")


def cache_get(video_id: str) -> Optional[Dict[str, Any]]:
    """Return cache entry for video_id if status is 'complete' and the cached file still exists."""
    cache = _load_cache()
    entry = cache.get(video_id)
    if not entry:
        return None
        
    if entry.get("status") != "complete":
        logger.debug(f"Cache hit for video '{video_id}' but status is '{entry.get('status')}', not 'complete'.")
        return None
        
    output_file = entry.get("output_file", "")
    if not output_file or not os.path.exists(output_file):
        logger.debug(f"Cache hit for video '{video_id}' but the output file '{output_file}' is missing.")
        return None
        
    logger.info(f"Cache hit for video '{video_id}' with output '{output_file}'")
    return entry


def cache_write(video_id: str, entry: Dict[str, Any]) -> None:
    """Write or update a cache entry."""
    cache = _load_cache()
    
    # Store clean UTC timestamp
    entry["processed_at"] = datetime.now(timezone.utc).isoformat()
    cache[video_id] = entry
    
    _save_cache(cache)
    logger.info(f"Cached state for video '{video_id}' updated.")
