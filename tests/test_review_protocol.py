from app.article_service import draft_journal_article
from app.review_protocol import build_review_protocol_documentation


def test_conceptual_review_protocol_keeps_integrative_positioning_and_separates_metadata_search():
    payload = {
        "article_type": "Conceptual article",
        "include_review_protocol_package": True,
        "review_databases": "Scopus; Web of Science Core Collection",
        "review_search_strings": 'TITLE-ABS-KEY("public procurement" AND ethics)',
        "review_search_date": "2026-07-22",
        "review_date_limits": "2016-2026",
        "review_language_limits": "English",
        "review_document_types": "Peer-reviewed articles and reviews",
        "review_eligibility_criteria": "Directly addresses procurement literacy or ethical procurement behaviour.",
        "review_screening_process": "Two-stage title/abstract and full-text screening with documented exclusion reasons.",
        "review_quality_appraisal": "Conceptual relevance and methodological credibility were critically evaluated.",
        "review_citation_tracking": "Backward and forward citation tracking was completed for included papers.",
        "review_duplicate_removal": "EndNote title-author-year matching followed by manual review.",
        "review_synthesis_method": "Construct decomposition, cross-theoretical comparison and mechanism integration.",
        "review_software": "EndNote 21 and a documented spreadsheet extraction matrix.",
        "review_records_identified": 100,
        "review_duplicates_removed": 20,
        "review_records_screened": 80,
        "review_records_excluded": 50,
        "review_full_text_assessed": 30,
        "review_full_text_excluded": 10,
        "review_citation_tracking_additions": 4,
        "review_final_corpus_size": 24,
        "variables_constructs": "procurement ethics; professional judgement; digital procurement",
    }
    search_result = {
        "query": "public procurement ethics",
        "searched_at": "2026-07-22T08:00:00+00:00",
        "databases": ["Openalex", "Crossref", "Semantic Scholar"],
        "quality_filters": ["deduplicated by DOI/title"],
    }
    text, audit = build_review_protocol_documentation(payload, search_result, [{"title": "A"}] * 12)
    assert "integrative, theory-building conceptual synthesis" in text
    assert "does not by itself establish a formal systematic-review search" in text
    assert "Final conceptual or review corpus | 24" in text
    assert audit["complete"] is True
    assert not audit["flow_warnings"]


def test_review_protocol_flags_inconsistent_counts():
    payload = {
        "article_type": "Systematic review",
        "include_review_protocol_package": True,
        "review_records_identified": 100,
        "review_duplicates_removed": 25,
        "review_records_screened": 90,
        "review_full_text_assessed": 20,
        "review_full_text_excluded": 5,
        "review_final_corpus_size": 12,
    }
    text, audit = build_review_protocol_documentation(payload, {}, [])
    assert audit["flow_warnings"]
    assert "do not equal identified records minus duplicates" in text
    assert "does not equal full texts assessed minus full-text exclusions" in text


def test_article_draft_returns_protocol_package_without_inventing_counts(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = draft_journal_article(
        {
            "article_title": "Procurement literacy and ethical behaviour",
            "article_type": "Conceptual article",
            "source_mode": "Develop as a new independent article",
            "draft_stage": "full_article",
            "include_source_search": False,
            "include_research_resource_search": False,
            "include_review_protocol_package": True,
            "review_databases": "Scopus",
            "review_search_strings": 'TITLE-ABS-KEY("procurement literacy")',
            "review_search_date": "2026-07-22",
        }
    )
    assert result["review_protocol_text"]
    assert result["review_protocol_audit"]["enabled"] is True
    assert "[Author action: Insert the verified count for this stage.]" in result["review_protocol_text"]
    assert "Review Protocol and Evidence Audit" in result["article_text"]
