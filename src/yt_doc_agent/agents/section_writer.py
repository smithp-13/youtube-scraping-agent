"""
Agent Node 11: Section Writer.
"""

from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import SectionOutput
from yt_doc_agent.core.llm import get_llm, llm_call_with_retry
from yt_doc_agent.core.config import DEFAULT_MODEL, TEMP_WRITING, MIN_SECTION_WORDS
from yt_doc_agent.prompts.section_writer import SECTION_WRITER_PROMPT

console = Console()


def _build_document_context(fetched_docs: list, min_relevance: float = 5.0) -> str:
    """Consolidate high-relevance external documents into a structured reference text for the writer."""
    relevant = [d for d in fetched_docs if d.relevance_score >= min_relevance and d.fetch_success]
    if not relevant:
        return "No referenced documents with sufficient relevance score (>= 5.0) for this video."
        
    parts = []
    for doc in relevant:
        parts.append(
            f"### {doc.title} ({doc.doc_type.upper()}) | Reference Link: {doc.url}\n"
            f"Relevance: {doc.relevance_score}/10 | "
            f"Completeness: {doc.completeness_score}/10 | "
            f"Accuracy: {doc.accuracy_score}/10\n\n"
            f"{doc.content_text[:2000]}\n"  # Keep first 2k chars to avoid blowing LLM context
        )
    return "\n---\n".join(parts)


def run(state: dict) -> dict:
    """
    Generate professional Markdown documentation for a single chapter.
    This is designed to be run in parallel via LangGraph's Send API.
    Expected state: {"chapter": Chapter, "video_title": str, "fetched_documents": List[DocumentScore]}
    """
    chapter = state.get("chapter")
    if not chapter:
        error_msg = "Section writer failed: No chapter provided in mapped state."
        logger.error(error_msg)
        return {"error_messages": [error_msg]}

    video_title = state.get("video_title", "Unknown Title")
    fetched_documents = state.get("fetched_documents", [])
    
    console.print(f"[dim]  Writing: Chapter {chapter.index} — {chapter.title}[/dim]")
    logger.info(f"Writing technical documentation for Chapter {chapter.index}: {chapter.title}")

    document_context = _build_document_context(fetched_documents)
    llm = get_llm(model=DEFAULT_MODEL, temperature=TEMP_WRITING)

    # Truncate segment to a safe 8000 characters to keep inside tokens
    segment = chapter.transcript_segment[:8000]

    prompt = SECTION_WRITER_PROMPT.format(
        video_title=video_title,
        chapter_index=chapter.index,
        chapter_title=chapter.title,
        start_timestamp=chapter.start_timestamp,
        end_timestamp=chapter.end_timestamp,
        transcript_segment=segment,
        document_context=document_context,
        min_words=MIN_SECTION_WORDS,
    )

    try:
        markdown_content = llm_call_with_retry(llm, prompt)
        
        # Ensure it actually starts with a proper markdown title
        if not markdown_content.strip().startswith(f"## {chapter.index}."):
            # Prepend heading if missing
            markdown_content = f"## {chapter.index}. {chapter.title} `[{chapter.start_timestamp} – {chapter.end_timestamp}]`\n\n" + markdown_content
            
        output = SectionOutput(
            chapter_index=chapter.index,
            chapter_title=chapter.title,
            timestamp=f"{chapter.start_timestamp} – {chapter.end_timestamp}",
            markdown_content=markdown_content,
        )
        
        word_count = len(markdown_content.split())
        console.print(f"[green]  ✓ Written: Chapter {chapter.index} ({word_count} words)[/green]")
        logger.info(f"Successfully generated section {chapter.index} ({word_count} words).")
        
        return {"section_outputs": [output]}
        
    except Exception as e:
        logger.error(f"Failed to generate section {chapter.index}: {e}")
        console.print(f"[red]  ✗ Failed Chapter {chapter.index}: {e}[/red]")
        
        # Append a fallback failed heading
        fallback_md = (
            f"## {chapter.index}. {chapter.title} `[{chapter.start_timestamp} – {chapter.end_timestamp}]`\n\n"
            f"> ⚠️ **Warning:** Generation of this section failed due to an LLM error: {e}\n"
        )
        output = SectionOutput(
            chapter_index=chapter.index,
            chapter_title=chapter.title,
            timestamp=f"{chapter.start_timestamp} – {chapter.end_timestamp}",
            markdown_content=fallback_md,
        )
        return {
            "section_outputs": [output],
            "error_messages": [f"Section {chapter.index} write failed: {e}"]
        }
