"""
YouTube Utility Functions — extracts metadata, playlists, and transcripts using yt-dlp and youtube-transcript-api.
"""

import re
import json
import subprocess
from typing import Optional, List, Dict, Any, Tuple
from loguru import logger
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from yt_doc_agent.core.config import YTDLP_TIMEOUT
from yt_doc_agent.core.exceptions import InvalidURLError, TranscriptNotAvailableError


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract the 11-character video ID from any YouTube URL format.
    
    Examples:
        - https://www.youtube.com/watch?v=dQw4w9WgXcQ
        - https://youtu.be/dQw4w9WgXcQ
        - https://www.youtube.com/shorts/dQw4w9WgXcQ
        - https://www.youtube.com/embed/dQw4w9WgXcQ
    """
    patterns = [
        r"(?:v=|\/embed\/|\/shorts\/|\/v\/|youtu\.be\/)([0-9A-Za-z_-]{11})",
        r"(?:watch\?v=)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
            
    # Try just matching any 11-char string if it's already an ID
    if len(url.strip()) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", url.strip()):
        return url.strip()
        
    return None


def is_playlist_url(url: str) -> bool:
    """Return True if URL represents a YouTube playlist and is not just a single video page."""
    return "list=" in url and "watch?v=" not in url


def get_playlist_items(url: str) -> List[Dict[str, Any]]:
    """
    Fetch all videos from a playlist using yt-dlp.
    Returns a list of dicts: {"index": int, "title": str, "video_id": str, "url": str}
    """
    logger.info(f"Fetching playlist items for URL: {url}")
    try:
        # Run yt-dlp with --flat-playlist and --dump-json to fetch item summaries quickly
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--dump-json",
            url
        ]
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=YTDLP_TIMEOUT
        )
        
        if result.returncode != 0:
            logger.error(f"yt-dlp playlist fetch failed: {result.stderr}")
            return []
            
        items = []
        idx = 1
        
        # Parse the JSON lines
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                video_id = data.get("id")
                if not video_id:
                    continue
                    
                items.append({
                    "index": idx,
                    "title": data.get("title") or f"Video {idx}",
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}"
                })
                idx += 1
            except json.JSONDecodeError as parse_err:
                logger.warning(f"Failed to parse playlist item line: {parse_err}")
                
        logger.info(f"Successfully loaded {len(items)} playlist items.")
        return items
        
    except subprocess.TimeoutExpired:
        logger.error("Timed out while fetching playlist items.")
        return []
    except Exception as e:
        logger.error(f"Error fetching playlist: {e}")
        return []


def get_video_metadata(url: str) -> Dict[str, Any]:
    """
    Fetch video metadata using yt-dlp.
    Returns a dict with: {title, description, duration_seconds, channel_name, chapters}
    """
    logger.info(f"Fetching video metadata for URL: {url}")
    try:
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-playlist",
            url
        ]
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=YTDLP_TIMEOUT
        )
        
        if result.returncode != 0:
            logger.error(f"yt-dlp metadata fetch failed: {result.stderr}")
            raise InvalidURLError(f"Failed to fetch metadata from URL. yt-dlp error: {result.stderr}")
            
        data = json.loads(result.stdout)
        
        # Extract chapters if present
        chapters = []
        raw_chapters = data.get("chapters")
        if raw_chapters:
            for ch in raw_chapters:
                chapters.append({
                    "title": ch.get("title") or "Untitled Chapter",
                    "start_seconds": float(ch.get("start_time", 0)),
                    "end_seconds": float(ch.get("end_time", 0)),
                })
                
        return {
            "title": data.get("title") or "Untitled Video",
            "description": data.get("description") or "",
            "duration_seconds": int(data.get("duration") or 0),
            "channel_name": data.get("uploader") or "",
            "chapters": chapters,
        }
        
    except subprocess.TimeoutExpired as e:
        logger.error("Timed out while fetching video metadata.")
        raise InvalidURLError("Timed out while fetching video metadata from YouTube.") from e
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse metadata JSON output: {e}")
        raise InvalidURLError("Failed to parse metadata returned by YouTube.") from e
    except Exception as e:
        logger.error(f"Failed to get video metadata: {e}")
        raise InvalidURLError(f"Failed to retrieve video metadata: {e}") from e


def get_transcript(video_id: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Fetch the transcript of a video using the youtube-transcript-api.
    
    Returns:
        (transcript_list, source_label)
        transcript_list: list of {"text": str, "start": float, "duration": float}
        source_label: "youtube_api"
        
    Raises:
        TranscriptNotAvailableError if no transcript could be retrieved.
    """
    logger.info(f"Fetching transcript for video ID: {video_id}")
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # 1. Prefer manual English transcripts
        try:
            transcript = transcript_list.find_manually_created_transcript(["en", "en-US", "en-GB"])
            logger.info("Found manual English transcript.")
        except NoTranscriptFound:
            # 2. Try generated English transcripts
            try:
                transcript = transcript_list.find_generated_transcript(["en", "en-US", "en-GB"])
                logger.info("Found generated English transcript.")
            except NoTranscriptFound:
                # 3. Take whatever manual/generated transcript is available
                # (we will translate it in the language agent)
                all_transcripts = list(transcript_list._manually_created_transcripts.values()) + \
                                  list(transcript_list._generated_transcripts.values())
                if not all_transcripts:
                    raise TranscriptNotAvailableError(f"No transcripts found for video {video_id}.")
                transcript = all_transcripts[0]
                logger.info(f"Found transcript in non-English language: {transcript.language_code}")
                
        data = transcript.fetch()
        
        # Format the items
        formatted_list = []
        for item in data:
            formatted_list.append({
                "text": item["text"].strip(),
                "start": float(item["start"]),
                "duration": float(item["duration"])
            })
            
        return formatted_list, "youtube_api"
        
    except (TranscriptsDisabled, NoTranscriptFound, Exception) as e:
        logger.warning(f"YouTube Transcript API failed for video '{video_id}': {e}")
        raise TranscriptNotAvailableError(f"YouTube transcript not available: {e}") from e


def seconds_to_timestamp(seconds: float) -> str:
    """Convert float seconds to 'MM:SS' or 'HH:MM:SS' string format."""
    total_seconds = int(round(seconds))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
