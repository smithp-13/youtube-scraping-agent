"""
Agent Node 2: URL Resolver.
"""

from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import GraphState
from yt_doc_agent.tools.youtube import is_playlist_url, get_playlist_items

console = Console()


def run(state: GraphState) -> dict:
    """Resolve input URL into playlist items or canonical single video URL."""
    console.print("\n[bold cyan]▶ Step 2/13: URL Resolver[/bold cyan]")
    logger.info("Running Agent: URL Resolver")

    url = state.get("input_url", "")
    if is_playlist_url(url):
        console.print("[yellow]Playlist URL detected. Fetching video list...[/yellow]")
        logger.info(f"Playlist detected: {url}")
        
        items = get_playlist_items(url)
        if not items:
            error_msg = "Could not fetch playlist items from YouTube."
            logger.error(error_msg)
            return {
                "error_messages": [error_msg],
                "is_playlist": True,
                "playlist_items": [],
                "current_step": "url_resolver_failed",
            }
            
        console.print(f"[green]✓ Found {len(items)} videos in playlist[/green]")
        return {
            "is_playlist": True,
            "playlist_items": items,
            "current_step": "url_resolved_playlist",
        }
    else:
        video_id = state.get("video_id", "")
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        console.print(f"[green]✓ Single video detected: {canonical_url}[/green]")
        logger.info(f"Single video detected: {canonical_url} (ID: {video_id})")
        return {
            "is_playlist": False,
            "video_url": canonical_url,
            "current_step": "url_resolved_single",
        }
