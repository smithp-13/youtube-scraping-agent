"""
Agent Node 6: Language Detection and Translation.
"""

from loguru import logger
from rich.console import Console
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
from yt_doc_agent.core.state import GraphState

console = Console()
CHUNK_SIZE = 4500  # GoogleTranslator character limit per request


def _translate_in_chunks(text: str, source_lang: str) -> str:
    """Translate long text in chunks to prevent API character limits."""
    words = text.split()
    chunks = []
    current_chunk = []
    current_len = 0

    for word in words:
        current_len += len(word) + 1
        if current_len > CHUNK_SIZE:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_len = len(word)
        else:
            current_chunk.append(word)
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    logger.debug(f"Splitting translation into {len(chunks)} chunks.")
    translator = GoogleTranslator(source=source_lang, target="en")
    translated_chunks = []
    
    for i, chunk in enumerate(chunks):
        try:
            translated_chunks.append(translator.translate(chunk))
            console.print(f"[dim]  Translating chunk {i+1}/{len(chunks)}...[/dim]")
        except Exception as e:
            logger.warning(f"Translation failed for chunk {i+1}: {e}. Retaining original text.")
            console.print(f"[yellow]⚠ Translation chunk {i+1} failed — using original[/yellow]")
            translated_chunks.append(chunk)

    return " ".join(translated_chunks)


def run(state: GraphState) -> dict:
    """Detect language of transcript; translate to English if needed."""
    console.print("\n[bold cyan]▶ Step 6/13: Language Detection[/bold cyan]")
    logger.info("Running Agent: Language Detection")

    transcript = state.get("cleaned_transcript", "")
    if not transcript:
        logger.info("Empty transcript. Skipping translation/detection.")
        return {
            "working_transcript": "",
            "detected_language": "en",
            "current_step": "language_done",
        }

    # 1. Use Whisper-detected language if already set
    detected = state.get("detected_language", "")
    
    # 2. Otherwise detect using langdetect on the first 1000 characters
    if not detected or detected == "en":
        try:
            detected = detect(transcript[:1000])
        except LangDetectException as e:
            logger.warning(f"langdetect failed: {e}. Defaulting to 'en'.")
            detected = "en"

    console.print(f"[green]✓ Spoken language detected: {detected.upper()}[/green]")
    logger.info(f"Detected spoken language: {detected}")

    if detected == "en":
        return {
            "detected_language": "en",
            "working_transcript": transcript,
            "current_step": "language_done",
        }

    # Non-English transcript: translate to English
    console.print(f"[yellow]Translating transcript from '{detected}' to English...[/yellow]")
    logger.info(f"Translating non-English transcript ({detected}) to English.")
    
    translated = _translate_in_chunks(transcript, detected)
    console.print("[green]✓ Transcript translation complete[/green]")
    
    return {
        "detected_language": detected,
        "working_transcript": translated,
        "current_step": "language_done",
    }
