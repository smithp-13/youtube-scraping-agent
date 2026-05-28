"""
Whisper Utility Functions — downloads audio via yt-dlp and transcribes it locally using faster-whisper.
"""

import os
import subprocess
from typing import List, Dict, Any, Tuple
from loguru import logger
from faster_whisper import WhisperModel
from yt_doc_agent.core.config import (
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DOWNLOAD_TIMEOUT,
    WHISPER_MODEL_DIR,
)


def download_audio(url: str, video_id: str) -> str:
    """
    Download audio from a YouTube video and convert it to a WAV file using yt-dlp.
    Returns the absolute or relative path to the downloaded WAV file.
    
    Raises:
        RuntimeError on download failure.
    """
    cache_dir = "data/cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    output_base = os.path.join(cache_dir, video_id)
    wav_path = f"{output_base}.wav"
    
    if os.path.exists(wav_path):
        logger.info(f"Audio file is already cached: {wav_path}")
        return wav_path
        
    logger.info(f"Downloading audio from YouTube video: {url}")
    
    # Construct yt-dlp command to extract audio as WAV
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--no-playlist",
        "-o", f"{output_base}.%(ext)s",
        url
    ]
    
    logger.debug(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=WHISPER_DOWNLOAD_TIMEOUT
        )
        
        if result.returncode != 0:
            logger.error(f"yt-dlp audio extraction failed: {result.stderr}")
            raise RuntimeError(f"yt-dlp audio download failed: {result.stderr}")
            
        if not os.path.exists(wav_path):
            raise RuntimeError(f"WAV audio file not found after download at expected path: {wav_path}")
            
        logger.info(f"Audio download completed: {wav_path}")
        return wav_path
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"yt-dlp audio download timed out after {WHISPER_DOWNLOAD_TIMEOUT} seconds.")
        raise RuntimeError(f"Audio download timed out: {e}") from e
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        raise RuntimeError(f"Failed to download audio: {e}") from e


def transcribe_audio(wav_path: str, model_size: str = WHISPER_MODEL_SIZE) -> Tuple[List[Dict[str, Any]], str]:
    """
    Transcribe a local WAV file using faster-whisper.
    
    Returns:
        (segments_list, detected_language)
        segments_list: list of {"text": str, "start": float, "duration": float}
        detected_language: ISO 639-1 language code (e.g., 'en')
    """
    model_size_or_path = model_size
    if WHISPER_MODEL_DIR:
        local_path = os.path.join(WHISPER_MODEL_DIR, f"faster-whisper-{model_size}")
        if os.path.exists(local_path):
            model_size_or_path = local_path
            logger.info(f"Loading local Whisper model from: {model_size_or_path}")
        else:
            logger.warning(f"WHISPER_MODEL_DIR is configured, but local path '{local_path}' does not exist. Falling back to default Hugging Face cache.")

    logger.info(f"Loading Whisper model '{model_size_or_path}' on '{WHISPER_DEVICE}' (type: {WHISPER_COMPUTE_TYPE})...")
    try:
        model = WhisperModel(
            model_size_or_path,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE
        )
        
        logger.info(f"Transcribing audio file: {wav_path}")
        segments, info = model.transcribe(wav_path, word_timestamps=False)
        
        formatted_segments = []
        for segment in segments:
            formatted_segments.append({
                "text": segment.text.strip(),
                "start": float(segment.start),
                "duration": float(segment.end - segment.start),
            })
            
        logger.info(f"Transcription complete. Detected language: {info.language} (probability: {info.language_probability:.2f})")
        return formatted_segments, info.language
        
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        raise RuntimeError(f"Whisper transcription failed: {e}") from e


def cleanup_audio(wav_path: str) -> None:
    """Delete the downloaded audio WAV file to save disk space."""
    if os.path.exists(wav_path):
        try:
            os.remove(wav_path)
            logger.info(f"Cleaned up temporary audio file: {wav_path}")
        except OSError as e:
            logger.warning(f"Failed to remove audio file '{wav_path}': {e}")
