"""
Agent Node 13: Cache Writer.
"""

from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import GraphState
from yt_doc_agent.tools.cache import cache_write

console = Console()


def run(state: GraphState) -> dict:
    """Store the completed pipeline state into the cache index file."""
    console.print("\n[bold cyan]▶ Step 13/13: Cache Writer[/bold cyan]")
    logger.info("Running Agent: Cache Writer")

    video_id = state.get("video_id", "")
    if not video_id:
        logger.warning("Cache Writer skipped: No video ID available in state.")
        return {"current_step": "done"}

    # Structuring clean, descriptive entry for json cache index
    entry = {
        "video_id": video_id,
        "video_title": state.get("video_title", ""),
        "input_url": state.get("input_url", ""),
        "transcript_source": state.get("transcript_source", ""),
        "detected_language": state.get("detected_language", ""),
        "documents_found": len(state.get("classified_links", [])),
        "documents_processed": [
            {
                "url": d.url,
                "type": d.doc_type,
                "relevance_score": d.relevance_score,
                "completeness_score": d.completeness_score,
                "accuracy_score": d.accuracy_score,
            }
            for d in state.get("fetched_documents", [])
        ],
        "chapters_source": state.get("chapters_source", ""),
        "chapters_count": len(state.get("chapters", [])),
        "output_file": state.get("output_file_path", ""),
        "error_count": len(state.get("error_messages", [])),
        "status": "complete",
    }

    try:
        cache_write(video_id, entry)
        console.print(f"[green]✓ Cache index updated for video ID '{video_id}'[/green]")
        logger.info(f"Successfully cached run summary for video: {video_id}")
    except Exception as e:
        logger.error(f"Failed to write cache entry for '{video_id}': {e}")
        console.print(f"[yellow]⚠ Failed to update cache index: {e}[/yellow]")

    return {"current_step": "done"}
