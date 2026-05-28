"""
LangChain Tool Wrappers for ReAct Agents.

Wraps existing document fetchers (from tools.documents) and adds web search
capabilities as LangChain @tool functions for use by the research_agent and
section_writer agents.

Usage:
    from yt_doc_agent.tools.react_tools import get_research_tools, get_writer_tools
"""

from __future__ import annotations

import os
from typing import List

from langchain_core.tools import tool, BaseTool
from loguru import logger

from yt_doc_agent.tools import documents as doc_tools
from yt_doc_agent.core.config import (
    MAX_DOC_FETCH_CHARS,
    REACT_SEARCH_PROVIDER,
    REACT_ENABLE_WEB_SEARCH,
    GOOGLE_API_KEY,
    GOOGLE_CSE_ID,
    NOTION_TOKEN,
    GOOGLE_DRIVE_CREDENTIALS,
)


# ═══════════════════════════════════════════════════════════════════════
# Search Tools
# ═══════════════════════════════════════════════════════════════════════


def _build_search_tool() -> BaseTool | None:
    """
    Build and return the configured search tool, or None if search is disabled.

    Returns DuckDuckGoSearchRun or GoogleSearchAPIWrapper based on
    REACT_SEARCH_PROVIDER config.
    """
    if not REACT_ENABLE_WEB_SEARCH:
        logger.info("Web search is disabled (REACT_ENABLE_WEB_SEARCH=false)")
        return None

    if REACT_SEARCH_PROVIDER == "google":
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            logger.warning(
                "Google Search selected but GOOGLE_API_KEY or GOOGLE_CSE_ID "
                "is missing. Falling back to DuckDuckGo."
            )
        else:
            try:
                from langchain_google_community import GoogleSearchAPIWrapper

                search_wrapper = GoogleSearchAPIWrapper(
                    google_api_key=GOOGLE_API_KEY,
                    google_cse_id=GOOGLE_CSE_ID,
                    k=5,
                )

                @tool
                def google_web_search(query: str) -> str:
                    """Search the internet using Google Custom Search. Use this to find official documentation, API references, library repos, tutorials, or any technical information mentioned in the video that you need more context on. Input should be a specific search query string."""
                    logger.info(f"[Tool] Google Search: {query}")
                    try:
                        results = search_wrapper.run(query)
                        return str(results)[:MAX_DOC_FETCH_CHARS]
                    except Exception as e:
                        error_msg = f"Google search failed for query '{query}': {e}"
                        logger.error(error_msg)
                        return error_msg

                logger.info("Initialized Google Custom Search tool")
                return google_web_search
            except ImportError:
                logger.warning(
                    "langchain-google-community not installed. "
                    "Falling back to DuckDuckGo."
                )

    # Default: DuckDuckGo
    try:
        from langchain_community.tools import DuckDuckGoSearchRun

        ddg_search = DuckDuckGoSearchRun()

        @tool
        def web_search(query: str) -> str:
            """Search the internet using DuckDuckGo. Use this to find official documentation, API references, library repos, tutorials, or any technical information mentioned in the video that you need more context on. Input should be a specific search query string."""
            logger.info(f"[Tool] DuckDuckGo Search: {query}")
            try:
                results = ddg_search.run(query)
                return str(results)[:MAX_DOC_FETCH_CHARS]
            except Exception as e:
                error_msg = f"Web search failed for query '{query}': {e}"
                logger.error(error_msg)
                return error_msg

        logger.info("Initialized DuckDuckGo search tool")
        return web_search
    except ImportError:
        logger.error(
            "duckduckgo-search is not installed. Web search tool unavailable."
        )
        return None


# ═══════════════════════════════════════════════════════════════════════
# Document Fetcher Tools
# ═══════════════════════════════════════════════════════════════════════


@tool
def fetch_webpage(url: str) -> str:
    """Fetch and extract the main text content from any webpage URL. Use this when you have a direct URL to a documentation page, blog post, article, or any web resource. Returns the extracted plain text content."""
    logger.info(f"[Tool] Fetching webpage: {url}")
    try:
        content = doc_tools.fetch_webpage(url)
        return content[:MAX_DOC_FETCH_CHARS]
    except Exception as e:
        error_msg = f"Failed to fetch webpage '{url}': {e}"
        logger.error(error_msg)
        return error_msg


@tool
def fetch_github_repo(url: str) -> str:
    """Fetch content from a GitHub repository or file URL. For repo roots, fetches the README.md. For blob/file URLs, fetches the raw file content. Use this for any github.com or raw.githubusercontent.com URL."""
    logger.info(f"[Tool] Fetching GitHub content: {url}")
    try:
        content = doc_tools.fetch_github(url)
        return content[:MAX_DOC_FETCH_CHARS]
    except Exception as e:
        error_msg = f"Failed to fetch GitHub content '{url}': {e}"
        logger.error(error_msg)
        return error_msg


