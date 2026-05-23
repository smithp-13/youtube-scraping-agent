"""
Language Detection Prompts.
"""

LANGUAGE_DETECTION_PROMPT = """
You are a language detection assistant. Examine the following transcript excerpt and identify the spoken language.

TRANSCRIPT EXCERPT:
{transcript_excerpt}

Return ONLY a JSON object with this exact schema (no preamble, no markdown fences):
{{"language_code": "en", "language_name": "English", "confidence": "high"}}

Use ISO 639-1 two-letter codes.
"""
