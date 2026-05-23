"""
Agent Node 3: Playlist Handler.
"""

from loguru import logger
from rich.console import Console
from rich.table import Table
from yt_doc_agent.core.state import GraphState

console = Console()


def run(state: GraphState) -> dict:
    """Prompt user to select a video from the playlist."""
    console.print("\n[bold cyan]▶ Step 3/13: Playlist Handler[/bold cyan]")
    logger.info("Running Agent: Playlist Handler")

    items = state.get("playlist_items", [])
    if not items:
        error_msg = "No playlist items to display."
        logger.error(error_msg)
        return {
            "error_messages": [error_msg],
            "current_step": "playlist_failed",
        }

    # Build and print a beautiful table of videos
    table = Table(title="Available Playlist Videos", show_lines=True)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Video Title", style="white")
    table.add_column("Video ID", style="dim")

    for item in items:
        table.add_row(str(item["index"]), item["title"], item["video_id"])

    console.print(table)

    # Interactive choice loop
    while True:
        try:
            choice = input(f"\nEnter the number of the video to process (1–{len(items)}): ").strip()
            idx = int(choice)
            if 1 <= idx <= len(items):
                selected = items[idx - 1]
                console.print(f"[green]✓ Selected: {selected['title']}[/green]")
                logger.info(f"User selected playlist item {idx}: {selected['title']} (ID: {selected['video_id']})")
                return {
                    "selected_video_id": selected["video_id"],
                    "video_url": selected["url"],
                    "video_id": selected["video_id"],
                    "current_step": "playlist_selected",
                }
            else:
                console.print(f"[red]Please enter a number between 1 and {len(items)}[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a valid number.[/red]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[red]Playlist selection cancelled by user.[/red]")
            logger.info("Playlist selection cancelled by user.")
            return {
                "error_messages": ["Playlist selection cancelled by user"],
                "current_step": "playlist_cancelled",
            }
