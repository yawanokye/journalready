import os
from pathlib import Path

import pytest

from app.annotated_exporter import _native_group_location_markers_enabled, _sentence_spans
from app.ai_config import HybridAIConfig
from app.document_parser import detect_doctoral_functional_coverage, detect_standard_chapter_coverage
from app.model_router import CostAwareAIProvider, ReviewStage
from app.review_engine import _partition_submission_for_review
from app.thesis_alignment_matrix import build_objective_alignment_matrix
from app.thesis_structure import build_chapter_role_map, uses_flexible_phd_structure


def row(text, heading, chapter, paragraph, is_heading=False):
    return {
        "text": text,
        "heading": heading,
        "chapter_number": chapter,
        "paragraph": paragraph,
        "page": None,
        "is_heading": is_heading,
        "chapter_marker_number": chapter if is_heading else None,
        "chapter_title_number": None,
        "section_number_chapter": None,
        "section_number": None,
    }


def phd_seven_chapter_thesis():
    data = []
    n = 1

    def add(chapter, heading, text):
        nonlocal n
        data.append(row(heading, heading, chapter, n, True)); n += 1
        data.append(row(text, heading, chapter, n)); n += 1

    add(1, "CHAPTER ONE INTRODUCTION AND RESEARCH PROBLEM",
        "The background to the study and study context establish the rationale for the study. "
        "The statement of the problem supports the aim of the study, specific objectives, research questions and research hypotheses. "
        "The significance of the study, scope of the study and definition of terms are stated.")
    add(2, "CHAPTER TWO CONTEXTUAL FRAMEWORK",
        "The contextual framework and historical background explain the disciplinary context and structural dynamics of the study.")
    add(3, "CHAPTER THREE LITERATURE REVIEW AND THEORY",
        "The literature review provides a critical synthesis, empirical review, theoretical framework and conceptual framework. "
        "It identifies the research gap, originality and expected contribution to knowledge.")
    add(4, "CHAPTER FOUR METHODOLOGY",
        "The research methodology explains the research philosophy, research approach and research design. "
        "It covers the population of the study, sample size, sampling procedure, data sources, data collection, measurement of variables and operationalisation of variables. "
        "The data analysis and model specification include diagnostic tests, robustness, software and code for reproducibility. "
        "Ethical considerations, ethics approval, confidentiality and research integrity are addressed.")
    add(5, "CHAPTER FIVE RESULTS OF THE STUDY",
        "The results and empirical findings present descriptive statistics, model estimates and analytical evidence for Objective 1.")
    add(6, "CHAPTER SIX DISCUSSION OF FINDINGS",
        "The discussion of findings integrates theory, interprets Objective 1 and considers alternative explanations and unexpected findings.")
    add(7, "CHAPTER SEVEN CONCLUSIONS AND CONTRIBUTION",
        "The conclusions state the original contribution to knowledge, theoretical contribution and methodological contribution. "
        "Policy implications, recommendations, limitations of the study and directions for future research are provided.")
    return data


def standard_five_chapter_thesis():
    rows = phd_seven_chapter_thesis()
    # Consolidate results and discussion into Chapter 4, and conclusions into 5.
    output = []
    p = 1
    mapping = {
        1: ("CHAPTER ONE INTRODUCTION", "Background to the study. Statement of the problem. Aim, objectives, research questions, significance, scope and definitions."),
        2: ("CHAPTER TWO LITERATURE REVIEW", "Literature review, theoretical framework, conceptual framework, empirical review and research gap."),
        3: ("CHAPTER THREE RESEARCH METHODS", "Research philosophy, design, population, sampling, data collection, measurement, analysis and ethical considerations."),
        4: ("CHAPTER FOUR RESULTS AND DISCUSSION", "Results, findings, hypothesis testing and discussion of findings by objective."),
        5: ("CHAPTER FIVE SUMMARY CONCLUSIONS AND RECOMMENDATIONS", "Summary of findings, conclusions, recommendations, limitations and future research."),
    }
    for chapter, (heading, text) in mapping.items():
        output.append(row(heading, heading, chapter, p, True)); p += 1
        output.append(row(text, heading, chapter, p)); p += 1
    return output


def test_only_phd_uses_flexible_structure():
    assert uses_flexible_phd_structure("PhD") is True
    assert uses_flexible_phd_structure("Professional Doctorate") is False
    assert uses_flexible_phd_structure("Research Masters / MPhil") is False


def test_phd_accepts_seven_chapters_only_when_all_prescribed_elements_exist():
    paragraphs = phd_seven_chapter_thesis()
    coverage = detect_doctoral_functional_coverage(paragraphs)
    assert coverage["complete"] is True
    assert coverage["missing_prescribed_elements"] == []
    partition = _partition_submission_for_review(
        paragraphs,
        selected_chapter=None,
        full_thesis=True,
        filename="phd.docx",
        academic_level="PhD",
    )
    assert partition["structure_mode"] == "flexible_doctoral"
    assert partition["fixed_five_chapter_required"] is False


def test_phd_rejects_variable_structure_when_prescribed_element_is_missing():
    paragraphs = [r for r in phd_seven_chapter_thesis() if "ethical considerations" not in r["text"].lower()]
    # Reinsert the methodology without ethics to preserve the chapter itself.
    paragraphs.append(row(
        "The methodology covers design, population, sampling, data collection, measurement, analysis, diagnostics, robustness, software and code.",
        "CHAPTER FOUR METHODOLOGY", 4, 99,
    ))
    coverage = detect_doctoral_functional_coverage(paragraphs)
    assert "Ethics and research integrity" in coverage["missing_prescribed_elements"]
    with pytest.raises(ValueError, match="Missing prescribed elements"):
        _partition_submission_for_review(
            paragraphs,
            selected_chapter=None,
            full_thesis=True,
            filename="incomplete-phd.docx",
            academic_level="PhD",
        )


