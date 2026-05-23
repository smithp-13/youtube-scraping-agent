"""
Agent Node 10: Chapter Architect.
"""

from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import GraphState, Chapter
from yt_doc_agent.tools.youtube import seconds_to_timestamp
from yt_doc_agent.core.llm import get_llm, llm_call_with_retry, parse_llm_json
from yt_doc_agent.core.config import DEFAULT_MODEL, TEMP_STRUCTURED, MAX_CHAPTERS
from yt_doc_agent.prompts.chapter_architect import CHAPTER_ARCHITECT_PROMPT

console = Console()


def _build_timestamp_transcript(transcript_list: list) -> str:
    """Format transcript with timestamps for the LLM to process."""
    lines = []
    for item in transcript_list:
        ts = seconds_to_timestamp(item["start"])
        lines.append(f"[{ts}] {item['text']}")
    return "\n".join(lines)


def _seconds_to_duration_str(seconds: int) -> str:
    """Format duration seconds into human readable string."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


def _slice_transcript_for_chapter(transcript_list: list, start_ts: str, end_ts: str) -> str:
    """Extract transcript lines that fall within a timestamp range."""
    def ts_to_seconds(ts: str) -> float:
        parts = ts.strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])

    try:
        start_s = ts_to_seconds(start_ts)
        end_s = ts_to_seconds(end_ts) if end_ts else float("inf")
    except Exception as e:
        logger.warning(f"Failed parsing timestamps for transcript slicing: {e}. Slicing failed.")
        return " ".join(item["text"] for item in transcript_list)

    segment = [
        item["text"] for item in transcript_list
        if start_s <= item["start"] < end_s
    ]
    return " ".join(segment)


def run(state: GraphState) -> dict:
    """Analyze the transcript and define documentation chapters."""
    console.print("\n[bold cyan]▶ Step 10/13: Chapter Architect[/bold cyan]")
    logger.info("Running Agent: Chapter Architect")

    yt_chapters = state.get("youtube_chapters", [])
    transcript_list = state.get("transcript_with_timestamps", [])
    duration = _seconds_to_duration_str(state.get("video_duration_seconds", 0))

    # ── Path A: YouTube Chapters Available ────────────────────────────────
    if yt_chapters and len(yt_chapters) >= 2:
        console.print(f"[green]✓ Found {len(yt_chapters)} pre-defined YouTube chapters[/green]")
        logger.info(f"Using {len(yt_chapters)} native YouTube chapters.")
        
        chapters = []
        for i, ch in enumerate(yt_chapters[:MAX_CHAPTERS]):
            start_ts = seconds_to_timestamp(ch["start_seconds"])
            
            # End timestamp = next chapter's start, or end of video
            if i + 1 < len(yt_chapters):
                end_seconds = yt_chapters[i + 1]["start_seconds"]
            else:
                end_seconds = state.get("video_duration_seconds", 0)
                
            end_ts = seconds_to_timestamp(end_seconds)
            segment = _slice_transcript_for_chapter(transcript_list, start_ts, end_ts)
            
            chapters.append(Chapter(
                index=i + 1,
                title=ch["title"],
                start_timestamp=start_ts,
                end_timestamp=end_ts,
                transcript_segment=segment,
                source="youtube_chapters",
            ))

        return {
            "chapters": chapters,
            "chapters_source": "youtube_chapters",
            "current_step": "chapters_done",
        }

    # ── Path B: AI-Inferred Chapters (fallback) ───────────────────────────
    console.print("[yellow]No YouTube chapters found — inferring chapters from transcript via LLM...[/yellow]")
    logger.info("No pre-defined chapters. Running LLM chapter inference.")
    
    ts_transcript = _build_timestamp_transcript(transcript_list)
    # Truncate transcript excerpt to stay within the model's comfortable reasoning context
    ts_transcript = ts_transcript[:12000]

    prompt = CHAPTER_ARCHITECT_PROMPT.format(
        video_title=state.get("video_title", ""),
        duration=duration,
        transcript_with_timestamps=ts_transcript,
        max_chapters=MAX_CHAPTERS,
    )

    llm = get_llm(model=DEFAULT_MODEL, temperature=TEMP_STRUCTURED)
    try:
        response = llm_call_with_retry(llm, prompt)
        raw_chapters = parse_llm_json(response)
        
        chapters = []
        for ch in raw_chapters:
            chapters.append(Chapter(
                index=ch.get("index", len(chapters) + 1),
                title=ch.get("title", f"Chapter {len(chapters)+1}"),
                start_timestamp=ch.get("start_timestamp", "0:00"),
                end_timestamp=ch.get("end_timestamp", ""),
                transcript_segment=ch.get("transcript_segment", ""),
                source="ai_inferred",
            ))
            
        # Post-process to slice accurate segment transcripts for AI-inferred chapters
        # (the LLM might return summary or truncated segments in the transcript_segment field,
        # so we re-slice them using the estimated start/end timestamps from the full transcript)
        for i, ch in enumerate(chapters):
            next_start = chapters[i + 1].start_timestamp if i + 1 < len(chapters) else seconds_to_timestamp(state.get("video_duration_seconds", 0))
            if not ch.end_timestamp:
                ch.end_timestamp = next_start
            ch.transcript_segment = _slice_transcript_for_chapter(transcript_list, ch.start_timestamp, ch.end_timestamp)

        console.print(f"[green]✓ Successfully generated {len(chapters)} AI-inferred chapters[/green]")
        logger.info(f"LLM generated {len(chapters)} chapter structures.")
        
        return {
            "chapters": chapters,
            "chapters_source": "ai_inferred",
            "current_step": "chapters_done",
        }
        
    except Exception as e:
        logger.error(f"Chapter inference failed: {e}. Falling back to single video chapter.")
        console.print(f"[yellow]⚠ Chapter inference failed: {e} — falling back to single chapter[/yellow]")
        
        full_text = " ".join(item["text"] for item in transcript_list)
        fallback_chapters = [Chapter(
            index=1,
            title=state.get("video_title", ""),
            start_timestamp="0:00",
            end_timestamp=seconds_to_timestamp(state.get("video_duration_seconds", 0)),
            transcript_segment=full_text,
            source="ai_inferred",
        )]
        
        return {
            "chapters": fallback_chapters,
            "chapters_source": "ai_inferred",
            "current_step": "chapters_done",
        }
