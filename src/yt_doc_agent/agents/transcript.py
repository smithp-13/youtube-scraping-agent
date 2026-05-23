"""
Agent Node 5: Transcript Extraction.
"""

from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import GraphState
from yt_doc_agent.tools.youtube import get_transcript
from yt_doc_agent.tools.whisper import download_audio, transcribe_audio, cleanup_audio
from yt_doc_agent.core.llm import get_llm, llm_call_with_retry
from yt_doc_agent.core.config import FAST_MODEL, TEMP_STRUCTURED

console = Console()


def _join_transcript(transcript_list: list) -> str:
    """Join transcript items into a single space-separated string."""
    return " ".join(item["text"] for item in transcript_list)


def _punctuate_transcript(raw_text: str, llm) -> str:
    """Add punctuation to auto-generated transcripts via a fast LLM pass."""
    prompt = f"""The following text is an auto-generated transcript with no punctuation.
Add proper punctuation and capitalization ONLY. Do not summarize, rephrase, or remove any content.
Preserve all technical terms, package names, variables, and code commands exactly as written.

TRANSCRIPT:
{raw_text[:8000]}

Return only the corrected transcript text. No explanation, no markdown formatting.
"""
    try:
        logger.debug("Calling LLM to punctuate/clean up transcript excerpt.")
        return llm_call_with_retry(llm, prompt)
    except Exception as e:
        logger.warning(f"Transcript punctuation pass failed: {e}. Falling back to raw text.")
        return raw_text


def run(state: GraphState) -> dict:
    """Extract transcript using YouTube transcript API or local Whisper fallback."""
    console.print("\n[bold cyan]▶ Step 5/13: Transcript Extraction[/bold cyan]")
    logger.info("Running Agent: Transcript Extraction")

    video_id = state.get("video_id", "")
    video_url = state.get("video_url", "")

    if not video_id:
        error_msg = "Transcript extraction failed: No video ID available in state."
        logger.error(error_msg)
        return {
            "error_messages": [error_msg],
            "current_step": "transcript_failed",
        }

    # Try 1: YouTube Transcript API
    try:
        logger.info(f"Attempting to fetch transcript via API for video ID: {video_id}")
        transcript_list, source = get_transcript(video_id)
        raw_text = _join_transcript(transcript_list)

        console.print(f"[green]✓ Transcript retrieved via YouTube API ({len(transcript_list)} segments)[/green]")
        logger.info(f"Successfully retrieved API transcript: {len(transcript_list)} segments.")

        # Determine if auto-generated and needs punctuation (punctuation density check)
        punct_count = sum(1 for c in raw_text if c in ".!?,;:")
        if len(raw_text) > 0 and (punct_count / len(raw_text)) < 0.01:
            console.print("[dim]Auto-generated transcript detected (low punctuation) — adding punctuation...[/dim]")
            logger.info("Auto-generated transcript detected. Running punctuation cleanup pass.")
            
            llm = get_llm(model=FAST_MODEL, temperature=TEMP_STRUCTURED)
            cleaned = _punctuate_transcript(raw_text, llm)
        else:
            logger.info("Transcript already punctuated or too short to warrant pass.")
            cleaned = raw_text

        return {
            "transcript_with_timestamps": transcript_list,
            "raw_transcript": raw_text,
            "cleaned_transcript": cleaned,
            "transcript_source": "youtube_api",
            "current_step": "transcript_done",
        }

    except Exception as e:
        console.print(f"[yellow]YouTube API failed: {e}[/yellow]")
        console.print("[yellow]Falling back to local audio download + Whisper STT...[/yellow]")
        logger.warning(f"YouTube Transcript API failed: {e}. Falling back to Whisper STT.")

    # Try 2: yt-dlp + local faster-whisper
    try:
        # Download audio WAV file
        wav_path = download_audio(video_url, video_id)
        
        # Transcribe locally
        transcript_list, detected_lang = transcribe_audio(wav_path)
        
        # Clean up temporary WAV file immediately to save space
        cleanup_audio(wav_path)

        raw_text = _join_transcript(transcript_list)
        console.print(f"[green]✓ Transcript generated via Whisper ({len(transcript_list)} segments)[/green]")
        logger.info(f"Whisper transcription completed successfully. Language: {detected_lang}")

        return {
            "transcript_with_timestamps": transcript_list,
            "raw_transcript": raw_text,
            "cleaned_transcript": raw_text,
            "transcript_source": "whisper",
            "detected_language": detected_lang,
            "current_step": "transcript_done",
        }

    except Exception as whisper_err:
        error_msg = f"Transcript extraction failed entirely (Whisper fallback failed): {whisper_err}"
        logger.error(error_msg)
        return {
            "error_messages": [error_msg],
            "current_step": "transcript_failed",
        }
