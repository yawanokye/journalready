# V-Professor v2.5.0 Deployment Guide

## Architecture

Deploy three Render resources:

1. PostgreSQL database: `vprofessor-db`
2. Web service: `vprofessor-web`
3. Background worker: `vprofessor-worker`

The included `render.yaml` creates all three and applies one shared environment definition to the web service and worker.

## Commands

Web service:

```text
Build: python -m pip install -r requirements.txt
Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Background worker:

```text
Build: python -m pip install -r requirements.txt
Start: python -m app.worker
```

## Required secrets

Set the API key for the selected provider in Render. Render generates `SESSION_SECRET` and injects `DATABASE_URL` from the PostgreSQL resource when the Blueprint is used.

For a manual deployment, set:

```env
OPENAI_API_KEY=<secret>
DEEPSEEK_API_KEY=<secret-if-selected>
SESSION_SECRET=<long-random-secret>
DATABASE_URL=<postgresql-connection-string>
```

The web service and worker must use the same `DATABASE_URL`. The same `SESSION_SECRET` may be shared, although only the web service uses browser sessions.

## Shared job and artifact storage

Keep:

```env
VPROF_DB_ARTIFACT_STORAGE=true
VPROF_RUN_JOBS_IN_WEB=false
REVIEW_STORAGE_DIR=/tmp/vprofessor/reviews
REVIEW_STORAGE_FALLBACK_DIR=/tmp/vprofessor/reviews
```

Render services do not share their local file systems. Database-backed artifact storage allows the worker to read uploads queued by the web service and allows the web service to deliver completed reports.

## Worker controls

Recommended starting configuration:

```env
VPROF_WORKER_CONCURRENCY=1
VPROF_WORKER_CLAIM_LIMIT=1
VPROF_WORKER_POLL_SECONDS=8
JOB_HEARTBEAT_SECONDS=30
JOB_LEASE_SECONDS=180
JOB_STALE_AFTER_SECONDS=240
AUTO_RESUME_JOBS=true
MAX_AUTO_RESUMES=2
```

Increase worker concurrency only after monitoring OpenAI rate limits, memory, database load and average job duration.

## Review models

The production route uses:

```env
OPENAI_SECTION_ANALYSIS_MODEL=gpt-5.6-terra
OPENAI_FINAL_SYNTHESIS_MODEL=gpt-5.6-sol
OPENAI_PHD_FINAL_SYNTHESIS_MODEL=gpt-5.6-sol
OPENAI_EXTERNAL_ADJUDICATOR_MODEL=gpt-5.6-sol
```

Terra handles routine extraction and section review. Sol handles bounded final synthesis and external-examiner adjudication.

For DeepSeek as the selected provider, use the same settings on the web service and worker:

```env
VPROF_PRIMARY_PROVIDER=deepseek
VPROF_ENABLE_DEEPSEEK=true
VPROF_ENABLE_OPENAI=false
DEEPSEEK_REVIEW_MODEL=deepseek-v4-pro
DEEPSEEK_QUALITY_MODEL=deepseek-v4-pro
DEEPSEEK_FAST_MODEL=deepseek-v4-flash
DEEPSEEK_PRIMARY_THINKING_ENABLED=false
DEEPSEEK_AUDIT_THINKING_ENABLED=true
DEEPSEEK_TRUNCATION_RECOVERY=true
DEEPSEEK_MAX_OUTPUT_TOKENS=12000
DEEPSEEK_PRIMARY_MAX_OUTPUT_TOKENS=7000
DEEPSEEK_SINGLE_TARGET_RECOVERY_MAX_OUTPUT_TOKENS=4200
DEEPSEEK_COMPACT_ISSUE_LIMIT_PER_TARGET=2
DEEPSEEK_COVERAGE_PARAGRAPHS_PER_UNIT=3
DEEPSEEK_COVERAGE_UNIT_MAX_CHARS=7000
DEEPSEEK_COVERAGE_TABLE_ROWS_PER_UNIT=4
DEEPSEEK_COVERAGE_UNITS_PER_REQUEST=1
DEEPSEEK_COVERAGE_HIGH_RISK_UNITS_PER_REQUEST=1
DEEPSEEK_COVERAGE_REQUEST_MAX_CHARS=9000
```

These provider-specific packet limits are intentionally lower than the general coverage limits. They prevent repeated cut-off JSON responses and are usually cheaper than retrying large failed packets.


## Current-submission isolation

The application rebuilds study context for every job. Example and benchmark documents do not become rules for later submissions. Previous chapters are retained only when they belong to the same submitted work and are intentionally supplied for alignment. Do not add sample documents, sample findings or learned topic terms to environment variables or production prompts.

## Native and inline comments

Recommended settings:

```env
VPROF_NATIVE_COMMENT_STYLE=exact_anchor_grouped
VPROF_EXPORT_ONE_COMMENT_PER_FINDING=false
VPROF_COMMENT_MERGE_BY_SECTION=false
VPROF_MAX_ITEMS_PER_NATIVE_COMMENT=20
VPROF_NATIVE_GROUP_LOCATION_MARKERS=false
VPROF_HUMAN_ROOT_CAUSE_CONSOLIDATION=true
VPROF_EXISTING_COMMENT_POLICY=label
```

`VPROF_EXISTING_COMMENT_POLICY=label` keeps comments already present in the uploaded DOCX but prefixes them as previous source-document comments. They are excluded from current finding reconciliation.

All released findings attached to the same paragraph share one numbered, natural Word comment. Findings attached to different paragraphs remain separate. Visible labels such as Issue, Problem identified, Action required and Verification are not shown. Visible location markers are disabled to protect decimals, citations, equations and DOI strings.

## Section-scoped review

The web interface lets supervisors scan the uploaded chapter, select one or more detected sections and submit only those boundaries for review. Whole-chapter review remains the default. External assessment, full-thesis review and combined-chapter review ignore subsection selection and review the complete submitted scope.

## Degree structure

Bachelor’s, Non-Research Master’s, Research Master’s/MPhil and Professional Doctorate work uses the standard five-chapter research architecture as the default. A PhD may use a variable chapter structure, but the system checks for all prescribed doctoral functions and their integration.

## Administrator bootstrap

Set the following on the web service only when creating the first administrator:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>
ADMIN_EMAIL=<email>
ADMIN_NAME=System Administrator
```

