from __future__ import annotations

from app.context_guard import build_context_lock, sanitise_generated_text, sanitise_issue


def ghana_context():
    paragraphs = [
        {"text": "Stakeholder engagement and project outcomes in mining projects in the Western Region of Ghana", "is_heading": True},
        {"text": "The study examines construction and CSR projects in the mining sector in the Western Region."},
    ]
    return build_context_lock(paragraphs, {"academic_level": "MPhil", "research_approach": "Quantitative"})


def test_external_country_and_setting_are_removed():
    context = ghana_context()
    text, adjusted = sanitise_generated_text(
        "Example: survey project managers in Gauteng, South Africa and compare them with organisations in the UK.",
        context,
    )
    assert adjusted is True
    assert "South Africa" not in text
    assert "Gauteng" not in text
    assert "UK" not in text
    assert "confirmed study setting" in text


def test_source_country_is_preserved():
    context = ghana_context()
    text, adjusted = sanitise_generated_text("The study is situated in Ghana's Western Region.", context)
    assert "Ghana" in text
    assert adjusted is False


def test_unverified_citation_and_statistic_are_replaced():
    context = ghana_context()
    text, adjusted = sanitise_generated_text(
        "Bourne (2016) reported that 55% of projects fail.",
        context,
    )
    assert adjusted is True
    assert "Bourne (2016)" not in text
    assert "55%" not in text
    assert "a verified scholarly source" in text
    assert "a verified statistic" in text


def test_issue_is_flagged_for_source_verification():
    context = ghana_context()
    issue = sanitise_issue({
        "category": "citations_and_sources",
        "issue_title": "Unsupported statistic",
        "assessment": "The 92% statistic requires verification.",
        "academic_consequence": "The problem is not adequately evidenced.",
        "required_action": "Locate and verify the original source.",
        "illustrative_guidance": "Use a verified source from South Africa.",
    }, context)
    assert issue["source_verification_required"] is True
    assert issue["guidance_type"] == "source_verification"
    assert "South Africa" not in issue["illustrative_guidance"]


def test_study_context_ignores_countries_mentioned_only_in_literature():
    paragraphs = [
        {"text": "E-PROCUREMENT ADOPTION ON PROCUREMENT EFFICIENCY: EVIDENCE FROM MOBILE PHONE DEALERS IN CAPE COAST METROPOLIS", "is_heading": True, "heading": "E-PROCUREMENT ADOPTION ON PROCUREMENT EFFICIENCY: EVIDENCE FROM MOBILE PHONE DEALERS IN CAPE COAST METROPOLIS"},
        {"text": "ABSTRACT", "is_heading": True, "heading": "ABSTRACT"},
        {"text": "This study examines mobile phone dealers in the Cape Coast Metropolis, Ghana.", "is_heading": False, "heading": "ABSTRACT"},
        {"text": "Empirical Review", "is_heading": True, "heading": "Empirical Review", "chapter_number": 2},
        {"text": "Prior studies were conducted in South Africa, Kenya, Tanzania, Rwanda and Germany.", "is_heading": False, "heading": "Empirical Review", "chapter_number": 2},
    ]
    context = build_context_lock(paragraphs, {})
    assert context["title_or_opening_focus"].startswith("E-PROCUREMENT ADOPTION")
    assert context["confirmed_countries"] == ["Ghana"]
    assert "South Africa" not in context["confirmed_countries"]
    assert "Kenya" not in context["confirmed_countries"]
