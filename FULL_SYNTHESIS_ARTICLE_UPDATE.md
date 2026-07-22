# Full Synthesis Article Update

ArticleReady AI now treats systematic reviews, scoping reviews, conceptual articles and bibliometric/scientometric articles as full synthesis designs.

## Workflow behaviour

- A new independent empirical article still defaults to Stage 1 and stops at Methods until results or analysis are supplied.
- A new independent systematic, scoping, conceptual or bibliometric article can use **Full synthesis article** immediately.
- These article types do not require new primary data collection.
- Systematic and scoping reviews still require transparent search, screening, appraisal and included-study evidence.
- Bibliometric articles still require a verified publication corpus and software-derived analysis.
- Missing PRISMA counts, corpus statistics, network clusters, thematic maps or other formal outputs are not invented. They appear as red `[Author action: ...]` items in DOCX.

## Article-specific structures

- Systematic/scoping: review methods, evidence-base profile, synthesis, discussion, contribution and research agenda.
- Conceptual: conceptual foundations, construct clarification, critical synthesis, integrative framework, propositions, contribution and research agenda.
- Bibliometric: corpus/search method, performance analysis, science mapping, intellectual structure, thematic evolution, discussion and research agenda.

## Long drafting

In Auto mode, synthesis articles below 9,500 words use one complete drafting pass to reduce web-request timeout risk. Explicit Batch mode remains available, and Auto mode switches to batch at 9,500 words or above.

Environment override:

```text
ARTICLEREADY_SYNTHESIS_BATCH_DRAFT_WORD_THRESHOLD=9500
```
