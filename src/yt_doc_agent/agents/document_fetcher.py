"""
Agent Node 8: Document Fetcher.
"""

from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import GraphState, DocumentScore
from yt_doc_agent.tools import documents as document_tools

console = Console()

# Mapping document types to their respective utility fetchers
FETCHER_MAP = {
    "pdf": document_tools.fetch_pdf,
    "gdrive": document_tools.fetch_gdrive,
    "notion": document_tools.fetch_notion,
    "github": document_tools.fetch_github,
    "youtube": document_tools.fetch_youtube_transcript,
    "webpage": document_tools.fetch_webpage,
}


def run(state: GraphState) -> dict:
    """Retrieve content from all identified documentation links."""
    console.print("\n[bold cyan]▶ Step 8/13: Document Fetcher[/bold cyan]")
    logger.info("Running Agent: Document Fetcher")

    classified_links = state.get("classified_links", [])
    fetched = []
    errors = []

    for link in classified_links:
        url = link.get("url", "")
        doc_type = link.get("type", "webpage")
        title_guess = link.get("title_guess", url[:50])

        fetcher = FETCHER_MAP.get(doc_type, document_tools.fetch_webpage)
        console.print(f"[dim]Fetching [{doc_type.upper()}]: {url[:70]}[/dim]")
        logger.info(f"Fetching document of type '{doc_type}' from URL: {url}")

        try:
            content = fetcher(url)
            if content and len(content.strip()) > 50:
                fetched.append(DocumentScore(
                    url=url,
                    doc_type=doc_type,
                    title=title_guess,
                    content_text=content[:50000],  # cap at 50k characters for LLM limits
                    fetch_success=True,
                ))
                console.print(f"[green]  ✓ Fetched {len(content)} characters[/green]")
                logger.info(f"Successfully fetched document '{title_guess}': {len(content)} characters.")
            else:
                logger.warning(f"Empty content returned from URL: {url}")
                console.print(f"[yellow]  ⚠ Warning: Empty content returned[/yellow]")
        except Exception as e:
            logger.error(f"Failed to fetch document from {url}: {e}")
            console.print(f"[yellow]  ✗ Failed to fetch document: {e}[/yellow]")
            errors.append(f"Document fetch failed for {url}: {e}")

    console.print(f"[green]✓ Successfully fetched {len(fetched)}/{len(classified_links)} documents[/green]")
    return {
        "fetched_documents": fetched,
        "error_messages": errors,
        "current_step": "documents_fetched",
    }
