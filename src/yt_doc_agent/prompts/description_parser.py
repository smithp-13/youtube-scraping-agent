"""
Description Parser Prompts.
"""

DESCRIPTION_PARSER_PROMPT = """
You are a URL classifier. Classify each of the following URLs found in a YouTube video description.

Classify each URL into exactly one of these types:
- pdf: Direct link to a .pdf file
- gdrive: Google Drive, Google Docs, Sheets, or Slides link
- notion: Notion.so page link  
- github: GitHub repository, file, raw link, or gist
- youtube: Another YouTube video link
- webpage: Any other website, blog, documentation, or article

URLs to classify:
{url_list}

Return ONLY a JSON array (no preamble, no markdown fences):
[
  {{"url": "https://example.com/slides.pdf", "type": "pdf", "title_guess": "Slides"}},
  {{"url": "https://github.com/user/repo", "type": "github", "title_guess": "Source Code"}}
]
"""
