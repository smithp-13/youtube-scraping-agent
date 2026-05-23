"""
Agent Node 1: Cache Check.
"""

from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import GraphState
from yt_doc_agent.tools.cache import cache_get
from yt_doc_agent.tools.youtube import extract_video_id

console = Console()


def run(state: GraphState) -> dict:
    """Check if the video is already fully processed and cached."""
    console.print("\n[bold cyan]▶ Step 1/13: Cache Check[/bold cyan]")
    logger.info("Running Agent: Cache Check")

    video_id = extract_video_id(state.get("input_url", ""))
    if not video_id:
        error_msg = f"Cannot extract video ID from input URL: {state.get('input_url', '')}"
        logger.error(error_msg)
        return {
            "error_messages": [error_msg],
            "current_step": "cache_check_failed"
        }

    entry = cache_get(video_id)
    if entry:
        output_file = entry.get("output_file")
        console.print(f"[green]✓ Cache hit for video '{video_id}'[/green]")
        console.print(f"[green]  Output File: {output_file}[/green]")
        logger.info(f"Cache hit. Video ID: {video_id}. File: {output_file}")
        return {
            "video_id": video_id,
            "cache_hit": True,
            "cached_output_path": output_file,
            "current_step": "cache_hit",
        }

    console.print(f"[dim]Cache miss for video '{video_id}' — proceeding with full pipeline[/dim]")
    logger.info(f"Cache miss for video ID: {video_id}")
    return {
        "video_id": video_id,
        "cache_hit": False,
        "current_step": "cache_check_done",
    }
