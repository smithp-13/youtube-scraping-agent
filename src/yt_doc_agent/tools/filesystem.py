"""
Filesystem Utility Functions — manages file saving, sanitization, and output deduplication.
"""

import os
import re
from typing import Optional
from loguru import logger
from yt_doc_agent.core import config


def sanitize_filename(title: str, max_length: int = 100) -> str:
    """
    Sanitize a string to be safe for use as a filename across Windows, macOS, and Linux.
    Replaces spaces with underscores and strips invalid characters.
    """
    # Strip leading/trailing spaces
    cleaned = title.strip()
    
    # Replace characters that are invalid in Windows/Linux/macOS filenames with empty string
    # Invalid: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/*?:"<>|]', "", cleaned)
    
    # Replace whitespace and tabs with single underscores
    cleaned = re.sub(r'\s+', "_", cleaned)
    
    # Strip any consecutive underscores
    cleaned = re.sub(r'_+', "_", cleaned)
    
    # Limit length
    if len(cleaned) > max_length:
        # Avoid splitting extension if any, but this is usually just the title
        cleaned = cleaned[:max_length].rstrip("_")
        
    return cleaned if cleaned else "untitled_document"


def write_markdown(content: str, video_title: str, output_dir: Optional[str] = None) -> str:
    """
    Write generated markdown content to a safe file path.
    Handles filename sanitization and naming collisions (appends _v2, _v3, etc.).

    Returns:
        The absolute path to the written file.
    """
    # Resolved at call time so CLI overrides (--output) are honoured
    output_dir = output_dir or config.OUTPUTS_DIR

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Sanitize title to make base filename
    base_name = sanitize_filename(video_title)
    filename = f"{base_name}.md"
    file_path = os.path.join(output_dir, filename)
    
    # Naming collision logic (deduplication)
    counter = 1
    while os.path.exists(file_path):
        counter += 1
        filename = f"{base_name}_v{counter}.md"
        file_path = os.path.join(output_dir, filename)
        
    try:
        logger.info(f"Writing Markdown output to file: {file_path}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        abs_path = os.path.abspath(file_path)
        logger.info(f"Markdown file successfully written to: {abs_path}")
        return abs_path
        
    except OSError as e:
        logger.error(f"Failed to write Markdown file to '{file_path}': {e}")
        raise