def test_professional_doctorate_and_other_levels_use_five_chapters():
    standard = standard_five_chapter_thesis()
    for level in ("Bachelors", "Non-Research Masters", "Research Masters / MPhil", "Professional Doctorate"):
        partition = _partition_submission_for_review(
            standard,
            selected_chapter=None,
            full_thesis=True,
            filename="standard.docx",
            academic_level=level,
        )
        assert partition["structure_mode"] == "standard_five_chapter"
        assert partition["fixed_five_chapter_required"] is True


def test_additional_chapter_does_not_replace_missing_standard_chapter():
    rows = [r for r in standard_five_chapter_thesis() if r["chapter_number"] != 5]
    rows.extend([
        row("CHAPTER SIX CONCLUSIONS", "CHAPTER SIX CONCLUSIONS", 6, 20, True),
        row("Summary, conclusions and recommendations.", "CHAPTER SIX CONCLUSIONS", 6, 21),
    ])
    coverage = detect_standard_chapter_coverage(rows)
    assert coverage["complete"] is False
    assert 5 in coverage["missing_chapter_numbers"]


def test_phd_roles_are_inferred_from_function_not_number():
    role_map = build_chapter_role_map(phd_seven_chapter_thesis(), "PhD")
    assert role_map[4]["role"] == "methodology"
    assert role_map[5]["role"] == "results"
    assert role_map[6]["role"] == "discussion"
    assert role_map[7]["role"] == "conclusion_contribution"


def test_standard_chapter_four_covers_results_and_discussion():
    role_map = build_chapter_role_map(standard_five_chapter_thesis(), "Professional Doctorate")
    assert role_map[4]["role"] == "results"
    assert "discussion" in role_map[4]["roles"]


def test_objective_matrix_traces_phd_variable_chapters():
    paragraphs = phd_seven_chapter_thesis()
    # Add a formally numbered objective in the Chapter One objective section.
    paragraphs.insert(2, row("RESEARCH OBJECTIVES", "RESEARCH OBJECTIVES", 1, 2, True))
    paragraphs.insert(3, row("1. To examine budget transparency and climate action.", "RESEARCH OBJECTIVES", 1, 3))
    for chapter, heading, text in (
        (4, "CHAPTER FOUR METHODOLOGY", "Objective 1 is estimated using a panel model of budget transparency and climate action."),
        (5, "CHAPTER FIVE RESULTS", "Results for Objective 1 show the association between budget transparency and climate action."),
        (6, "CHAPTER SIX DISCUSSION", "The discussion of Objective 1 explains budget transparency and climate action using theory."),
        (7, "CHAPTER SEVEN CONCLUSIONS", "The conclusion for Objective 1 concerns budget transparency and climate action."),
    ):
        paragraphs.append(row(text, heading, chapter, 100 + chapter))
    matrix = build_objective_alignment_matrix(paragraphs, "PhD")
    assert matrix["objective_count"] >= 1
    assert matrix["complete_trace_count"] >= 1


def test_sentence_anchoring_preserves_decimals_doi_and_et_al():
    text = "The value was $11.4 billion and warming was 1.2°C. Smith et al. (2025) reported doi.org/10.1108/JICES-09-2025-0264. Next sentence."
    spans = [segment for _, _, segment in _sentence_spans(text)]
    joined = "".join(spans)
    assert "$11.4" in joined
    assert "1.2°C" in joined
    assert "10.1108" in joined
    assert any("Smith et al. (2025)" in segment for segment in spans)


def test_visible_body_markers_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("VPROF_NATIVE_GROUP_LOCATION_MARKERS", raising=False)
    assert _native_group_location_markers_enabled() is False


def test_combined_pipeline_allows_selective_section_escalation(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("VPROF_ENABLE_OPENAI", "true")
    monkeypatch.setenv("VPROF_COMBINED_APP_PIPELINE", "true")
    monkeypatch.setenv("VPROF_ENABLE_SELECTIVE_ESCALATION", "true")
    monkeypatch.setenv("OPENAI_SECTION_ANALYSIS_MODEL", "gpt-5.6-terra")
    monkeypatch.setenv("OPENAI_FINAL_SYNTHESIS_MODEL", "gpt-5.6-sol")
    config = HybridAIConfig.from_env()
    provider = CostAwareAIProvider(config)
    plan = provider.plan(stage=ReviewStage.STANDARD_REVIEW, review_depth="standard")
    assert plan.allow_escalation is False
    assert plan.escalation is not None
    assert plan.escalation.model == "gpt-5.6-sol"
    advanced = provider.plan(stage=ReviewStage.ADVANCED_REVIEW, review_depth="advanced")
    assert advanced.allow_escalation is True


def test_no_previous_study_terms_remain_in_generic_generators():
    root = Path(__file__).resolve().parents[1] / "app"
    generator_files = [
        root / "human_supervisory_editor.py",
        root / "final_review_quality.py",
        root / "deterministic_supervisory_checklist.py",
        root / "supervisory_accuracy_guard.py",
        root / "ucc_section_contract.py",
    ]
    forbidden = ("ghanaian colleges of education", "green procurement", "asha-mari", "sijm-eeken")
    content = "\n".join(path.read_text(encoding="utf-8").lower() for path in generator_files)
    for phrase in forbidden:
        assert phrase not in content
