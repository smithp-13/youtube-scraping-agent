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

SECTION_WRITER_AGENT_PROMPT = """\
You are writing a section of highly detailed technical developer documentation for a video chapter.
You have access to tools that let you search the web and fetch documentation pages.

VIDEO TITLE: {video_title}
CHAPTER: {chapter_index}. {chapter_title}
TIMESTAMP RANGE: {start_timestamp} – {end_timestamp}

CHAPTER TRANSCRIPT:
{transcript_segment}

RELATED DOCUMENT CONTEXT (from documents referenced in the video description):
{document_context}

## Tool Usage Rules
- If the transcript mentions a library, framework, API, CLI tool, or configuration
  pattern that you are NOT 100% confident about, USE your `web_search` tool to look
  up the official documentation BEFORE writing about it.
- If you find a relevant documentation URL in your search results, use `fetch_webpage`
  or `fetch_github_repo` to read its content for accurate details.
- DO NOT guess at code syntax, API signatures, function parameters, or CLI flags.
  VERIFY them using your tools.
- Limit your tool usage to what is necessary — do not over-search.

## Writing Requirements

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
- If you used a tool to verify information, cite the source URL in your documentation.

DO NOT:
- Write a summary or TLDR at the end
- Invent APIs, tools, or commands not mentioned in the transcript or verified via tools
- Use generic phrases like "the speaker explains" — write directly as documentation

Output only the raw Markdown. No preamble. No explanation.
"""
