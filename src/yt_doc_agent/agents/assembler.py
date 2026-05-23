"""
Agent Node 12: Document Assembler.
"""

from datetime import datetime, timezone
from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import GraphState
from yt_doc_agent.tools.filesystem import write_markdown
from yt_doc_agent.core.llm import get_llm, llm_call_with_retry
from yt_doc_agent.core.config import DEFAULT_MODEL, TEMP_WRITING

console = Console()


def _format_duration(seconds: int) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _build_toc(chapters: list) -> str:
    """Generate a clean Markdown Table of Contents with valid anchor links."""
    lines = []
    for ch in chapters:
        # Standard github markdown anchor sanitization
        anchor = ch.title.lower().strip()
        anchor = re.sub(r"[^\w\s-]", "", anchor)  # remove non-alphanumeric except dashes/spaces
        anchor = re.sub(r"\s+", "-", anchor)      # spaces to dashes
        anchor = f"{ch.index}-{anchor}"
        
        lines.append(f"- {ch.index}. [{ch.title}](#{anchor}) `[{ch.start_timestamp} – {ch.end_timestamp}]`")
    return "\n".join(lines)


def _build_documents_table(docs: list) -> str:
    """Generate a formatted markdown evaluation table for description-referenced documents."""
    if not docs:
        return "_No external documents fetched/analyzed from description._"
        
    header = "| # | Document | Type | Relevance | Completeness | Accuracy | Notes |\n"
    header += "|---|---|---|---|---|---|---|\n"
    rows = []
    for i, doc in enumerate(docs, 1):
        title_link = f"[{doc.title}]({doc.url})"
        # Slice notes to fit table nicely
        notes = doc.judge_notes[:120] + "..." if len(doc.judge_notes) > 120 else doc.judge_notes
        rows.append(
            f"| {i} | {title_link} | {doc.doc_type.upper()} | "
            f"{doc.relevance_score}/10 | {doc.completeness_score}/10 | "
            f"{doc.accuracy_score}/10 | {notes} |"
        )
    return header + "\n".join(rows)


def _generate_summary(working_transcript: str, video_title: str, llm) -> str:
    """Generate a high-quality developer summary and key technical takeaways."""
    prompt = f"""Write a concise technical summary and key takeaways for the following video.

VIDEO TITLE: {video_title}

TRANSCRIPT EXCERPT:
{working_transcript[:6000]}

Format the output exactly as follows:
### Technical Overview
Write a 2-3 paragraph precise technical summary for developers explaining the key architectures, systems, designs, and tools covered.

### Key Technical Takeaways
Write a bulleted list of 5-8 highly precise technical takeaways (e.g. commands, key parameters, gotchas, configuration steps).

Write in pure Markdown. Avoid corporate fluff, generic text, or summarizing intro/outro conversational bits.
"""
    try:
        logger.info("Generating final technical summary via LLM.")
        return llm_call_with_retry(llm, prompt)
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return f"_Technical summary generation failed: {e}_"


def _generate_cross_references(docs: list, video_title: str, llm) -> str:
    """Generate cross-reference documentation detailing how external docs complement the video."""
    if not docs:
        return "_No referenced documents to cross-reference._"
        
    docs_summary = "\n".join([
        f"- {doc.title} ({doc.doc_type}): Relevance {doc.relevance_score}/10. {doc.judge_notes[:200]}"
        for doc in docs
    ])
    
    prompt = f"""For each of the following documents referenced in the video '{video_title}', write one technical paragraph explaining:
1. What the document contains (based on the evaluation notes)
2. How it directly relates to and complements the video content
3. When a developer should refer to it rather than the video documentation itself

DOCUMENTS:
{docs_summary}

Write in pure Markdown with a ### heading for each document. Be highly technical, concise, and specific.
"""
    try:
        logger.info("Generating external document cross-references via LLM.")
        return llm_call_with_retry(llm, prompt)
    except Exception as e:
        logger.error(f"Cross-reference generation failed: {e}")
        return f"_Cross-reference generation failed: {e}_"


