"""
Agent Node: Research Agent (ReAct).

Replaces the linear description_parser → document_fetcher → relevance_judge
pipeline with a single tool-calling agent that autonomously decides what
documents to fetch and proactively searches for missing context.
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
    REACT_MAX_ITERATIONS,
    TEMP_STRUCTURED,
)
from yt_doc_agent.core.exceptions import LLMCallError
from yt_doc_agent.core.llm import parse_llm_json
from yt_doc_agent.core.state import DocumentScore, GraphState
from yt_doc_agent.prompts.research_agent import RESEARCH_AGENT_SYSTEM_PROMPT
from yt_doc_agent.tools.react_tools import get_research_tools

console = Console()


def _extract_final_documents(agent_output: Dict[str, Any]) -> List[DocumentScore]:
    """
    Parse the ReAct agent's final message to extract structured DocumentScore objects.

    The agent is instructed to return a JSON block with a 'documents' array.
    This function finds that JSON, validates it, and converts each entry
    into a DocumentScore Pydantic model.

    Args:
        agent_output: The raw output dict from create_react_agent invocation.

    Returns:
        List of validated DocumentScore objects.
    """
    messages = agent_output.get("messages", [])
    if not messages:
        logger.warning("Research agent returned no messages")
        return []

    # The final message should contain the structured JSON output
    final_message = messages[-1]
    content: str = ""

    if hasattr(final_message, "content"):
        content = str(final_message.content)
    elif isinstance(final_message, dict):
        content = str(final_message.get("content", ""))

    if not content:
        logger.warning("Research agent's final message has no content")
        return []

    # Parse the JSON from the agent's response
    try:
        parsed = parse_llm_json(content)
    except (ValueError, Exception) as e:
        logger.error(f"Failed to parse research agent's final output as JSON: {e}")
        logger.debug(f"Raw final message content: {content[:2000]}")
        return []

    # Handle both direct list and nested dict formats
    raw_documents: List[Dict[str, Any]] = []
    if isinstance(parsed, dict):
        raw_documents = parsed.get("documents", [])
    elif isinstance(parsed, list):
        raw_documents = parsed

    # Convert to DocumentScore objects with validation
    scored_documents: List[DocumentScore] = []
    for doc_data in raw_documents:
        try:
            doc = DocumentScore(
                url=str(doc_data.get("url", "")),
                doc_type=str(doc_data.get("doc_type", "webpage")),
                title=str(doc_data.get("title", "")),
                content_text=str(doc_data.get("content_summary", ""))[:50000],
                fetch_success=True,
                relevance_score=float(doc_data.get("relevance_score", 0.0)),
                completeness_score=float(doc_data.get("completeness_score", 0.0)),
                accuracy_score=float(doc_data.get("accuracy_score", 0.0)),
                judge_notes=str(doc_data.get("judge_notes", "")),
            )
            scored_documents.append(doc)
            logger.debug(
                f"Parsed document: {doc.title} | R={doc.relevance_score} "
                f"C={doc.completeness_score} A={doc.accuracy_score}"
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed document entry: {e}")
            continue

    return scored_documents


def _extract_classified_links(
    scored_documents: List[DocumentScore],
) -> List[Dict[str, str]]:
    """
    Build the classified_links list from scored documents for backward
    compatibility with the GraphState schema.

    Args:
        scored_documents: Validated DocumentScore objects.

    Returns:
        List of dicts with 'url', 'type', and 'title_guess' keys.
    """
    return [
        {
            "url": doc.url,
            "type": doc.doc_type,
            "title_guess": doc.title,
        }
        for doc in scored_documents
    ]


def run(state: GraphState) -> dict:
    """
    Execute the ReAct research agent.

    Analyzes the video transcript and description, uses tools to fetch
    documents and search the web, then returns curated DocumentScore
    objects with relevance scoring.

    This node replaces the old description_parser → document_fetcher →
    relevance_judge chain.

    Args:
        state: The current LangGraph pipeline state.

    Returns:
        Dict with fetched_documents, classified_links, raw_links,
        skip_document_pipeline, and current_step.
    """
    console.print("\n[bold cyan]▶ Step 7/13: Research Agent (ReAct)[/bold cyan]")
    logger.info("Running Agent: Research Agent (ReAct)")

    # ── Extract context from state ────────────────────────────────────
    video_title: str = state.get("video_title", "")
    video_description: str = state.get("video_description", "")
    working_transcript: str = state.get("working_transcript", "")
    transcript_excerpt: str = working_transcript[:6000]

    # ── Build tools ───────────────────────────────────────────────────
    tools = get_research_tools()
    tool_names = [t.name for t in tools]
    console.print(f"[dim]Available tools: {', '.join(tool_names)}[/dim]")
    logger.info(f"Research agent tools: {tool_names}")

    # ── Create LLM with tool binding ──────────────────────────────────
    if not GOOGLE_API_KEY:
        raise LLMCallError(
            "GOOGLE_API_KEY is not set. Cannot initialize research agent."
        )

    llm = ChatGoogleGenerativeAI(
        model=DEFAULT_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=TEMP_STRUCTURED,
    )

    # ── Build the system prompt ───────────────────────────────────────
    system_prompt = RESEARCH_AGENT_SYSTEM_PROMPT.format(
        video_title=video_title,
        video_description=video_description[:4000],
        transcript_excerpt=transcript_excerpt,
    )

    # ── Create and invoke the ReAct agent ─────────────────────────────
    console.print(
        f"[yellow]Starting ReAct research loop "
        f"(max {REACT_MAX_ITERATIONS} iterations)...[/yellow]"
    )
    logger.info(
        f"Creating ReAct agent with recursion_limit={REACT_MAX_ITERATIONS}"
    )

    try:
        react_agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt,
        )

        agent_output = react_agent.invoke(
            {"messages": [("user", "Begin your research now.")]},
            config={"recursion_limit": REACT_MAX_ITERATIONS * 2 + 1},
        )
    except Exception as e:
        error_msg = f"Research agent execution failed: {e}"
        logger.error(error_msg)
        console.print(f"[red]✗ {error_msg}[/red]")
        return {
            "fetched_documents": [],
            "classified_links": [],
            "raw_links": [],
            "skip_document_pipeline": True,
            "error_messages": [error_msg],
            "current_step": "research_failed",
        }

    # ── Parse results ─────────────────────────────────────────────────
    scored_documents = _extract_final_documents(agent_output)
    classified_links = _extract_classified_links(scored_documents)
    raw_links = [doc.url for doc in scored_documents]

    console.print(
        f"[green]✓ Research agent completed: "
        f"{len(scored_documents)} documents gathered and scored[/green]"
    )

    for doc in scored_documents:
        console.print(
            f"[dim]  [{doc.doc_type.upper()}] {doc.title[:50]} | "
            f"R={doc.relevance_score} C={doc.completeness_score} "
            f"A={doc.accuracy_score}[/dim]"
        )

    logger.info(
        f"Research agent found {len(scored_documents)} documents. "
        f"Links: {raw_links}"
    )

    return {
        "fetched_documents": scored_documents,
        "classified_links": classified_links,
        "raw_links": raw_links,
        "skip_document_pipeline": False,
        "current_step": "research_complete",
    }
