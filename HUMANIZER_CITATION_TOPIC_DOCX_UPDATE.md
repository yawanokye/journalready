# ArticleReady AI 1.8.0 update

- Synchronised `app/scholarly_humanizer.py` with the latest ThesisReady/ProjectReady preservation-gated scholarly humanizer.
- Added user-selectable `off`, `light`, `balanced` and `deep` humanizer modes to Article Writer and Article Revision.
- Added one paid DOCX export to the Article Ideas package, including an automatic migration for existing Article Ideas purchases.
- Added `/api/article-ideas/export` and an **Export DOCX** button on the Topic Ideas page.
- Increased citation-density requirements by article type and added section-level citation coverage audits.
- Added citation-density and humanizer reports to writer and revision results.
- Increased manual source-search selection to 80 records and article source context to 100 verified records.
- Repaired the developer-access HTML and JavaScript, and aligned frontend and backend validation to an exact six-digit numeric code.
- Updated browser cache versions and application version to 1.8.0.
- Validation completed with 37 passing automated tests, Python compilation and JavaScript syntax checks.
