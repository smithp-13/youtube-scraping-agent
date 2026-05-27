"""
Quick smoke test — verifies prompt_loader fetches from Langfuse.
Run from project root:  uv run tests/test_prompt_loader.py
Or from tests/:         uv run test_prompt_loader.py
"""
import sys
import os

# Ensure the src package is importable regardless of CWD
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(project_root, "src"))

from yt_doc_agent.core.prompt_loader import prompt_loader

# ── Test data for each prompt ────────────────────────────────────────────
TESTS = {
    "chapter_architect": {
        "video_title": "TEST — Building a RAG Pipeline",
        "duration": "24m 15s",
        "transcript_with_timestamps": "[0:00] hello world\n[0:15] today we build a RAG pipeline",
        "max_chapters": "10",
    },
    "section_writer": {
        "video_title": "TEST — Building a RAG Pipeline",
        "chapter_index": "1",
        "chapter_title": "Environment Setup",
        "start_timestamp": "0:00",
        "end_timestamp": "4:30",
        "transcript_segment": "first install langchain and pinecone",
        "document_context": "No referenced documents.",
        "min_words": "400",
    },
    "description_parser": {
        "url_list": "https://github.com/langchain-ai/langchain\nhttps://docs.pinecone.io",
    },
    "relevance_judge": {
        "transcript_excerpt": "today we build a retrieval augmented generation pipeline",
        "doc_title": "Pinecone Quickstart",
        "doc_type": "webpage",
        "doc_content": "Pinecone is a vector database for ML applications.",
    },
    "language_detection": {
        "transcript_excerpt": "hoy vamos a construir una pipeline de generacion aumentada",
    },
}

# ── Run tests ────────────────────────────────────────────────────────────
print("=" * 70)
print("PROMPT LOADER TEST — LANGFUSE ONLY (no local fallback)")
print("=" * 70)

# Show Langfuse config status
from yt_doc_agent.core.config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL
print(f"\nLangfuse Public Key:  {'SET (' + LANGFUSE_PUBLIC_KEY[:12] + '...)' if LANGFUSE_PUBLIC_KEY else 'NOT SET'}")
print(f"Langfuse Secret Key:  {'SET (' + LANGFUSE_SECRET_KEY[:12] + '...)' if LANGFUSE_SECRET_KEY else 'NOT SET'}")
print(f"Langfuse Base URL:    {LANGFUSE_BASE_URL}")
print()

passed = 0
failed = 0

for name, variables in TESTS.items():
    print(f"{'─' * 70}")
    print(f"Testing: {name}")
    try:
        result, prompt_obj = prompt_loader.get_prompt(name, variables)

        # Check that variables were actually substituted
        has_unresolved = False
        for var_name in variables:
            if "{{" + var_name + "}}" in result:
                has_unresolved = True
                break

        if has_unresolved:
            print(f"  ⚠ WARNING: Unresolved {{{{variable}}}} found in compiled prompt!")
            failed += 1
        else:
            print(f"  ✓ PASS — Fetched from Langfuse")
            print(f"  Preview (first 150 chars):")
            print(f"    {result.strip()[:150]}...")
            passed += 1
    except Exception as e:
        print(f"  ✗ FAIL — {type(e).__name__}: {e}")
        failed += 1

print(f"\n{'=' * 70}")
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
if failed > 0:
    print("\nTips for failures:")
    print("  • Ensure the prompt exists in Langfuse dashboard")
    print("  • Check if 'production' label is set (or version=1 will be tried)")
    print("  • Verify LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY in .env")
print("=" * 70)
