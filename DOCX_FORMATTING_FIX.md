# DOCX revision-colour and Markdown-formatting fix

## Revision export colours

- Added or changed manuscript wording remains blue (`#0070C0`).
- Bracketed author-action placeholders, such as `[confirm robustness test]`, are red (`#C00000`).
- Labels such as `Action required:` and `Remaining action:` are red.
- Unchanged manuscript wording remains black.
- Red action formatting overrides blue revision formatting when both apply.

## Word formatting

The Article Writer and Article Polishing/Revision DOCX exporters now convert Markdown emphasis into real Microsoft Word formatting:

- `**bold**` becomes bold text.
- `*italic*` becomes italic text.
- `***bold italic***` becomes bold and italic text.
- Common extra-marker output, such as `**bold***`, is normalised during export.
- Markdown markers no longer remain visible in headings, paragraphs, lists or table cells.

## Files updated

- `app/article_service.py`
- `app/article_revision_service.py`
- `tests/test_article_workflows.py`

## Verification

- All automated tests passed.
- Article Writer and Article Revision DOCX samples were rendered and visually checked.
