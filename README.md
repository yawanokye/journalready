# V-Professor Supervisory Review 2.5.0

V-Professor provides degree-calibrated supervisory review and external assessment for Bachelor’s, Non-Research Master’s, Research Master’s/MPhil, Professional Doctorate and PhD work.

## Current-submission-only review

Every uploaded work is treated as evidence for that review job only. A thesis, dissertation, chapter or benchmark used to test the system is an example, not a reusable model for later submissions.

V-Professor therefore:

- builds the study context afresh from the current title, purpose, objectives, questions, scope and submitted chapters;
- does not retain names, institutions, locations, constructs, sectors, examples or detected weaknesses as rules for another job;
- keeps earlier chapters only when they belong to the same submission and are supplied for alignment;
- removes sample, benchmark, learned-rule and prior-submission fields before provider calls and before the final finding ledger;
- applies only generic academic, methodological, statistical, language and citation standards across jobs.

## Natural and reconciled comments

Native Word comments and inline annotations use connected supervisory prose. They do not expose mechanical labels such as `Issue`, `Problem identified`, `Action required` or `Verification`.

Related concerns with one root cause are consolidated before numbering. Findings attached to the same exact paragraph share one numbered comment box. Every released finding number must appear in the annotated output and in the appended correction register.

Comments already present in an uploaded Word document are retained but labelled as previous source-document comments so that they are not mistaken for the current V-Professor review.

## Accuracy controls in 2.5.0

- Reads the complete section before declaring content missing.
- Preserves verified section-contract findings while suppressing heuristic false positives.
- Distinguishes present-but-weak content from absent content.
- Does not require hypotheses unless the programme contract or confirmed methodology requires them.
- Detects research design and submission stage before applying methodology or results checks.
- Consolidates repeated background, problem-gap, construct-definition, significance, framework and regression-protocol findings.
- Generates study-specific actions from the current submission without hardcoded topic, institution or location examples.
- Separates current findings from older comments embedded in the source document.

## Provider selection and cost control

Use the same provider settings on the web service and worker.

OpenAI:

```env
VPROF_PRIMARY_PROVIDER=openai
VPROF_ENABLE_OPENAI=true
VPROF_ENABLE_DEEPSEEK=false
OPENAI_API_KEY=your-key
VPROF_FALLBACK_PROVIDER=none
VPROF_PROVIDER_FAILOVER=false
```

DeepSeek Pro route:

```env
VPROF_PRIMARY_PROVIDER=deepseek
VPROF_ENABLE_DEEPSEEK=true
VPROF_ENABLE_OPENAI=false
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_REVIEW_MODEL=deepseek-v4-pro
DEEPSEEK_ADVANCED_MODEL=deepseek-v4-pro
DEEPSEEK_QUALITY_MODEL=deepseek-v4-pro
DEEPSEEK_FAST_MODEL=deepseek-v4-flash
DEEPSEEK_PRIMARY_THINKING_ENABLED=false
DEEPSEEK_AUDIT_THINKING_ENABLED=true
DEEPSEEK_TRUNCATION_RECOVERY=true
DEEPSEEK_COVERAGE_UNITS_PER_REQUEST=1
DEEPSEEK_COVERAGE_HIGH_RISK_UNITS_PER_REQUEST=1
VPROF_FALLBACK_PROVIDER=none
VPROF_PROVIDER_FAILOVER=false
```

## Deployment

Web service:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Background worker:

```bash
python -m app.worker
```

Both services must use the same `DATABASE_URL`, provider choice and provider API key. Deploy the package to both services and submit unfinished reviews as new jobs because the 2.5.0 checkpoint identifiers differ from earlier releases. See `DEPLOYMENT.md` and `.env.example`.
