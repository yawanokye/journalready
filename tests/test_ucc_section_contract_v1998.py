from app.academic_ai_engine import _valid_issue
from app.context_guard import build_context_lock
from app.supervisory_accuracy_guard import paragraph_id
from app.ucc_section_contract import ucc_comment_floor, ucc_section_contract_issues


def _p(n, text, heading=None, chapter=1, is_heading=False):
    return {
        "paragraph": n,
        "text": text,
        "heading": heading,
        "chapter_number": chapter,
        "is_heading": is_heading,
        "document_role": "current",
    }


def sample_chapter_one():
    return [
        {"paragraph": 1, "text": "Green Procurement Practices and Environmental Sustainability: A Study of Manufacturing Firms in the Central Region Of Ghana", "heading": None, "chapter_number": None, "is_heading": False, "document_role": "current"},
        _p(2, "CHAPTER ONE", "CHAPTER ONE", 1, True),
        _p(3, "INTRODUCTION", "INTRODUCTION", 1, True),
        _p(4, "Background to the Study", "Background to the Study", 1, True),
        _p(5, "The study revolve around climate change. Asha-Mari & Daud (2026) note green practices. An empirical analysis involving 100 manufacturing enterprises in Ghana shows effects. Central Region firms are mentioned without local statistics.", "Background to the Study"),
        _p(6, "Statement of the Problem", "Statement of the Problem", 1, True),
        _p(7, "Studies from Pakistan, India and Portugal cannot be extrapolated to Ghana. Hence this study examines green procurement in the Central Region.", "Statement of the Problem"),
        _p(8, "Purpose of the study", "Purpose of the study", 1, True),
        _p(9, "The purpose of this study is to examine the effect of green procurement practices on environmental sustainability among manufacturing firms in the Central Region of Ghana.", "Purpose of the study"),
        _p(10, "Research Objectives", "Research Objectives", 1, True),
        _p(11, "To examine current green procurement practices. To assess the relationship between green procurement and environmental sustainability. To assess awareness. To examine the impact of green procurement on operational performance.", "Research Objectives"),
        _p(12, "Research Questions", "Research Questions", 1, True),
        _p(13, "What is the level of awareness regarding green procurement practices among manufacturing firms.?", "Research Questions"),
        _p(14, "Significance of the Study", "Significance of the Study", 1, True),
        _p(15, "The study evaluates the impact of these results. As the results reveal, managers will benefit. Liu et al. (2024) meta analysis shows correlations.", "Significance of the Study"),
        _p(16, "Limitations of the Study", "Limitations of the Study", 1, True),
        _p(17, "Data will be collected once. The study faced practical constraints and some respondents did not participate.", "Limitations of the Study"),
        _p(18, "Delimitation of the Study", "Delimitation of the Study", 1, True),
        _p(19, "The study covers data collected between [insert start month/year] and [insert end month/year].", "Delimitation of the Study"),
        _p(20, "Definition of Terms", "Definition of Terms", 1, True),
        _p(21, "Awareness means the extent of awareness. Environmental sustainability means operating without causing any harm. Environmental Performance is reducing effects. Operational Performance includes cost savings ( Sijm-Eeken et al. 2024)", "Definition of Terms"),
        _p(22, "References", "References", 1, True),
        _p(23, "Asha'ari, M., & Daud, S. (2026). Factorising green practices items.", "References"),
    ]


def test_ucc_section_contract_generates_level_appropriate_depth():
    rows = sample_chapter_one()
    issues = ucc_section_contract_issues(rows, academic_level="Research Masters (MPhil)", depth="standard", max_issues=100)
    titles = {issue["issue_title"] for issue in issues}
    assert ucc_comment_floor(rows, "Research Masters (MPhil)", "standard") == 0
    assert len(issues) >= 1
    assert "The purpose statement is narrower than the objectives" in titles
    assert "The delimitation contains an unresolved drafting placeholder" in titles
    assert any("hypotheses" in title.lower() for title in titles)


def test_valid_issue_accepts_ucc_metadata_fields():
    rows = sample_chapter_one()
    paragraph_index = {paragraph_id(row): row for row in rows if paragraph_id(row)}
    context_lock = build_context_lock(rows)
    first = ucc_section_contract_issues(rows, academic_level="Research Masters (MPhil)", depth="standard", max_issues=5)[0]
    valid = _valid_issue(first, paragraph_index, context_lock)
    assert valid is not None
    assert valid["verification_status"] == "ucc_section_contract"
    assert valid["checklist_code"].startswith("UCC-")
