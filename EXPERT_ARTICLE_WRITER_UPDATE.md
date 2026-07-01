# Expert Article Writer update

This update strengthens `app/article_service.py` so that ArticleReady AI:

1. writes with the conceptual, methodological and editorial judgement expected of a senior professor in the selected field;
2. removes future-tense constructions from every article stage;
3. converts all author advice, missing information and unresolved actions into `[Author action: ...]` instructions;
4. renders those instructions in red in downloaded DOCX files;
5. keeps substantive article prose black;
6. increases claim-level citation density using verified, directly relevant records; and
7. reports citation occurrences per 1,000 words in the API result.

The output guard also covers lists, tables, Methods readiness checklists, Next Stage notes and reference placeholders.
