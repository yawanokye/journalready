from app.article_ideas_service import generate_article_ideas
from app.article_service import draft_journal_article, export_article_docx


def test_article_ideas_fallback_is_article_focused(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = generate_article_ideas(
        {
            "research_area": "digital procurement and public expenditure",
            "source_mode": "Extract from a completed thesis or dissertation",
            "thesis_title": "Digitalisation, procurement governance and public expenditure",
            "thesis_material": "The study analysed public procurement systems and expenditure outcomes.",
            "context": "African public sectors",
            "article_type": "Empirical research article",
            "variables_or_themes": "e-procurement, procurement expenditure, governance",
            "max_ideas": 4,
            "include_source_search": False,
        }
    )
    assert len(result["ideas"]) == 4
    assert all(idea["objective"].startswith("To ") for idea in result["ideas"])
    assert all("scope_warning" in idea for idea in result["ideas"])


def test_article_draft_and_docx_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = draft_journal_article(
        {
            "article_title": "Digital procurement and expenditure intensity",
            "article_type": "Empirical research article",
            "academic_level": "Research Masters (e.g. MPhil)",
            "include_source_search": False,
            "thesis_source_material": "Study summary",
        }
    )
    assert "# Digital procurement and expenditure intensity" in result["article_text"]
    stream, filename = export_article_docx(result["article_text"], "Digital procurement")
    assert filename.endswith(".docx")
    assert len(stream.getvalue()) > 1000


def test_attached_source_bank_is_used_and_retracted_record_is_excluded(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = draft_journal_article(
        {
            "article_title": "Governance and digital procurement outcomes",
            "article_type": "Empirical research article",
            "include_source_search": False,
            "source_search_terms": "digital procurement governance",
            "source_bank": [
                {
                    "title": "Digital procurement and public-sector governance",
                    "authors": ["A. Researcher"],
                    "year": 2025,
                    "source": "Public Management Review",
                    "doi": "10.1000/example",
                    "abstract": "The study examines digital procurement and governance outcomes.",
                    "apa_hint": "Researcher, A. (2025). Digital procurement and public-sector governance.",
                },
                {
                    "title": "Retracted: Procurement systems and governance",
                    "authors": ["B. Author"],
                    "year": 2022,
                    "is_retracted": True,
                },
            ],
        }
    )
    assert result["attached_source_count"] == 1
    assert result["source_bank_count"] == 1
    assert result["excluded_retracted_count"] == 1
    assert result["source_records_used"][0]["title"] == "Digital procurement and public-sector governance"
    assert "## Source Use Audit" in result["article_text"]
    assert "Retracted: Procurement systems and governance" not in result["article_text"]


def test_article_ideas_list_secondary_data_sources(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = generate_article_ideas(
        {
            "research_area": "public procurement governance and expenditure",
            "source_mode": "Develop from an existing dataset",
            "article_type": "Empirical research article",
            "research_route": "Secondary data or existing dataset",
            "methodology": "cross-country panel data analysis",
            "variables_or_themes": "e-procurement, governance, public expenditure",
            "max_ideas": 3,
            "include_source_search": False,
            "include_research_resource_search": True,
        }
    )
    assert result["research_resources"]["data_sources"]
    assert any(idea["resource_guidance"]["possible_data_sources"] for idea in result["ideas"])


def test_independent_article_defaults_to_phd_and_stops_at_methods(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = draft_journal_article(
        {
            "article_title": "Financial literacy and retirement planning",
            "source_mode": "Develop as a new independent article",
            "draft_stage": "full_article",
            "academic_level": "Research Masters (e.g. MPhil)",
            "research_route": "Primary survey or questionnaire",
            "methodology": "cross-sectional questionnaire survey",
            "variables_constructs": "financial literacy, retirement planning",
            "include_source_search": False,
            "include_research_resource_search": True,
            "include_instrument_draft": True,
        }
    )
    assert result["draft_stage"] == "initial_to_methods"
    assert result["academic_level_used"] == "PhD"
    assert "## 4. Methods" in result["article_text"]
    assert "## 5. Results" not in result["article_text"]
    assert result["instrument_text"]
    assert result["research_resources"]["instrument_sources"]


def test_continuation_stage_requires_previous_or_results(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        draft_journal_article(
            {
                "article_title": "Article continuation",
                "source_mode": "Develop as a new independent article",
                "draft_stage": "continuation_after_results",
                "include_source_search": False,
            }
        )
    except ValueError as exc:
        assert "previous article sections" in str(exc)
    else:
        raise AssertionError("Expected continuation validation error")


def test_text_file_extraction():
    from app.file_extractor import extract_uploaded_text

    result = extract_uploaded_text("results.txt", b"Model 1 coefficient = 0.42\np-value = 0.01")
    assert result["filename"] == "results.txt"
    assert "0.42" in result["text"]
