# V-Professor 2.5.0 Current-Submission Isolation Update

## Purpose

This release prevents a reviewed thesis, dissertation, chapter or benchmark from becoming a hidden template for later jobs. Example documents are used only to test generic review behaviour. Their names, institutions, locations, constructs, sectors, wording and detected weaknesses are not stored as production rules.

## Main changes

- Added a current-submission-only isolation layer before AI review and before final finding generation.
- Removed explicit sample, benchmark, learned-rule, prior-submission and cross-job context fields.
- Added provider prompt locks prohibiting cross-submission learning and example-term persistence.
- Replaced topic-specific deterministic rules with document-derived setting, population, construct and alignment checks.
- Strengthened whole-section contradiction checks for introductions, organisation sections, framework references and verified missing sections.
- Preserved verified programme section-contract findings while suppressing unverified hypothesis requirements.
- Consolidated duplicate root causes before numbering and export.
- Shortened natural supervisor comments and removed generic filler instructions.
- Labelled comments already present in the uploaded Word document as previous source-document comments.
- Reconciled the current V-Professor finding ledger independently of older comments.

## Deployment

Deploy the complete package to both the web service and background worker. Use the same database and selected provider configuration on both services. Submit unfinished or failed reviews as new jobs so they use the 2.5.0 isolation and checkpoint identifiers.
