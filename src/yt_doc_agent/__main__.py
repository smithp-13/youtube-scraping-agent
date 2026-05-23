"""
YouTube Documentation Agent — CLI Main Module.
"""

import sys
import argparse
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from yt_doc_agent.graph.pipeline import run_pipeline
from yt_doc_agent.core.state import GraphState
from yt_doc_agent.core.config import validate_config

console = Console()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="yt-doc-agent",
        description="Generate comprehensive developer documentation from a YouTube video or playlist.",
    )
    parser.add_argument(
        "url",
        help="YouTube video or playlist URL",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output directory where generated documentation Markdown files will be written (default: data/outputs)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip the cache check and force full reprocessing of the video transcript.",
    )
    parser.add_argument(
        "--model",
        help="Gemini model name override (e.g. gemini-2.5-flash, gemini-2.5-pro)",
    )
    parser.add_argument(
        "--whisper-model",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size override for local STT fallback (default: base)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Set logging level to DEBUG to print comprehensive step logs to stdout.",
    )
    return parser.parse_args()


def setup_logger(verbose: bool):
    """Adjust logger output formats and levels."""
    # Remove default handler
    try:
        logger.remove(0)
    except ValueError:
        pass

    log_level = "DEBUG" if verbose else "INFO"
    
    # Simple console format
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level
    )
    
    # Structured file logging under data/logs/
    logger.add(
        "data/logs/yt_doc_agent.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        encoding="utf-8"
    )


def main():
    """Entry point for the CLI script."""
    args = parse_args()
    setup_logger(args.verbose)

    console.print(Panel.fit(
        "[bold cyan]YouTube Documentation Agent[/bold cyan]\n"
        "[dim]LangChain · LangGraph · Google Gemini API[/dim]",
        border_style="cyan"
    ))
    console.print(f"[bold]Input URL:[/bold] {args.url}\n")

    # Run quick startup validation
    warnings = validate_config()
    for warning in warnings:
        if "[CRITICAL]" in warning:
            console.print(f"[red]{warning}[/red]")
            sys.exit(1)
        elif "[WARN]" in warning:
            logger.warning(warning)
            console.print(f"[yellow]{warning}[/yellow]")
        else:
            logger.info(warning)

    # 1. Package overrides mapping
    settings_overrides = {}
    if args.model:
        settings_overrides["DEFAULT_MODEL"] = args.model
        settings_overrides["FAST_MODEL"] = args.model
    if args.whisper_model:
        settings_overrides["WHISPER_MODEL_SIZE"] = args.whisper_model
    if args.output:
        settings_overrides["OUTPUTS_DIR"] = args.output

    # 2. Handle --no-cache by patching cache_get helper
    if args.no_cache:
        import yt_doc_agent.tools.cache as cache_tool
        cache_tool.cache_get = lambda video_id: None
        console.print("[yellow]⚠ Cache check disabled via --no-cache flag. Forcing regeneration.[/yellow]\n")

    # 3. Invoke pipeline
    try:
        final_state_dict = run_pipeline(args.url, settings_overrides)
        
        # 4. Display Results
        cache_hit = final_state_dict.get("cache_hit", False)
        output_file_path = final_state_dict.get("output_file_path", "")
        cached_output_path = final_state_dict.get("cached_output_path", "")
        
        if cache_hit:
            console.print(Panel.fit(
                f"[green]✓ Documentation loaded from cache (No LLM calls made).[/green]\n"
                f"[bold]Output File Path:[/bold] {cached_output_path}",
                border_style="green"
            ))
        elif output_file_path:
            console.print(Panel.fit(
                f"[green bold]✅ Documentation generation complete![/green bold]\n"
                f"[bold]Output File Path:[/bold] {output_file_path}",
                border_style="green"
            ))
            
            error_messages = final_state_dict.get("error_messages", [])
            if error_messages:
                console.print("\n[yellow]Non-fatal warnings occurred during run:[/yellow]")
                for err in error_messages:
                    console.print(f"  [yellow]⚠ {err}[/yellow]")
        else:
            console.print("[red]✗ Pipeline completed, but no documentation file was written.[/red]")
            for err in final_state_dict.get("error_messages", []):
                console.print(f"  [red]✗ {err}[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"\n[red bold]✗ Critical Pipeline Failure: {e}[/red bold]")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