@tool
def fetch_pdf_document(url: str) -> str:
    """Download and extract text from a PDF file at the given URL. Use this for any direct link to a .pdf file (slides, papers, documentation PDFs)."""
    logger.info(f"[Tool] Fetching PDF: {url}")
    try:
        content = doc_tools.fetch_pdf(url)
        return content[:MAX_DOC_FETCH_CHARS]
    except Exception as e:
        error_msg = f"Failed to fetch PDF '{url}': {e}"
        logger.error(error_msg)
        return error_msg


@tool
def fetch_youtube_transcript(url: str) -> str:
    """Fetch the plain text transcript of a YouTube video. Use this when a referenced YouTube video URL is found and you need to understand its content."""
    logger.info(f"[Tool] Fetching YouTube transcript: {url}")
    try:
        content = doc_tools.fetch_youtube_transcript(url)
        return content[:MAX_DOC_FETCH_CHARS]
    except Exception as e:
        error_msg = f"Failed to fetch YouTube transcript '{url}': {e}"
        logger.error(error_msg)
        return error_msg


def _build_notion_tool() -> BaseTool | None:
    """Build Notion fetch tool only if NOTION_TOKEN is configured."""
    if not NOTION_TOKEN:
        logger.info("NOTION_TOKEN not set — Notion tool will not be registered")
        return None

    @tool
    def fetch_notion_page(url: str) -> str:
        """Fetch content from a Notion page. Use this for any notion.so URL. Requires NOTION_TOKEN to be configured."""
        logger.info(f"[Tool] Fetching Notion page: {url}")
        try:
            content = doc_tools.fetch_notion(url)
            return content[:MAX_DOC_FETCH_CHARS]
        except Exception as e:
            error_msg = f"Failed to fetch Notion page '{url}': {e}"
            logger.error(error_msg)
            return error_msg

    return fetch_notion_page


def _build_gdrive_tool() -> BaseTool | None:
    """Build Google Drive fetch tool only if credentials are configured."""
    if not os.path.exists(GOOGLE_DRIVE_CREDENTIALS):
        logger.info(
            "Google Drive credentials not found — GDrive tool will not be registered"
        )
        return None

    @tool
    def fetch_gdrive_document(url: str) -> str:
        """Fetch content from a Google Drive file, Google Docs, Sheets, or Slides. Use this for any drive.google.com or docs.google.com URL."""
        logger.info(f"[Tool] Fetching Google Drive document: {url}")
        try:
            content = doc_tools.fetch_gdrive(url)
            return content[:MAX_DOC_FETCH_CHARS]
        except Exception as e:
            error_msg = f"Failed to fetch Google Drive document '{url}': {e}"
            logger.error(error_msg)
            return error_msg

    return fetch_gdrive_document


# ═══════════════════════════════════════════════════════════════════════
# Tool Factory Functions
# ═══════════════════════════════════════════════════════════════════════


def get_research_tools() -> List[BaseTool]:
    """
    Build and return the full set of tools available to the research agent.

    Includes:
      - Web search (DuckDuckGo or Google, based on config)
      - fetch_webpage
      - fetch_github_repo
      - fetch_pdf_document
      - fetch_youtube_transcript
      - fetch_notion_page (if NOTION_TOKEN is set)
      - fetch_gdrive_document (if Google Drive credentials exist)

    Returns:
        List of LangChain BaseTool instances.
    """
    tools: List[BaseTool] = []

    # Search tool
    search_tool = _build_search_tool()
    if search_tool is not None:
        tools.append(search_tool)

    # Core document fetchers (always available)
    tools.extend([
        fetch_webpage,
        fetch_github_repo,
        fetch_pdf_document,
        fetch_youtube_transcript,
    ])

    # Conditional tools (credential-gated)
    notion_tool = _build_notion_tool()
    if notion_tool is not None:
        tools.append(notion_tool)

    gdrive_tool = _build_gdrive_tool()
    if gdrive_tool is not None:
        tools.append(gdrive_tool)

    logger.info(
        f"Research agent tools initialized: {[t.name for t in tools]} "
        f"({len(tools)} total)"
    )
    return tools


def get_writer_tools() -> List[BaseTool]:
    """
    Build and return a lighter set of tools for the section writer agent.

    The writer needs quick lookups, not full document fetching pipelines.

    Includes:
      - Web search (DuckDuckGo or Google, based on config)
      - fetch_webpage
      - fetch_github_repo

    Returns:
        List of LangChain BaseTool instances.
    """
    tools: List[BaseTool] = []

    # Search tool
    search_tool = _build_search_tool()
    if search_tool is not None:
        tools.append(search_tool)

    # Lightweight fetchers for quick lookups
    tools.extend([
        fetch_webpage,
        fetch_github_repo,
    ])

    logger.info(
        f"Section writer tools initialized: {[t.name for t in tools]} "
        f"({len(tools)} total)"
    )
    return tools
