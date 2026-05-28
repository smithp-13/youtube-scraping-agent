"""
LangGraph Orchestration — builds the CompiledStateGraph StateGraph wiring all nodes and edges.
"""

from typing import Union
from loguru import logger
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send
from langgraph.checkpoint.memory import MemorySaver
from yt_doc_agent.core.state import GraphState
from yt_doc_agent.agents import (
    cache_check,
    url_resolver,
    playlist_handler,
    ingestion,
    transcript,
    language,
    research_agent,
    chapter_architect,
    section_writer,
    assembler,
    cache_writer,
)


def _route_cache(state: GraphState) -> str:
    """Route after cache_check: short-circuit on HIT."""
    return END if state.get("cache_hit") else "url_resolver"


def _route_url(state: GraphState) -> str:
    """Route after url_resolver: playlist needs selection step."""
    return "playlist_handler" if state.get("is_playlist") else "ingestion"


def map_chapters(state: GraphState) -> list[Send]:
    """
    Map over chapters to spawn parallel section_writer workers.

    Always send a slim dict — not the full GraphState. Only the fields
    section_writer.run() actually needs are included. This keeps memory usage
    proportional to chapter count rather than duplicating the entire state.
    """
    chapters = state.get("chapters", []) or []

    return [
        Send(
            "section_writer",
            {
                "chapter": ch,
                "video_title": state.get("video_title", ""),
                "fetched_documents": state.get("fetched_documents", []),
                "working_transcript": state.get("working_transcript", ""),
            },
        )
        for ch in chapters
    ]


def build_graph() -> CompiledStateGraph:
    """
    Build and compile the multi-agent StateGraph.

    Flow:
      1.  cache_check: HIT -> END, MISS -> url_resolver
      2.  url_resolver: PLAYLIST -> playlist_handler, SINGLE -> ingestion
      3.  playlist_handler -> ingestion (always)
      4.  ingestion -> transcript -> language -> research_agent
      5.  research_agent (ReAct) -> chapter_architect
      6.  chapter_architect --(map_chapters via Send)--> section_writer (parallel workers)
      7.  section_writer -> assembler -> cache_writer -> END
    """
    logger.info("Initializing StateGraph builder...")

    workflow = StateGraph(GraphState)

    # ── Register Agent Nodes ───────────────────────────────────────────────
    workflow.add_node("cache_check", cache_check.run)
    workflow.add_node("url_resolver", url_resolver.run)
    workflow.add_node("playlist_handler", playlist_handler.run)
    workflow.add_node("ingestion", ingestion.run)
    workflow.add_node("transcript", transcript.run)
    workflow.add_node("language", language.run)
    workflow.add_node("research_agent", research_agent.run)
    workflow.add_node("chapter_architect", chapter_architect.run)
    workflow.add_node("section_writer", section_writer.run)
    workflow.add_node("assembler", assembler.run)
    workflow.add_node("cache_writer", cache_writer.run)

    # ── Set Entry Point ────────────────────────────────────────────────────
    workflow.set_entry_point("cache_check")

    # ── Conditional Edges ──────────────────────────────────────────────────

    # 1. cache_check -> END on cache hit, otherwise to url_resolver
    workflow.add_conditional_edges(
        "cache_check",
        _route_cache,
        {
            END: END,
            "url_resolver": "url_resolver",
        },
    )

    # 2. url_resolver -> playlist_handler if playlist URL, otherwise ingestion
    workflow.add_conditional_edges(
        "url_resolver",
        _route_url,
        {
            "playlist_handler": "playlist_handler",
            "ingestion": "ingestion",
        },
    )

    # 3. playlist_handler always advances to ingestion
    workflow.add_edge("playlist_handler", "ingestion")

    # 4. Ingestion sequence (linear flow)
    workflow.add_edge("ingestion", "transcript")
    workflow.add_edge("transcript", "language")
    workflow.add_edge("language", "research_agent")

    # 5. Research agent (ReAct) always flows to chapter architect
    workflow.add_edge("research_agent", "chapter_architect")

    # 6. Chapter parallel execution (Map-Reduce)
    workflow.add_conditional_edges(
        "chapter_architect",
        map_chapters,
        ["section_writer"],
    )

    workflow.add_edge("section_writer", "assembler")
    workflow.add_edge("assembler", "cache_writer")
    workflow.add_edge("cache_writer", END)

    logger.info("Compiling StateGraph with checkpointer...")
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)