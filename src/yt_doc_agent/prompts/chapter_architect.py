"""
Chapter Architect Prompts.
"""

CHAPTER_ARCHITECT_PROMPT = """
You are analyzing the transcript of a technical video to create a chapter structure for developer documentation.

VIDEO TITLE: {video_title}
VIDEO DURATION: {duration}

TRANSCRIPT WITH TIMESTAMPS:
{transcript_with_timestamps}

Create between 4 and {max_chapters} logical chapters based on topic transitions in the transcript.

Rules:
- Chapter titles must be technically descriptive (e.g. "Configuring Webhook Authentication" not "Step 3")
- Estimate timestamps based on where topic shifts occur in the transcript
- Each chapter must cover a distinct technical topic or phase
- Include the relevant portion of the transcript in transcript_segment
- Chapters must be in chronological order

Return ONLY a JSON array (no preamble, no markdown fences):
[
  {{
    "index": 1,
    "title": "Environment Setup and Prerequisites",
    "start_timestamp": "0:00",
    "end_timestamp": "4:30",
    "transcript_segment": "... the relevant transcript lines for this chapter ..."
  }}
]
"""
