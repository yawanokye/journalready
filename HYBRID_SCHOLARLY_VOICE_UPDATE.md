# ArticleReady AI 2.3.0: Hybrid Scholarly Voice Update

## Routing

- GPT-5.5: substantive scholarly drafting, conceptual writing and manuscript revision.
- GPT-5.4: selective preservation-gated final naturalness pass.
- GPT-5.6 Terra: analytical recovery and revision reporting.
- GPT-5.6 Luna: revision planning and reviewer-response support.
- GPT-5.6 Sol: exceptional escalation after smaller recovery batches fail.

## Voice continuity

The revision workflow now creates a global author-voice profile from the original manuscript. Every section batch receives the same profile, the tail of the preceding revised section and the opening of the following original section. Boundary excerpts are used only for continuity and may not be repeated.

## Deployment

Use the model aliases shown in `.env.example` and `render.yaml`, or replace GPT-5.4 and GPT-5.5 with dated snapshots that are available to the deployed OpenAI project. The startup validator accepts approved aliases and snapshots from the GPT-5.4, GPT-5.5 and GPT-5.6 families.
