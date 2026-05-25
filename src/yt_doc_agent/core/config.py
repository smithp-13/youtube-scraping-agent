"""
Centralized configuration — loads all settings from .env via python-dotenv.

Usage:
    from yt_doc_agent.core.config import GOOGLE_API_KEY, DEFAULT_MODEL, OUTPUTS_DIR

Pattern:
    from dotenv import load_dotenv
    load_dotenv()  # reads .env file at project root
    VARIABLE = os.getenv("VARIABLE", "default_value")

Rules:
    1. All env vars are read HERE and only here.
    2. Other modules import constants from this module — never call os.getenv().
    3. CLI flags can override module-level vars after import:
           import yt_doc_agent.core.config as config
           config.DEFAULT_MODEL = args.model
"""
import os
from dotenv import load_dotenv

# ── Load .env file ──────────────────────────────────────────────────────
load_dotenv()

# ═══════════════════════════════════════════════════════════════════════
# 1. LLM / AI PROVIDER KEYS
# ═══════════════════════════════════════════════════════════════════════
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ═══════════════════════════════════════════════════════════════════════
# 2. EXTERNAL SERVICE TOKENS
# ═══════════════════════════════════════════════════════════════════════
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# ═══════════════════════════════════════════════════════════════════════
# 3. GOOGLE CLOUD / OAUTH
# ═══════════════════════════════════════════════════════════════════════
GOOGLE_DRIVE_CREDENTIALS = os.getenv("GOOGLE_DRIVE_CREDENTIALS", "data/credentials/credentials.json")
GOOGLE_DRIVE_TOKEN_PATH = os.getenv("GOOGLE_DRIVE_TOKEN_PATH", "data/credentials/token.json")

# ═══════════════════════════════════════════════════════════════════════
# 4. LLM MODEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.5-flash")
FAST_MODEL = os.getenv("FAST_MODEL", "gemini-2.5-flash")
TEMP_STRUCTURED = float(os.getenv("TEMP_STRUCTURED", "0.2"))
TEMP_WRITING = float(os.getenv("TEMP_WRITING", "0.7"))

# ═══════════════════════════════════════════════════════════════════════
# 5. WHISPER / STT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_MODEL_DIR = os.getenv("WHISPER_MODEL_DIR", "").strip()

# ═══════════════════════════════════════════════════════════════════════
# 6. PATHS & STORAGE
# ═══════════════════════════════════════════════════════════════════════
CACHE_FILE = os.getenv("CACHE_FILE", "data/cache/index.json")
OUTPUTS_DIR = os.getenv("OUTPUTS_DIR", "data/outputs")
LOG_DIR = os.getenv("LOG_DIR", "data/logs")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ═══════════════════════════════════════════════════════════════════════
# 7. RATE LIMITS & TUNING CONSTANTS
# ═══════════════════════════════════════════════════════════════════════
MAX_TRANSCRIPT_TOKENS = int(os.getenv("MAX_TRANSCRIPT_TOKENS", "12000"))
MAX_DOC_CONTENT_TOKENS = int(os.getenv("MAX_DOC_CONTENT_TOKENS", "4000"))
MAX_CHAPTERS = int(os.getenv("MAX_CHAPTERS", "20"))
MIN_SECTION_WORDS = int(os.getenv("MIN_SECTION_WORDS", "400"))
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
RETRY_WAIT_SECONDS = int(os.getenv("RETRY_WAIT_SECONDS", "30"))
MAX_DOC_FETCH_CHARS = int(os.getenv("MAX_DOC_FETCH_CHARS", "50000"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", "60"))
WHISPER_DOWNLOAD_TIMEOUT = int(os.getenv("WHISPER_DOWNLOAD_TIMEOUT", "300"))


def validate_config() -> list[str]:
    """
    Validate critical configuration at startup.
    Returns a list of warning/error messages. Empty list = all good.
    """
    issues = []

    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "your_gemini_api_key_here":
        issues.append("[CRITICAL] GOOGLE_API_KEY is not set. Set it in .env or as an environment variable.")

    if NOTION_TOKEN:
        issues.append("[INFO] NOTION_TOKEN is set — Notion document fetching enabled.")
    else:
        issues.append("[INFO] NOTION_TOKEN not set — Notion pages in video descriptions will be skipped.")

    if GITHUB_TOKEN:
        issues.append("[INFO] GITHUB_TOKEN is set — GitHub API rate limit: 5000 req/hr.")
    else:
        issues.append("[WARN] GITHUB_TOKEN not set — GitHub API rate limit: 60 req/hr (may hit limits).")

    if not os.path.exists(GOOGLE_DRIVE_CREDENTIALS):
        issues.append("[INFO] Google Drive credentials not found — Google Drive/Docs fetching disabled.")

    return issues
