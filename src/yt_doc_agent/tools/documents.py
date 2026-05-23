"""
Document Fetching Utilities — extracts text from PDFs, webpages, GitHub READMEs/files, Google Drive, Notion, and referenced YouTube videos.
"""

import io
import os
import re
import pickle
import requests
from bs4 import BeautifulSoup
from typing import Optional
from loguru import logger
from yt_doc_agent.core.config import (
    NOTION_TOKEN,
    GITHUB_TOKEN,
    GOOGLE_DRIVE_CREDENTIALS,
    GOOGLE_DRIVE_TOKEN_PATH,
    REQUEST_TIMEOUT,
)
from yt_doc_agent.tools.youtube import extract_video_id, get_transcript
from yt_doc_agent.core.exceptions import DocumentFetchError

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; YTDocAgent/1.0; +https://github.com/GoogleDeepMind)"
}


# ── PDF Fetcher ─────────────────────────────────────────────────────────────

def fetch_pdf(url: str) -> str:
    """
    Download a PDF file from a URL and extract its text using PyMuPDF (fitz).
    """
    logger.info(f"Fetching PDF document from: {url}")
    try:
        import fitz  # PyMuPDF
        
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        
        # Open the PDF directly from the downloaded bytes
        doc = fitz.open(stream=io.BytesIO(resp.content), filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            pages.append(page.get_text())
            
        text = "\n\n".join(pages)
        logger.debug(f"Extracted {len(text)} characters from {len(doc)} PDF pages.")
        return text
        
    except ImportError as e:
        logger.error("PyMuPDF (fitz) is not installed.")
        raise DocumentFetchError("PyMuPDF is required to parse PDF files.") from e
    except Exception as e:
        logger.error(f"PDF extraction failed for '{url}': {e}")
        raise DocumentFetchError(f"PDF extraction failed: {e}") from e


# ── Webpage Fetcher ─────────────────────────────────────────────────────────

def fetch_webpage(url: str) -> str:
    """
    Fetch a standard HTML webpage and extract structured, clean main body text.
    """
    logger.info(f"Fetching webpage from: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Remove navigation, headers, footers, scripts, styles, and other metadata noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
            tag.decompose()
            
        # Get plain text
        text = soup.get_text(separator="\n", strip=True)
        
        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        logger.debug(f"Extracted {len(text)} characters of text from webpage.")
        return text
        
    except Exception as e:
        logger.error(f"Webpage fetch failed for '{url}': {e}")
        raise DocumentFetchError(f"Webpage fetch failed: {e}") from e


# ── GitHub Fetcher ──────────────────────────────────────────────────────────

def fetch_github(url: str) -> str:
    """
    Fetch content from a GitHub repository or file URL.
    - If repo root: attempts to fetch branch README (main or master).
    - If blob file: fetches raw file content.
    - If raw URL or gist: retrieves content directly.
    """
    logger.info(f"Fetching GitHub document from: {url}")
    
    # Prepare authenticated headers if GITHUB_TOKEN is configured
    headers = {**HEADERS}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
        logger.debug("Using GITHUB_TOKEN for authenticated rate limits.")
        
    try:
        # 1. Handle repo roots (e.g. https://github.com/username/repo)
        # We strip trailing slashes, split, and try to grab raw READMEs
        clean_url = url.rstrip("/")
        if "github.com" in clean_url and "/blob/" not in clean_url and "gist.github.com" not in clean_url:
            parts = clean_url.split("/")
            if len(parts) >= 5:
                owner = parts[3]
                repo = parts[4]
                logger.debug(f"Identified GitHub repository root: {owner}/{repo}")
                
                # Attempt to retrieve README on standard branches
                for branch in ["main", "master"]:
                    raw_readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
                    try:
                        resp = requests.get(raw_readme_url, headers=headers, timeout=REQUEST_TIMEOUT)
                        if resp.status_code == 200:
                            logger.info(f"Successfully fetched README.md from branch '{branch}'")
                            return resp.text
                    except Exception as readme_err:
                        logger.debug(f"Failed to fetch README.md on branch '{branch}': {readme_err}")
                        continue
                        
        # 2. Convert standard blob file URLs to raw user content URLs
        if "github.com" in url and "/blob/" in url:
            raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            logger.debug(f"Converting blob URL to raw URL: {raw_url}")
            resp = requests.get(raw_url, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.text
            
        # 3. If it's already a raw user content file or gist, fetch directly
        if "raw.githubusercontent.com" in url or "gist.githubusercontent.com" in url:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.text
            
        # Fallback to general webpage extraction
        logger.debug("Falling back to standard webpage extraction for GitHub URL.")
        return fetch_webpage(url)
        
    except Exception as e:
        logger.error(f"GitHub fetch failed for '{url}': {e}")
        raise DocumentFetchError(f"GitHub fetch failed: {e}") from e


# ── Google Drive Fetcher ────────────────────────────────────────────────────

def fetch_gdrive(url: str) -> str:
    """
    Fetch content from a Google Drive file, Docs document, Sheets spreadsheet, or Slides presentation.
    Requires OAuth setup with credentials stored in data/credentials/credentials.json.
    """
    logger.info(f"Fetching Google Drive document from: {url}")
    try:
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        
        SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
        
        if not os.path.exists(GOOGLE_DRIVE_CREDENTIALS):
            raise DocumentFetchError(
                f"Google Drive credentials file not found at: {GOOGLE_DRIVE_CREDENTIALS}. "
                "Ensure you downloaded your OAuth desktop client credentials to this location."
            )
            
        creds = None
        # Load existing refresh token cache
        if os.path.exists(GOOGLE_DRIVE_TOKEN_PATH):
            with open(GOOGLE_DRIVE_TOKEN_PATH, "rb") as token_file:
                creds = pickle.load(token_file)
                
        # Authenticate / Refresh credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired Google Drive credentials...")
                creds.refresh(Request())
            else:
                logger.info("Initializing first-time Google Drive OAuth flow...")
                os.makedirs(os.path.dirname(GOOGLE_DRIVE_TOKEN_PATH), exist_ok=True)
                flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_DRIVE_CREDENTIALS, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(GOOGLE_DRIVE_TOKEN_PATH, "wb") as token_file:
                pickle.dump(creds, token_file)
                
        # Build the Drive client
        service = build("drive", "v3", credentials=creds)
        
        # Extract file ID from URL
        file_id_match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
        if not file_id_match:
            # Check for other formats (like open?id=...)
            file_id_match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
            
        if not file_id_match:
            raise DocumentFetchError(f"Could not extract Google Drive file ID from URL: {url}")
            
        file_id = file_id_match.group(1)
        logger.debug(f"Extracted Google Drive File ID: {file_id}")
        
        # First, try to export as plain text (works for Google Docs, Sheets, and Slides)
        try:
            logger.debug("Attempting to export document as plain text...")
            content = service.files().export(fileId=file_id, mimeType="text/plain").execute()
            return content.decode("utf-8")
        except Exception as export_err:
            logger.debug(f"Google Docs export failed: {export_err}. Trying direct media download...")
            
            # If export failed, download raw binary (for PDFs, text files uploaded to Drive)
            try:
                media_request = service.files().get_media(fileId=file_id)
                file_metadata = service.files().get(fileId=file_id).execute()
                mime_type = file_metadata.get("mimeType", "")
                
                content_bytes = media_request.execute()
                
                # If downloaded file is PDF, parse it with PyMuPDF
                if b"%PDF" in content_bytes[:10] or "pdf" in mime_type.lower():
                    logger.debug("Downloaded direct binary represents a PDF. Parsing with PyMuPDF...")
                    import fitz
                    doc = fitz.open(stream=io.BytesIO(content_bytes), filetype="pdf")
                    return "\n\n".join(page.get_text() for page in doc)
                    
                return content_bytes.decode("utf-8", errors="replace")
            except Exception as download_err:
                raise DocumentFetchError(f"Direct media download failed: {download_err}") from download_err
                
    except Exception as e:
        logger.error(f"Google Drive fetching failed for '{url}': {e}")
        raise DocumentFetchError(f"Google Drive fetching failed: {e}") from e


# ── Notion Fetcher ──────────────────────────────────────────────────────────

def fetch_notion(url: str) -> str:
    """
    Fetch a Notion page's block content recursively.
    Requires NOTION_TOKEN in .env.
    """
    logger.info(f"Fetching Notion page from: {url}")
    if not NOTION_TOKEN:
        raise DocumentFetchError("NOTION_TOKEN is not configured in .env. Cannot fetch Notion documents.")
        
    try:
        from notion_client import Client
        
        client = Client(auth=NOTION_TOKEN)
        
        # Extract page ID: 32 hex chars, hyphenated or flat
        # URL format usually is: https://www.notion.so/workspace/Page-Title-page_id
        flat_url = url.replace("-", "").split("?")[0]
        page_id_match = re.search(r"([a-f0-9]{32})", flat_url)
        
        if not page_id_match:
            raise DocumentFetchError(f"Could not extract Notion 32-character Page ID from: {url}")
            
        page_id = page_id_match.group(1)
        logger.debug(f"Extracted Notion Page ID: {page_id}")
        
        # Recursive function to fetch and format block texts
        def get_block_text(block_id: str, depth: int = 0) -> str:
            blocks = client.blocks.children.list(block_id=block_id)
            lines = []
            for block in blocks.get("results", []):
                block_type = block.get("type", "")
                # Get rich text block fields depending on type
                block_data = block.get(block_type, {})
                rich_text = block_data.get("rich_text", [])
                
                plain_text = "".join([rt.get("plain_text", "") for rt in rich_text])
                
                if plain_text:
                    indent = "  " * depth
                    lines.append(f"{indent}{plain_text}")
                    
                # Fetch children if nested (e.g. toggles, lists)
                if block.get("has_children"):
                    try:
                        child_text = get_block_text(block["id"], depth + 1)
                        if child_text:
                            lines.append(child_text)
                    except Exception as child_err:
                        logger.warning(f"Failed to fetch children blocks for block ID '{block['id']}': {child_err}")
                        
            return "\n".join(lines)
            
        return get_block_text(page_id)
        
    except Exception as e:
        logger.error(f"Notion fetching failed for '{url}': {e}")
        raise DocumentFetchError(f"Notion fetch failed: {e}") from e


# ── Referenced YouTube Video Fetcher ────────────────────────────────────────

def fetch_youtube_transcript(url: str) -> str:
    """
    Fetch the plain text transcript of a referenced YouTube video in the description.
    """
    logger.info(f"Fetching referenced YouTube video transcript from: {url}")
    video_id = extract_video_id(url)
    if not video_id:
        raise DocumentFetchError(f"Cannot extract video ID from referenced URL: {url}")
        
    try:
        transcript_data, _ = get_transcript(video_id)
        full_text = " ".join(item["text"] for item in transcript_data)
        logger.debug(f"Fetched {len(full_text)} characters of transcript from video '{video_id}'")
        return full_text
    except Exception as e:
        logger.error(f"Failed to fetch transcript for referenced video '{video_id}': {e}")
        raise DocumentFetchError(f"YouTube referenced transcript fetch failed: {e}") from e
