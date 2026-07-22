from __future__ import annotations

import pytest

from app.academic_ai_engine import (
    _degree_audit_max_findings,
    _degree_audit_settings,
    _degree_issue_limit,
    _degree_primary_output_tokens,
    _degree_specific_review_contract,
    _use_research_intensive_route,
)
from app.ai_config import HybridAIConfig
from app.model_router import ReviewStage
from app.supervisory_accuracy_guard import deterministic_expert_issues


@pytest.mark.parametrize(
    "level,audit_capacity,orientation",
    [
        ("Bachelors", 32, "foundational-research"),
        ("Non-Research Masters", 42, "applied-master's"),
        ("Research Masters / MPhil", 56, "research-intensive-master's"),
        ("Professional Doctorate", 68, "practice-based-doctoral"),
        ("PhD", 80, "knowledge-creation-doctoral"),
    ],
)
def test_every_level_has_distinct_standard_depth_without_comment_quotas(level, audit_capacity, orientation):
    contract = _degree_specific_review_contract(level, 1, "standard")
    assert _degree_issue_limit(level, "standard") == 0
    assert _degree_audit_max_findings(level, "standard") == audit_capacity
    assert contract["orientation"] == orientation
    assert contract["coverage_driven_review"] is True
    assert "No predetermined comment count" in contract["comment_count_rule"]
    assert len(contract["chapter_specific_mandatory_checks"]) >= 8
    assert len(contract["mandatory_dimensions"]) >= 9


def test_professional_doctorate_and_phd_have_different_contribution_contracts():
    professional = _degree_specific_review_contract("Professional Doctorate", 1, "standard")
    phd = _degree_specific_review_contract("PhD", 1, "standard")
    assert "professional practice" in professional["contribution_standard"]
    assert "contribution to knowledge" in phd["contribution_standard"]
    assert professional["mandatory_dimensions"] != phd["mandatory_dimensions"]


def test_all_chapter_types_receive_mandatory_checks():
    for chapter in range(1, 8):
        for level in ("Bachelors", "Non-Research Masters", "Research Masters / MPhil", "Professional Doctorate", "PhD"):
            contract = _degree_specific_review_contract(level, chapter, "standard")
            assert contract["chapter_specific_mandatory_checks"], (level, chapter)


def test_degree_specific_tokens_and_audits(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    config = HybridAIConfig.from_env()

    assert _degree_primary_output_tokens("Bachelors", "standard", config) == config.standard_max_output_tokens
    assert _degree_primary_output_tokens("Non-Research Masters", "standard", config) == config.non_research_masters_max_output_tokens
    assert _degree_primary_output_tokens("Research Masters / MPhil", "standard", config) == config.research_masters_max_output_tokens
    assert _degree_primary_output_tokens("Professional Doctorate", "standard", config) == config.professional_doctorate_max_output_tokens
    assert _degree_primary_output_tokens("PhD", "standard", config) == config.phd_max_output_tokens

    bachelor = _degree_audit_settings("Bachelors", "standard", config)
    applied = _degree_audit_settings("Non-Research Masters", "standard", config)
    mphil = _degree_audit_settings("Research Masters / MPhil", "standard", config)
    professional = _degree_audit_settings("Professional Doctorate", "standard", config)
    phd = _degree_audit_settings("PhD", "standard", config)

    assert bachelor[0] == config.openai_chapter_model
    assert applied[0] == config.openai_chapter_model
    assert mphil[0] == config.openai_expert_model
    assert professional[0] == config.openai_expert_model
    assert phd[0] == config.openai_expert_model
    assert bachelor[2] < applied[2] < mphil[2] < professional[2] <= phd[2]
    assert bachelor[3] is ReviewStage.FINAL_AUDIT
    assert applied[3] is ReviewStage.FINAL_AUDIT
    assert mphil[3] is ReviewStage.RESEARCH_INTENSIVE_AUDIT
    assert professional[3] is ReviewStage.RESEARCH_INTENSIVE_AUDIT
    assert phd[3] is ReviewStage.RESEARCH_INTENSIVE_AUDIT


def test_research_intensive_route_is_reserved_for_research_degrees(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    config = HybridAIConfig.from_env()
    assert not _use_research_intensive_route("Bachelors", config)
    assert not _use_research_intensive_route("Non-Research Masters", config)
    assert _use_research_intensive_route("Research Masters / MPhil", config)
    assert _use_research_intensive_route("Professional Doctorate", config)
    assert _use_research_intensive_route("PhD", config)


def test_deterministic_quality_checks_apply_to_every_level():
    rows = [
        {"paragraph": 1, "text": "The purpose of this study is to examine environmental sustainability.", "heading": "Purpose of the Study", "section_path": ["CHAPTER ONE", "Purpose of the Study"], "chapter_number": 1, "document_role": "current", "is_heading": False},
        {"paragraph": 2, "text": "To assess awareness and operational performance among firms.", "heading": "Research Objectives", "section_path": ["CHAPTER ONE", "Research Objectives"], "chapter_number": 1, "document_role": "current", "is_heading": False},
        {"paragraph": 3, "text": "As the results reveal a connection, firms will benefit from the study.", "heading": "Significance of the Study", "section_path": ["CHAPTER ONE", "Significance of the Study"], "chapter_number": 1, "document_role": "current", "is_heading": False},
    ]
    for level in ("Bachelors", "Non-Research Masters", "Research Masters / MPhil", "Professional Doctorate", "PhD"):
        ids = {item["finding_id"] for item in deterministic_expert_issues(rows, academic_level=level)}
        assert "DET-DEGREE-PURPOSE-OBJECTIVE-COVERAGE" in ids
        assert "DET-DEGREE-PREMATURE-SIGNIFICANCE-RESULTS" in ids
