"""
LLM Client Factory, retry logic, and JSON parsing helpers.
"""

import json
import time
import re
from typing import Any, Optional
from loguru import logger
from langchain_google_genai import ChatGoogleGenerativeAI
from yt_doc_agent.core.config import (
    GOOGLE_API_KEY,
    DEFAULT_MODEL,
    TEMP_STRUCTURED,
    MAX_RETRY_ATTEMPTS,
    RETRY_WAIT_SECONDS,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
    LANGFUSE_BASE_URL,
)
from yt_doc_agent.core.exceptions import LLMCallError

# Initialize global tracer if Langfuse is configured
_tracer = None
if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
    try:
        from langfuse import Langfuse
        _tracer = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_BASE_URL,
        )
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse tracer in llm.py: {e}")


def get_llm(model: Optional[str] = None, temperature: Optional[float] = None) -> ChatGoogleGenerativeAI:
    """
    Initialize and return a ChatGoogleGenerativeAI instance.
    
    Args:
        model: Gemini model name (default: config.DEFAULT_MODEL)
        temperature: LLM temperature (default: config.TEMP_STRUCTURED)
    """
    model_name = model or DEFAULT_MODEL
    temp = temperature if temperature is not None else TEMP_STRUCTURED

    if not GOOGLE_API_KEY:
        raise LLMCallError("GOOGLE_API_KEY is not set in configuration/environment variables.")

    logger.debug(f"Initializing Gemini model '{model_name}' with temperature {temp}")
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=GOOGLE_API_KEY,
        temperature=temp,
    )


def llm_call_with_retry(
    llm: ChatGoogleGenerativeAI, 
    prompt: str, 
    prompt_obj: Optional[Any] = None,
    max_retries: int = MAX_RETRY_ATTEMPTS
) -> str:
    """
    Invoke the LLM with exponential backoff retry logic.
    
    Args:
        llm: ChatGoogleGenerativeAI instance
        prompt: The input prompt/message string or list of messages
        prompt_obj: The Langfuse prompt object (if any) to link this call to a prompt version
        max_retries: Number of retries on failure (default: config.MAX_RETRY_ATTEMPTS)
    """
    attempt = 0
    wait_time = RETRY_WAIT_SECONDS

    # Create a Langfuse generation if tracer is available
    generation = None
    if _tracer and prompt_obj:
        generation = _tracer.generation(
            name="llm-call",
            input=prompt,
            model=getattr(llm, "model", "unknown"),
            prompt=prompt_obj,
        )

    while attempt <= max_retries:
        try:
            logger.debug(f"Invoking LLM (attempt {attempt + 1}/{max_retries + 1})")
            response = llm.invoke(prompt)
            result = str(response.content)
            if generation:
                generation.end(output=result)
            if _tracer:
                _tracer.flush()
            return result
        except Exception as e:
            attempt += 1
            if attempt > max_retries:
                if generation:
                    generation.end(level="ERROR", status_message=str(e))
                if _tracer:
                    _tracer.flush()
                logger.error(f"LLM call failed after {max_retries} retries: {e}")
                raise LLMCallError(f"LLM call failed after multiple attempts: {e}") from e
            
            logger.warning(f"LLM call failed: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            wait_time *= 2  # Exponential backoff


def parse_llm_json(response_text: str) -> Any:
    """
    Extract and parse JSON from LLM response text, handling markdown code blocks
    and potential trailing/leading whitespace/noise.
    """
    cleaned = response_text.strip()
    
    # Check if wrapped in markdown code blocks: ```json ... ```
    pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(pattern, cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    
    # Try parsing
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Fallback: attempt to find first '{' and last '}' or first '[' and last ']'
        # to deal with conversational clutter
        first_brace = cleaned.find('{')
        last_brace = cleaned.rfind('}')
        
        first_bracket = cleaned.find('[')
        last_bracket = cleaned.rfind(']')
        
        if first_brace != -1 and last_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            try:
                return json.loads(cleaned[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass
        elif first_bracket != -1 and last_bracket != -1:
            try:
                return json.loads(cleaned[first_bracket:last_bracket + 1])
            except json.JSONDecodeError:
                pass
                
        logger.error(f"Failed to parse JSON from LLM response: {e}. Raw response: {response_text}")
        raise ValueError(f"Failed to parse JSON from LLM response: {e}")
