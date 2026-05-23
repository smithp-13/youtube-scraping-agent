"""
Section Writer Prompts.
"""

SECTION_WRITER_PROMPT = """
You are writing a section of highly detailed technical developer documentation for a video chapter.

VIDEO TITLE: {video_title}
CHAPTER: {chapter_index}. {chapter_title}
TIMESTAMP RANGE: {start_timestamp} – {end_timestamp}

CHAPTER TRANSCRIPT:
{transcript_segment}

RELATED DOCUMENT CONTEXT (from documents referenced in the video description):
{document_context}

Write comprehensive Markdown documentation for this chapter. Requirements:

STRUCTURE:
- Start with exactly this heading: ## {chapter_index}. {chapter_title} `[{start_timestamp} – {end_timestamp}]`
- Use ### sub-headings for distinct sub-topics within this chapter
- Minimum {min_words} words of technical content

CONTENT RULES:
- Cover every technical concept, tool, API, command, configuration, or pattern mentioned
- Include properly fenced code blocks with correct language tags (```python, ```bash, ```json, etc.)
- Format any sequential steps as numbered lists
- Format reference information (flags, options, parameters) as tables where appropriate
- Use blockquotes with ⚠️ for critical warnings: > ⚠️ **Warning:** ...
- Use blockquotes with 💡 for key insights: > 💡 **Note:** ...
- Where a referenced document provides additional context, cite it: "As detailed in [Document Title](url), ..."

DO NOT:
- Write a summary or TLDR at the end
- Invent APIs, tools, or commands not mentioned in the transcript
- Use generic phrases like "the speaker explains" — write directly as documentation

Output only the raw Markdown. No preamble. No explanation.
"""
