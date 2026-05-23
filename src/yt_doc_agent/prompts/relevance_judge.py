"""
Relevance Judge Prompts.
"""

RELEVANCE_JUDGE_PROMPT = """
You are a technical document evaluator.

VIDEO TRANSCRIPT (excerpt):
{transcript_excerpt}

DOCUMENT TITLE: {doc_title}
DOCUMENT TYPE: {doc_type}
DOCUMENT CONTENT (excerpt):
{doc_content}

Score this document on three dimensions from 0.0 to 10.0 with one decimal place:

1. RELEVANCE: How topically related is this document to the video?
   (0 = completely unrelated, 10 = directly about the exact same subject)

2. COMPLETENESS: How much of the video's content does this document cover?
   (0 = covers nothing in the video, 10 = covers everything discussed)

3. ACCURACY: Does the document's information align with and not contradict the video?
   (0 = contradicts the video, 10 = fully consistent and accurate)

Return ONLY a JSON object (no preamble, no markdown fences):
{{
  "relevance_score": 7.5,
  "completeness_score": 6.0,
  "accuracy_score": 8.8,
  "judge_notes": "One paragraph explaining the scores, key alignments, and any discrepancies found."
}}
"""
