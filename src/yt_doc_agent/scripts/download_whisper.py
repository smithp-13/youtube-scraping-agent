"""
Utility script to check and download the Whisper model specified in the .env configuration.
"""
import os
import sys
from pathlib import Path

# Add src/ directory to python path to import our modules
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from yt_doc_agent.core.config import (
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
)

# Read WHISPER_MODEL_DIR from env if set, otherwise default to HF cache
WHISPER_MODEL_DIR = os.getenv("WHISPER_MODEL_DIR", "").strip()

console = Console()

def main():
    console.print(Panel.fit(
        "[bold cyan]Whisper Model Downloader / Status Check[/bold cyan]\n"
        "[dim]YouTube Documentation Agent Helper[/dim]",
        border_style="cyan"
    ))

    model_size = WHISPER_MODEL_SIZE
    console.print(f"[bold]Configured Whisper Model Size:[/bold] {model_size}")
    
    # Determine the target directory
    if WHISPER_MODEL_DIR:
        target_dir = Path(WHISPER_MODEL_DIR).resolve()
        console.print(f"[bold]Target Storage Folder:[/bold] {target_dir} (Custom local directory)")
        os.makedirs(target_dir, exist_ok=True)
    else:
        # Default Hugging Face hub cache directory
        user_home = Path.home()
        target_dir = user_home / ".cache" / "huggingface" / "hub"
        console.print(f"[bold]Target Storage Folder:[/bold] {target_dir} (Default Hugging Face Cache)")

    # Model specific folder names in huggingface cache vs local dir
    # faster-whisper repository format is Systran/faster-whisper-<size>
    # huggingface_hub uses models--Systran--faster-whisper-<size> inside hub/
    hf_repo_name = f"models--Systran--faster-whisper-{model_size}"
    model_folder = target_dir / hf_repo_name if not WHISPER_MODEL_DIR else target_dir / f"faster-whisper-{model_size}"

    console.print(f"[bold]Expected Cache Subdirectory:[/bold] {model_folder.name}\n")

    # Check if files already exist
    is_downloaded = False
    if WHISPER_MODEL_DIR:
        # If storing locally, check if local directory contains model files
        # A fully downloaded model directory should contain config.json and model.bin
        if (target_dir / "config.json").exists() and (target_dir / "model.bin").exists():
            is_downloaded = True
            model_folder = target_dir
        elif (target_dir / f"faster-whisper-{model_size}" / "config.json").exists() and (target_dir / f"faster-whisper-{model_size}" / "model.bin").exists():
            is_downloaded = True
            model_folder = target_dir / f"faster-whisper-{model_size}"
    else:
        # Checking default Hugging Face cache
        if model_folder.exists():
            # Check if there's a snapshot/refs/main folder containing files
            snapshots_dir = model_folder / "snapshots"
            if snapshots_dir.exists():
                snapshots = list(snapshots_dir.glob("*"))
                if snapshots and any(s.is_dir() for s in snapshots):
                    is_downloaded = True

    if is_downloaded:
        console.print(Panel(
            f"[green bold]✓ Model '{model_size}' is already downloaded and cached![/green bold]\n\n"
            f"[bold]Location:[/bold] {model_folder}\n"
            f"[bold]Ready for use with device:[/bold] {WHISPER_DEVICE} ({WHISPER_COMPUTE_TYPE})",
            title="Status: Cached",
            border_style="green"
        ))
        return

    console.print(Panel(
        f"[yellow bold]⚠ Model '{model_size}' is NOT cached locally.[/yellow bold]\n\n"
        f"We will now download the [bold cyan]Systran/faster-whisper-{model_size}[/bold cyan] model from Hugging Face Hub.\n"
        f"This download is roughly [cyan]150MB[/cyan] and will be saved to your configured directory.",
        title="Status: Not Found",
        border_style="yellow"
    ))

    # Proceed with download using faster_whisper utility
    console.print("[cyan]Initiating download from Hugging Face Hub...[/cyan]")
    try:
        from faster_whisper import download_model
        
        # If a custom dir is set, we download to it directly. 
        # Otherwise, let download_model download to default HF cache.
        if WHISPER_MODEL_DIR:
            output_dir = str(target_dir / f"faster-whisper-{model_size}")
            console.print(f"Downloading to: [bold]{output_dir}[/bold]")
            downloaded_path = download_model(model_size, output_dir=output_dir)
        else:
            console.print("Downloading to default Hugging Face cache...")
            downloaded_path = download_model(model_size)
            
        console.print(Panel(
            f"[green bold]🎉 Success! Model '{model_size}' downloaded successfully.[/green bold]\n\n"
            f"[bold]Saved to path:[/bold] {downloaded_path}\n"
            f"[bold]Ready to use on device:[/bold] {WHISPER_DEVICE} ({WHISPER_COMPUTE_TYPE})",
            title="Download Complete",
            border_style="green"
        ))
        
    except Exception as e:
        console.print(f"[red bold]✗ Failed to download Whisper model: {e}[/red bold]")
        console.print("[yellow]Please check your internet connection or Hugging Face Hub availability.[/yellow]")
        sys.exit(1)

if __name__ == "__main__":
    main()