These values do not overwrite an administrator already stored in PostgreSQL during normal startup.

For a controlled one-time reset of the stored administrator credential, set:

```env
VPROF_RESET_ADMIN_PASSWORD_ON_STARTUP=true
```

Redeploy the web service, sign in with `ADMIN_USERNAME` and `ADMIN_PASSWORD`, then immediately set the flag back to `false` and redeploy. The application logs whether the reset was applied but never prints the configured password. A trusted Render Shell may alternatively run `python scripts/reset_admin_password.py`.

## Deployment sequence

1. Stop or allow active legacy jobs to finish.
2. Deploy the database, web service and worker from `render.yaml`.
3. Add `OPENAI_API_KEY`.
4. Confirm both services are Live.
5. Check worker logs for the startup message.
6. Submit a short test chapter.
7. Confirm the status moves from queued to document preparation within one or two polling cycles.
8. Confirm the output contains the annotated DOCX, inline-annotated DOCX and supervisory action report.

Old review checkpoints should not be reused because the v2.5.0 isolation, natural-comment and evidence-ledger identifiers changed.

## Validation

Run locally before deployment:

```bash
PYTHONPATH=. pytest -q
python -m compileall -q app
node --check app/static/app.js
```

## Selecting OpenAI or DeepSeek in Render

Add the provider configuration to both `vprofessor-web` and `vprofessor-worker`, or edit the shared environment anchor in `render.yaml`.

For DeepSeek V4 Pro, set:

```env
VPROF_PRIMARY_PROVIDER=deepseek
VPROF_ENABLE_DEEPSEEK=true
VPROF_ENABLE_OPENAI=false
DEEPSEEK_API_KEY=<secret>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_QUALITY_MODEL=deepseek-v4-pro
DEEPSEEK_ADVANCED_MODEL=deepseek-v4-pro
DEEPSEEK_REVIEW_MODEL=deepseek-v4-pro
DEEPSEEK_FAST_MODEL=deepseek-v4-flash
VPROF_PROVIDER_FAILOVER=false
VPROF_FALLBACK_PROVIDER=none
```

For OpenAI, set `VPROF_PRIMARY_PROVIDER=openai`, enable OpenAI, disable DeepSeek, and provide `OPENAI_API_KEY`. Redeploy the web service and worker after changing providers. Unfinished jobs should be submitted again so the selected provider is recorded in the new job route.
