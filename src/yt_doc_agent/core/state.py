"""
Pydantic state models for the YouTube Documentation Agent.
These define the shared state that flows through the LangGraph agents.
"""

from pydantic import BaseModel
from typing import List, Dict, Optional, Any, TypedDict, Annotated
import operator

class DocumentScore(BaseModel):
    url: str = ""
    doc_type: str = ""          # pdf | gdrive | notion | github | youtube | webpage
    title: str = ""
    content_text: str = ""      # raw extracted text
    fetch_success: bool = False
    relevance_score: float = 0.0
    completeness_score: float = 0.0
    accuracy_score: float = 0.0
    judge_notes: str = ""

class Chapter(BaseModel):
    index: int = 0
    title: str = ""
    start_timestamp: str = ""   # "MM:SS" or "HH:MM:SS"
    end_timestamp: str = ""
    transcript_segment: str = ""
    source: str = ""            # "youtube_chapters" | "ai_inferred"

class SectionOutput(BaseModel):
    chapter_index: int = 0
    chapter_title: str = ""
    timestamp: str = ""
    markdown_content: str = ""

class GraphState(TypedDict, total=False):
    # ── Input ──────────────────────────────────────────────
    input_url: str

    # ── URL Resolution ─────────────────────────────────────
    video_id: str
    is_playlist: bool
    playlist_items: List[Dict[str, str]]
    selected_video_id: str
    video_url: str

    # ── Video Metadata ─────────────────────────────────────
    video_title: str
    video_description: str
    video_duration_seconds: int
    channel_name: str
    youtube_chapters: List[Dict[str, Any]]

    # ── Transcript ─────────────────────────────────────────
    transcript_with_timestamps: List[Dict[str, Any]]
    raw_transcript: str
    cleaned_transcript: str
    transcript_source: str   # "youtube_api" | "whisper"

    # ── Language ───────────────────────────────────────────
    detected_language: str
    working_transcript: str  # always English, ready for agents

    # ── Description Links ──────────────────────────────────
    raw_links: List[str]
    classified_links: List[Dict[str, str]]

    # ── Fetched Documents ──────────────────────────────────
    fetched_documents: List[DocumentScore]

    # ── Chapters ───────────────────────────────────────────
    chapters: List[Chapter]
    chapters_source: str     # "youtube_chapters" | "ai_inferred"

    # ── Written Sections ───────────────────────────────────
    # Reducer allows parallel worker nodes to safely append to this list
    section_outputs: Annotated[List[SectionOutput], operator.add]

    # ── Final Output ───────────────────────────────────────
    output_file_path: str
    output_markdown: str

    # ── Control Flow ───────────────────────────────────────
    cache_hit: bool
    cached_output_path: str
    
    # Reducer allows agents to append errors without overwriting previous errors
    error_messages: Annotated[List[str], operator.add]
    current_step: str
    skip_document_pipeline: bool
