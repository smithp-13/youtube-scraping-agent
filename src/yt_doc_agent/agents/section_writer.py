"""
Agent Node 11: Section Writer.

Generates professional Markdown documentation for individual chapters.
Supports two modes:
  - Tool-augmented (ReAct): Uses web search & fetch tools to verify and
    enrich content while writing (when SECTION_WRITER_ENABLE_TOOLS=true).
  - Standard: Single LLM call with pre-fetched context only (legacy mode).
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from loguru import logger
from rich.console import Console

from yt_doc_agent.core.config import (
    DEFAULT_MODEL,
    GOOGLE_API_KEY,
    MIN_SECTION_WORDS,
    SECTION_WRITER_ENABLE_TOOLS,
    SECTION_WRITER_MAX_TOOL_CALLS,
    TEMP_WRITING,
)
from yt_doc_agent.core.exceptions import LLMCallError
from yt_doc_agent.core.llm import get_llm, llm_call_with_retry
from yt_doc_agent.core.state import SectionOutput
from yt_doc_agent.prompts.section_writer import (
    SECTION_WRITER_AGENT_PROMPT,
    SECTION_WRITER_PROMPT,
)

console = Console()


def _build_document_context(fetched_docs: list, min_relevance: float = 5.0) -> str:
    """Consolidate high-relevance external documents into a structured reference text for the writer."""
    relevant = [d for d in fetched_docs if d.relevance_score >= min_relevance and d.fetch_success]
    if not relevant:
        return "No referenced documents with sufficient relevance score (>= 5.0) for this video."

    parts: List[str] = []
    for doc in relevant:
        parts.append(
            f"### {doc.title} ({doc.doc_type.upper()}) | Reference Link: {doc.url}\n"
            f"Relevance: {doc.relevance_score}/10 | "
            f"Completeness: {doc.completeness_score}/10 | "
            f"Accuracy: {doc.accuracy_score}/10\n\n"
            f"{doc.content_text[:2000]}\n"  # Keep first 2k chars to avoid blowing LLM context
        )
    return "\n---\n".join(parts)


def _extract_markdown_from_agent_output(agent_output: Dict[str, Any]) -> str:
    """
    Extract the final markdown content from a ReAct agent's output messages.

    The agent's last message should contain the raw markdown documentation.

    Args:
        agent_output: Raw output dict from create_react_agent invocation.

    Returns:
        The markdown string from the agent's final response.
    """
    messages = agent_output.get("messages", [])
    if not messages:
        return ""

    final_message = messages[-1]
    if hasattr(final_message, "content"):
        return str(final_message.content)
    elif isinstance(final_message, dict):
        return str(final_message.get("content", ""))
    return str(final_message)


def _run_tool_augmented(
    chapter: Any,
    video_title: str,
    document_context: str,
    segment: str,
) -> str:
    """
    Execute the tool-augmented section writer using a ReAct sub-agent.

    The writer can use web_search, fetch_webpage, and fetch_github_repo
    tools to verify API calls, look up code examples, and enrich content.

    Args:
        chapter: Chapter Pydantic model with index, title, timestamps, etc.
        video_title: The YouTube video title.
        document_context: Pre-built document context string.
        segment: The transcript segment for this chapter.

    Returns:
        Generated markdown content string.

    Raises:
        LLMCallError: If the agent execution fails entirely.
    """
    from yt_doc_agent.tools.react_tools import get_writer_tools

    tools = get_writer_tools()
    tool_names = [t.name for t in tools]
    logger.debug(f"Section writer tools: {tool_names}")

    llm = ChatGoogleGenerativeAI(
        model=DEFAULT_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=TEMP_WRITING,
    )

    system_prompt = SECTION_WRITER_AGENT_PROMPT.format(
        video_title=video_title,
        chapter_index=chapter.index,
        chapter_title=chapter.title,
        start_timestamp=chapter.start_timestamp,
        end_timestamp=chapter.end_timestamp,
        transcript_segment=segment,
        document_context=document_context,
        min_words=MIN_SECTION_WORDS,
    )

    react_agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )

    agent_output = react_agent.invoke(
        {"messages": [("user", "Write the documentation section now.")]},
        config={"recursion_limit": SECTION_WRITER_MAX_TOOL_CALLS * 2 + 1},
    )

    return _extract_markdown_from_agent_output(agent_output)


def _run_standard(
    chapter: Any,
    video_title: str,
    document_context: str,
    segment: str,
) -> str:
    """
    Execute the standard (non-tool) section writer with a single LLM call.

    This is the legacy path used when SECTION_WRITER_ENABLE_TOOLS=false.

    Args:
        chapter: Chapter Pydantic model with index, title, timestamps, etc.
        video_title: The YouTube video title.
        document_context: Pre-built document context string.
        segment: The transcript segment for this chapter.

    Returns:
        Generated markdown content string.
    """
    llm = get_llm(model=DEFAULT_MODEL, temperature=TEMP_WRITING)

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

    return llm_call_with_retry(llm, prompt)


def run(state: dict) -> dict:
    """
    Generate professional Markdown documentation for a single chapter.

    This is designed to be run in parallel via LangGraph's Send API.
    Supports two modes based on SECTION_WRITER_ENABLE_TOOLS config:
      - Tool-augmented (ReAct): Uses web search tools to verify and enrich
      - Standard: Single LLM call with pre-fetched context only

    Expected state:
        {
            "chapter": Chapter,
            "video_title": str,
            "fetched_documents": List[DocumentScore],
            "working_transcript": str,
        }

    Returns:
        Dict with section_outputs and optional error_messages.
    """
    chapter = state.get("chapter")
    if not chapter:
        error_msg = "Section writer failed: No chapter provided in mapped state."
        logger.error(error_msg)
        return {"error_messages": [error_msg]}

    video_title: str = state.get("video_title", "Unknown Title")
    fetched_documents: list = state.get("fetched_documents", [])
    working_transcript: str = state.get("working_transcript", "")

    mode_label = "Tool-Augmented" if SECTION_WRITER_ENABLE_TOOLS else "Standard"
    console.print(
        f"[dim]  Writing ({mode_label}): "
        f"Chapter {chapter.index} — {chapter.title}[/dim]"
    )
    logger.info(
        f"Writing technical documentation for Chapter {chapter.index}: "
        f"{chapter.title} [mode={mode_label}]"
    )

    document_context = _build_document_context(fetched_documents)

    # Port fallback transcript slice logic if chapter transcript segment is empty
    segment: str = (
        chapter.transcript_segment[:8000]
        if chapter.transcript_segment
        else working_transcript[:4000]
    )

    try:
        if SECTION_WRITER_ENABLE_TOOLS:
            markdown_content = _run_tool_augmented(
                chapter=chapter,
                video_title=video_title,
                document_context=document_context,
                segment=segment,
            )
        else:
            markdown_content = _run_standard(
                chapter=chapter,
                video_title=video_title,
                document_context=document_context,
                segment=segment,
            )

        # Ensure it actually starts with a proper markdown title
        expected_heading = f"## {chapter.index}."
        if not markdown_content.strip().startswith(expected_heading):
            markdown_content = (
                f"## {chapter.index}. {chapter.title} "
                f"`[{chapter.start_timestamp} – {chapter.end_timestamp}]`\n\n"
                + markdown_content
            )

        output = SectionOutput(
            chapter_index=chapter.index,
            chapter_title=chapter.title,
            timestamp=f"{chapter.start_timestamp} – {chapter.end_timestamp}",
            markdown_content=markdown_content,
        )

        word_count = len(markdown_content.split())
        console.print(
            f"[green]  ✓ Written: Chapter {chapter.index} "
            f"({word_count} words, {mode_label})[/green]"
        )
        logger.info(
            f"Successfully generated section {chapter.index} "
            f"({word_count} words, mode={mode_label})."
        )

        return {"section_outputs": [output]}

    except Exception as e:
        logger.error(f"Failed to generate section {chapter.index}: {e}")
        console.print(f"[red]  ✗ Failed Chapter {chapter.index}: {e}[/red]")

        # Append a fallback failed heading
        fallback_md = (
            f"## {chapter.index}. {chapter.title} "
            f"`[{chapter.start_timestamp} – {chapter.end_timestamp}]`\n\n"
            f"> ⚠️ **Warning:** Generation of this section failed "
            f"due to an error: {e}\n"
        )
        output = SectionOutput(
            chapter_index=chapter.index,
            chapter_title=chapter.title,
            timestamp=f"{chapter.start_timestamp} – {chapter.end_timestamp}",
            markdown_content=fallback_md,
        )
        return {
            "section_outputs": [output],
            "error_messages": [f"Section {chapter.index} write failed: {e}"],
        }
