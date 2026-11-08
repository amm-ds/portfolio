# Summarize

Compress long texts — pasted documents, fetched pages, long answers — into a
short neutral summary with the `summarize_text` tool.

# Rules

- Offer a summary when the user pastes more than a few paragraphs or asks for
  the short version of anything.
- Use `summarize_text`; do not summarize by paraphrasing in your own words
  when the tool is available.
- Keep the summary neutral: no opinions, no added facts, drop the details that
  only matter to a specialist. Preserve decisive events, dates, and actor changes
  even when the extractive tool omits them.
- If the user asks for a specific length, pass it as `max_sentences`.
