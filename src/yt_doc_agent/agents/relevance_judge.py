"""
Agent Node 9: Relevance Judge.
"""

from loguru import logger
from rich.console import Console
from yt_doc_agent.core.state import GraphState, DocumentScore
from yt_doc_agent.core.llm import get_llm, llm_call_with_retry, parse_llm_json
from yt_doc_agent.core.config import DEFAULT_MODEL, TEMP_STRUCTURED
from yt_doc_agent.core.prompt_loader import prompt_loader

console = Console()


def run(state: GraphState) -> dict:
    """Evaluate external documents using the default Gemini model and calculate score metrics."""
    console.print("\n[bold cyan]▶ Step 9/13: Relevance Judge[/bold cyan]")
    logger.info("Running Agent: Relevance Judge")

    docs = state.get("fetched_documents", [])
    if not docs:
        console.print("[dim]No documents fetched — skipping scoring pipeline[/dim]")
        logger.info("No documents to judge.")
        return {
            "fetched_documents": [],
            "current_step": "documents_judged",
        }

    # Extract a representative excerpt from the beginning of our clean transcript for evaluation
    transcript_excerpt = state.get("working_transcript", "")[:6000]
    llm = get_llm(model=DEFAULT_MODEL, temperature=TEMP_STRUCTURED)

    scored_docs = []
    for doc in docs:
        if not doc.fetch_success:
            logger.info(f"Skipping failed fetch document: {doc.url}")
            scored_docs.append(doc)
            continue

        console.print(f"[dim]Judging relevance for: {doc.title[:50]} ({doc.doc_type.upper()})[/dim]")
        logger.info(f"Judging document: {doc.title}")
        
        prompt_str, prompt_obj = prompt_loader.get_prompt("relevance_judge", {
            "transcript_excerpt": transcript_excerpt,
            "doc_title": doc.title,
            "doc_type": doc.doc_type,
            "doc_content": doc.content_text[:4000],
        })

        try:
            response = llm_call_with_retry(llm, prompt_str, prompt_obj=prompt_obj)
            scores = parse_llm_json(response)
            
            # Populate scores
            doc.relevance_score = float(scores.get("relevance_score", 0.0))
            doc.completeness_score = float(scores.get("completeness_score", 0.0))
            doc.accuracy_score = float(scores.get("accuracy_score", 0.0))
            doc.judge_notes = scores.get("judge_notes", "")
            
            console.print(
                f"[green]  ✓ Evaluated -> Relevance: {doc.relevance_score} | Completeness: {doc.completeness_score} | Accuracy: {doc.accuracy_score}[/green]"
            )
            logger.info(f"Judged '{doc.title}': R={doc.relevance_score}, C={doc.completeness_score}, A={doc.accuracy_score}")
        except Exception as e:
            logger.error(f"Failed to judge document '{doc.title}': {e}")
            console.print(f"[yellow]  ⚠ Evaluation scoring failed: {e}[/yellow]")
            doc.judge_notes = f"Scoring failed: {e}"

        scored_docs.append(doc)

    console.print(f"[green]✓ Successfully evaluated {len(scored_docs)} documents[/green]")
    return {
        "fetched_documents": scored_docs,
        "current_step": "documents_judged",
    }
