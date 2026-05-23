"""
LangGraph Orchestration — builds the CompiledGraph StateGraph wiring all nodes and edges.
"""

from loguru import logger
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledGraph
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
    description_parser,
    document_fetcher,
    relevance_judge,
    chapter_architect,
    section_writer,
    assembler,
    cache_writer,
)


def map_chapters(state: GraphState):
    """Map over chapters to spawn parallel section writer workers."""
    chapters = state.get("chapters", [])
    if not chapters:
        # If no chapters for some reason, skip to assembler
        return "assembler"
        
    return [
        Send(
            "section_writer",
            {
                "chapter": ch,
                "video_title": state.get("video_title", ""),
                "fetched_documents": state.get("fetched_documents", [])
            }
        )
        for ch in chapters
    ]


def build_graph() -> CompiledGraph:
    """
    Build and compile the multi-agent StateGraph.
    
    Flow:
      1.  cache_check: HIT -> END, MISS -> url_resolver
      2.  url_resolver: PLAYLIST -> playlist_handler, SINGLE -> ingestion
      3.  playlist_handler -> ingestion (always)
      4.  ingestion -> transcript -> language -> description_parser
      5.  description_parser: HAS_LINKS -> document_fetcher, NO_LINKS -> chapter_architect
      6.  document_fetcher -> relevance_judge -> chapter_architect
      7.  chapter_architect --(map_chapters via Send)--> section_writer (parallel workers)
      8.  section_writer -> assembler -> cache_writer -> END
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
    workflow.add_node("description_parser", description_parser.run)
    workflow.add_node("document_fetcher", document_fetcher.run)
    workflow.add_node("relevance_judge", relevance_judge.run)
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
        lambda s: "end" if s.cache_hit else "url_resolver",
        {
            "end": END,
            "url_resolver": "url_resolver"
        }
    )

    # 2. url_resolver -> playlist_handler if playlist URL, otherwise ingestion
    workflow.add_conditional_edges(
        "url_resolver",
        lambda s: "playlist_handler" if s.is_playlist else "ingestion",
        {
            "playlist_handler": "playlist_handler",
            "ingestion": "ingestion"
        }
    )

    # 3. playlist_handler always advances to ingestion
    workflow.add_edge("playlist_handler", "ingestion")

    # 4. Ingestion sequence (linear flow)
    workflow.add_edge("ingestion", "transcript")
    workflow.add_edge("transcript", "language")
    workflow.add_edge("language", "description_parser")

    # 5. description_parser -> skipped document fetcher if no docs, otherwise to fetcher
    workflow.add_conditional_edges(
        "description_parser",
        lambda s: "chapter_architect" if s.skip_document_pipeline else "document_fetcher",
        {
            "document_fetcher": "document_fetcher",
            "chapter_architect": "chapter_architect"
        }
    )

    # 6. Document pipeline links back to chapter architect
    workflow.add_edge("document_fetcher", "relevance_judge")
    workflow.add_edge("relevance_judge", "chapter_architect")

    # 7. Chapter parallel execution (Map-Reduce)
    workflow.add_conditional_edges(
        "chapter_architect",
        map_chapters,
        ["section_writer", "assembler"]
    )
    workflow.add_edge("section_writer", "assembler")
    workflow.add_edge("assembler", "cache_writer")
    workflow.add_edge("cache_writer", END)

    logger.info("Compiling StateGraph with checkpointer...")
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
