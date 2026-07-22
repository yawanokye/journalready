from __future__ import annotations

import zipfile

from app import review_workspace_store as store


def _configure_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "REVIEW_DB_PATH", tmp_path / "review_workspace.db")
    store.init_review_workspace_tables()


def test_review_workspace_import_deduplicate_screen_and_writer_payload(tmp_path, monkeypatch):
    _configure_store(tmp_path, monkeypatch)
    project = store.create_project(
        {
            "title": "Procurement integrity systematic review",
            "article_type": "Systematic review",
            "review_question": "How do digital procurement systems influence public procurement integrity?",
            "eligibility_criteria": "Peer-reviewed studies directly addressing public procurement integrity.",
            "screening_process": "Title and abstract screening followed by full-text assessment.",
            "quality_appraisal": "Methodological credibility and direct relevance were assessed.",
            "synthesis_method": "Thematic synthesis.",
            "software": "ArticleReady Review Evidence Workspace",
        }
    )
    token = project["access_token"]
    run = store.create_search_run(
        project["id"],
        {
            "database_name": "Scopus",
            "platform": "Elsevier",
            "source_route": "database",
            "search_string": 'TITLE-ABS-KEY("public procurement" AND integrity)',
            "search_date": "2026-07-22",
            "reported_result_count": 3,
        },
    )
    ris = b"""TY  - JOUR\nTI  - Digital procurement and integrity\nAU  - Adam, A.\nPY  - 2025\nDO  - 10.1000/example1\nER  -\nTY  - JOUR\nTI  - Digital procurement and integrity\nAU  - Adam, A.\nPY  - 2025\nDO  - https://doi.org/10.1000/example1\nER  -\nTY  - JOUR\nTI  - Professional judgement in public purchasing\nAU  - Doe, J.\nPY  - 2024\nDO  - 10.1000/example2\nER  -\n"""
    result = store.import_records(project["id"], run["id"], "scopus.ris", ris)
    assert result["records_imported"] == 3
    assert result["exact_duplicates"] == 1

    listing = store.list_records(project["id"], limit=20)
    unique = [record for record in listing["records"] if not record["duplicate_of"]]
    assert len(unique) == 2
    first, second = unique
    store.update_record(
        project["id"],
        first["id"],
        {"title_abstract_decision": "include", "full_text_decision": "include"},
    )
    store.update_record(
        project["id"],
        second["id"],
        {"title_abstract_decision": "exclude", "title_abstract_reason": "Wrong conceptual focus"},
    )
    summary = store.calculate_summary(project["id"])
    assert summary["records_identified"] == 3
    assert summary["duplicates_removed"] == 1
    assert summary["records_screened"] == 2
    assert summary["records_excluded"] == 1
    assert summary["final_corpus"] == 1

    payload = store.writer_payload(project["id"])
    assert payload["review_databases"] == "Scopus (Elsevier)"
    assert payload["review_records_identified"] == 3
    assert payload["review_final_corpus_size"] == 1
    assert "TITLE-ABS-KEY" in payload["review_search_strings"]

    document_stream, filename = store.export_protocol_docx(project["id"])
    assert filename.endswith(".docx")
    assert zipfile.is_zipfile(document_stream)
    assert store.get_project(project["id"], token)["summary"]["final_corpus"] == 1


def test_review_workspace_rejects_invalid_token(tmp_path, monkeypatch):
    _configure_store(tmp_path, monkeypatch)
    project = store.create_project({"title": "Test review", "article_type": "Scoping review"})
    try:
        store.verify_project(project["id"], "wrong-token")
        assert False, "Expected invalid token to be rejected"
    except PermissionError:
        pass
