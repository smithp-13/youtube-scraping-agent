"""
Pipeline Runner — high-level runner that compiles and executes the LangGraph workflow.
"""

from typing import Dict, Any, Optional
from loguru import logger
from yt_doc_agent.graph.builder import build_graph
from yt_doc_agent.core.state import GraphState
import yt_doc_agent.core.config as config


def run_pipeline(url: str, settings_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Build, compile, and execute the full LangGraph state machine pipeline.
    
    Args:
        url: The input YouTube video or playlist URL.
        settings_overrides: A dictionary containing overrides for global config settings (e.g. model, outputs dir).
        
    Returns:
        The final state of the pipeline as a dictionary.
    """
    logger.info("Starting execution of YouTube Doc Agent pipeline...")
    
    # 1. Apply overrides to global configuration if specified
    if settings_overrides:
        logger.info(f"Applying settings overrides: {settings_overrides}")
        for key, value in settings_overrides.items():
            if hasattr(config, key) and value is not None:
                old_val = getattr(config, key)
                setattr(config, key, value)
                logger.debug(f"Config override: config.{key} = {value} (was {old_val})")

    # 2. Build and compile our workflow state machine
    graph = build_graph()
    
    # 3. Instantiate the initial shared state
    logger.info(f"Instantiating pipeline state for url: {url}")
    initial_state = GraphState(input_url=url)
    
    # 4. Execute the graph workflow
    try:
        logger.info("Invoking LangGraph StateGraph...")
        thread_config = {"configurable": {"thread_id": "session_1"}}
        final_state = graph.invoke(initial_state, config=thread_config)
        logger.info("Pipeline execution completed successfully.")
        
        # Convert state object to dict
        return final_state
        
    except Exception as e:
        logger.error(f"Pipeline execution encountered an unhandled exception: {e}")
        raise
