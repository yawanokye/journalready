import importlib

import pytest
from docx import Document
from pydantic import ValidationError


def test_developer_login_schema_requires_exactly_six_digits():
    from app.developer_access import DeveloperLoginRequest

    payload = DeveloperLoginRequest(email="developer@example.com", access_code="482731")
    assert payload.access_code == "482731"

    for invalid in ["12345", "1234567", "ABC123", "12 345"]:
        with pytest.raises(ValidationError):
            DeveloperLoginRequest(email="developer@example.com", access_code=invalid)


def test_article_ideas_plan_includes_one_docx_export():
    from app.payments.entitlements import get_plan, quota_payload

    plan = get_plan("article_ideas")
    quotas = quota_payload("article_ideas")
    assert plan["exports"] == 1
    assert quotas["exports_total"] == 1
    assert "DOCX export" in plan["description"]


def test_new_article_ideas_purchase_receives_export_entitlement(tmp_path, monkeypatch):
    database = tmp_path / "article-ideas-payment.db"
    monkeypatch.setenv("ARTICLEREADY_SQLITE_DB_PATH", str(database))
    from app.payments import store

    importlib.reload(store)
    reference = store.make_provider_reference("stripe")
    purchase = store.create_pending_purchase(
        user_email="author@example.com",
        work_id="topic-portfolio",
        module_key="topic_ideas",
        plan_key="article_ideas",
        amount=2.99,
        currency="USD",
        display_amount=2.99,
        display_currency="USD",
        payment_provider="stripe",
        provider_reference=reference,
    )
    assert purchase["exports_total"] == 1


def test_topic_ideas_export_produces_readable_docx():
    from app.article_ideas_export import export_article_ideas_docx

    stream, filename = export_article_ideas_docx(
        {
            "research_area": "Digital procurement and public expenditure",
            "source_mode": "Develop as a new independent article",
            "article_type": "Conceptual article",
            "target_journal": "Public Management Review",
            "context": "African public sectors",
            "portfolio_note": "Develop the strongest idea first.",
            "ideas": [
                {
                    "idea_number": 1,
                    "title": "Digital procurement capability and expenditure discipline",
                    "article_type": "Conceptual article",
                    "research_route": "review_conceptual",
                    "readiness_score": 86,
                    "angle": "Integrates capability and governance mechanisms.",
                    "gap": "Existing explanations remain fragmented.",
                    "objective": "To develop an integrated framework.",
                    "questions_or_hypotheses": ["How do digital capabilities shape expenditure discipline?"],
                    "contribution": "Clarifies the mechanism and boundary conditions.",
                    "method_and_data_route": "Critical literature synthesis.",
                    "journal_fit": "Fits public-management debates.",
                    "suggested_sections": ["Introduction", "Conceptual synthesis", "Propositions", "Conclusion"],
                    "keywords": ["digital procurement", "public expenditure"],
                    "evidence_needed": ["Verified governance literature"],
                    "scope_warning": "Keep one central theoretical mechanism.",
                }
            ],
            "source_records_used": [
                {
                    "authors": ["A. Researcher"],
                    "year": 2025,
                    "title": "Digital procurement and governance",
                    "source": "Public Management Review",
                    "doi": "10.1000/example",
                }
            ],
            "quality_filters": ["Verify every source before use."],
        }
    )

    assert filename.endswith("_article_topic_ideas.docx")
    assert len(stream.getvalue()) > 1500
    document = Document(stream)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Article Topic Ideas" in text
    assert "Digital procurement capability and expenditure discipline" in text
    assert "Relevant scholarly source records retained" in text


def test_citation_density_targets_are_higher_and_article_type_specific():
    from app.article_service import _citation_density_requirements

    standard = _citation_density_requirements({"article_type": "Empirical research article"})
    synthesis = _citation_density_requirements({"article_type": "Systematic review"})
    short = _citation_density_requirements({"article_type": "Short communication"})

    assert standard["citation_occurrences_per_1000_words"] == {"minimum": 10, "target": 14}
    assert synthesis["citation_occurrences_per_1000_words"] == {"minimum": 16, "target": 22}
    assert short["citation_occurrences_per_1000_words"] == {"minimum": 7, "target": 10}


def test_article_source_search_accepts_up_to_eighty_records():
    from app.schemas import ArticleSourceSearchRequest

    payload = ArticleSourceSearchRequest(article_title="A defensible working title", max_results=100)
    assert payload.max_results == 80


def test_humanizer_modes_are_available_in_writer_and_revision_payloads():
    from app.schemas import JournalArticleRequest, ArticleRevisionRequest

    writer = JournalArticleRequest(article_title="A defensible working title", humanizer_mode="deep")
    revision = ArticleRevisionRequest(
        article_title="A defensible working title",
        article_text="A" * 120,
        humanizer_mode="light",
    )
    assert writer.humanizer_mode == "deep"
    assert revision.humanizer_mode == "light"
