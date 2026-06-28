# Strong Human-Supervised Writing Layer

The strong writing layer adapted from ProjectReady's `ai_service.py` now runs in both the Article Writer and Article Polishing and Revision modules.

## Pipeline

1. Removes stock academic filler and repetitive phrasing.
2. Increases natural sentence-length variation by splitting overloaded sentences at defensible clause boundaries.
3. Varies paragraph openings and transition patterns.
4. Applies meaning-preserving lexical variation.
5. Preserves headings, tables, equations, citations, placeholders, references and confirmed evidence.
6. Uses a deterministic seed so the same manuscript does not change unpredictably on repeated processing.

The layer does not randomise paragraph order, inject unrelated tangents, fabricate citations or introduce deliberate grammatical mistakes.

## Environment variables

```text
ARTICLEREADY_STRONG_HUMANISATION=1
ARTICLEREADY_HUMANISATION_STRENGTH=strong
ARTICLEREADY_HUMANISATION_SEED_SALT=articleready-v1
```

Allowed strengths are `light`, `standard` and `strong`.
