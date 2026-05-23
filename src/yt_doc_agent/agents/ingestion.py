"""
Agent Node 4: Video Ingestion.
"""

from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import GraphState
from yt_doc_agent.tools.youtube import get_video_metadata

console = Console()


def run(state: GraphState) -> dict:
    """Fetch video uploader, duration, title, description, and chapters."""
    console.print("\n[bold cyan]▶ Step 4/13: Video Ingestion[/bold cyan]")
    logger.info("Running Agent: Video Ingestion")

    url = state.get("video_url", "")
    if not url:
        error_msg = "Ingestion failed: No video URL available in state."
        logger.error(error_msg)
        return {
            "error_messages": [error_msg],
            "current_step": "ingestion_failed",
        }

    try:
        meta = get_video_metadata(url)
        console.print(f"[green]✓ Video Ingestion Complete[/green]")
        console.print(f"[green]  Title: {meta['title']}[/green]")
        console.print(f"[dim]  Channel: {meta['channel_name']} | Duration: {meta['duration_seconds']}s | Chapters: {len(meta['chapters'])}[/dim]")
        
        logger.info(f"Ingested video metadata successfully: {meta['title']}")
        return {
            "video_title": meta["title"],
            "video_description": meta["description"],
            "video_duration_seconds": meta["duration_seconds"],
            "channel_name": meta["channel_name"],
            "youtube_chapters": meta["chapters"],
            "current_step": "ingestion_done",
        }
    except Exception as e:
        error_msg = f"Video ingestion failed: {e}"
        logger.error(error_msg)
        return {
            "error_messages": [error_msg],
            "current_step": "ingestion_failed",
        }
