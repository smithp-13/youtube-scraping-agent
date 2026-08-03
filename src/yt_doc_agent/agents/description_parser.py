"""
Agent Node 7: Description Parser.
"""

import re
from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import GraphState
from yt_doc_agent.core.llm import get_llm, llm_call_with_retry, parse_llm_json
from yt_doc_agent.core import config
from yt_doc_agent.core.config import TEMP_STRUCTURED
from yt_doc_agent.core.prompt_loader import prompt_loader

console = Console()

# Regular expression to catch any HTTP/HTTPS URLs
URL_PATTERN = re.compile(
    r"https?://[^\s\)\]\>\"\']+",
    re.IGNORECASE
)

# Social media, support platforms, and shopping domains to skip
SKIP_DOMAINS = [
    "twitter.com", "x.com", "instagram.com", "facebook.com",
    "linkedin.com", "tiktok.com", "discord.gg", "discord.com",
    "patreon.com", "buymeacoffee.com", "ko-fi.com",
    "amzn.to", "amazon.com", "ebay.com", "youtube.com/user",
    "youtube.com/c", "youtube.com/channel", "t.me",
]


def _is_skippable(url: str) -> bool:
    """Return True if the URL contains any domain we want to ignore."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in SKIP_DOMAINS)


def run(state: GraphState) -> dict:
    """Extract and classify useful documentation URLs from the video description."""
    console.print("\n[bold cyan]▶ Step 7/13: Description Parser[/bold cyan]")
    logger.info("Running Agent: Description Parser")

    description = state.get("video_description", "")
    if not description:
        console.print("[dim]No description found — skipping document pipeline[/dim]")
        logger.info("Empty video description. Skipping document pipeline.")
        return {
            "raw_links": [],
            "classified_links": [],
            "skip_document_pipeline": True,
            "current_step": "description_parsed",
        }

    # Extract all URLs using pattern
    all_urls = URL_PATTERN.findall(description)
    
    # Strip common trailing markdown or sentence punctuation
    clean_urls = [url.rstrip(".,;)>\"'") for url in all_urls]
    
    # Filter out skippable domains (social links, affiliate codes, support channels)
    filtered_urls = [url for url in clean_urls if not _is_skippable(url)]
    
    # Deduplicate preserving order
    unique_urls = list(dict.fromkeys(filtered_urls))

    console.print(f"[dim]Found {len(all_urls)} URLs, {len(unique_urls)} after filtration[/dim]")
    logger.debug(f"URLs found: {len(all_urls)}. Filtered to unique documentation URLs: {len(unique_urls)}")

    if not unique_urls:
        logger.info("No relevant documentation links found. Skipping document pipeline.")
        return {
            "raw_links": clean_urls,
            "classified_links": [],
            "skip_document_pipeline": True,
            "current_step": "description_parsed",
        }

    # Classify the links using LLM
    console.print(f"[yellow]Classifying {len(unique_urls)} URLs via LLM...[/yellow]")
    url_list_str = "\n".join(unique_urls)
    
    prompt_str, prompt_obj = prompt_loader.get_prompt("description_parser", {
        "url_list": url_list_str
    })

    llm = get_llm(model=config.DEFAULT_MODEL, temperature=TEMP_STRUCTURED)

    try:
        response_text = llm_call_with_retry(llm, prompt_str, prompt_obj=prompt_obj)
        classified = parse_llm_json(response_text)
        
        console.print(f"[green]✓ Classified {len(classified)} links[/green]")
        for item in classified:
            console.print(f"[dim]  [{item.get('type', 'webpage').upper()}] {item.get('url', '')[:60]}[/dim]")
            
        logger.info(f"Classified {len(classified)} links.")
        return {
            "raw_links": unique_urls,
            "classified_links": classified,
            "skip_document_pipeline": False,
            "current_step": "description_parsed",
        }
    except Exception as e:
        logger.warning(f"Link classification via LLM failed: {e}. Skipping document pipeline.")
        console.print(f"[yellow]⚠ Link classification failed: {e} — skipping document pipeline[/yellow]")
        return {
            "raw_links": unique_urls,
            "classified_links": [],
            "skip_document_pipeline": True,
            "current_step": "description_parsed",
        }