import re  # needed for Toc anchor regex

def run(state: GraphState) -> dict:
    """Compile and write the complete, beautiful markdown documentation file."""
    console.print("\n[bold cyan]▶ Step 12/13: Document Assembler[/bold cyan]")
    logger.info("Running Agent: Document Assembler")

    llm = get_llm(model=DEFAULT_MODEL, temperature=TEMP_WRITING)
    
    # Prepend translation footnote if required
    lang_note = ""
    detected_lang = state.get("detected_language", "")
    if detected_lang and detected_lang != "en":
        lang_note = f" → Translated to English (Original spoken: {detected_lang.upper()})"

    # ── Header Section ────────────────────────────────────────────────────
    header = f"""# {state.get("video_title", "")}

> 📺 **Video Source:** {state.get("video_url", "")}  
> 👤 **Channel:** {state.get("channel_name", "")}  
> ⏱️ **Duration:** {_format_duration(state.get("video_duration_seconds", 0))}  
> 🌐 **Language:** {detected_lang.upper() if detected_lang else "EN"}{lang_note}  
> 📝 **Transcript Source:** {"YouTube Transcript API" if state.get("transcript_source", "") == "youtube_api" else "Whisper Local STT"}  
> 🗂️ **Chapters Source:** {state.get("chapters_source", "").replace("_", " ").title()}  
> ⚙️ **Generated:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}  

---

"""

    # ── Table of Contents ────────────────────────────────────────────────
    toc = f"## Table of Contents\n\n{_build_toc(state.get('chapters', []))}\n\n---\n\n"

    # ── Referenced Documents Evaluation ──────────────────────────────────
    fetched_docs = state.get("fetched_documents", [])
    docs_section = f"## External Reference Documents\n\n{_build_documents_table(fetched_docs)}\n\n---\n\n"

    # ── Technical Chapters Section ───────────────────────────────────────
    sections = sorted(state.get("section_outputs", []), key=lambda s: s.chapter_index)
    sections_md = "\n\n---\n\n".join(s.markdown_content for s in sections)

    # ── Summary & Takeaways ──────────────────────────────────────────────
    console.print("[dim]Generating final technical summary...[/dim]")
    video_title = state.get("video_title", "")
    summary_content = _generate_summary(state.get("working_transcript", ""), video_title, llm)
    summary = f"\n\n---\n\n## Summary & Key Takeaways\n\n{summary_content}"

    # ── Cross References ─────────────────────────────────────────────────
    if fetched_docs:
        console.print("[dim]Generating document cross-references...[/dim]")
        xref_content = _generate_cross_references(fetched_docs, video_title, llm)
        xref = f"\n\n---\n\n## Reference Document Deep-Dive\n\n{xref_content}"
    else:
        xref = ""

    # ── Footer ────────────────────────────────────────────────────────────
    footer = "\n\n---\n\n*Generated by Antigravity's YouTube Documentation Agent · LangGraph StateGraph · Gemini*\n"

    # ── Full Assembly ────────────────────────────────────────────────────
    full_doc = header + toc + docs_section + sections_md + summary + xref + footer

    # Write file out
    try:
        output_path = write_markdown(full_doc, state.get("video_title", ""))
        console.print(f"[green]✓ Professional Documentation generated successfully![/green]")
        console.print(f"[green]  Saved to: [bold]{output_path}[/bold][/green]")
        logger.info(f"Assembled final document: {output_path}")
        
        return {
            "output_file_path": output_path,
            "output_markdown": full_doc,
            "current_step": "assembled",
        }
    except Exception as e:
        logger.error(f"Assembler failed to write file: {e}")
        return {
            "error_messages": [f"Assembler file write failed: {e}"],
            "current_step": "assembly_failed",
        }
