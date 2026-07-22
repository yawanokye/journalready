from __future__ import annotations

from app.academic_ai_engine import _valid_issue
from app.ai_prompts import COMMON_CONTEXT_RULES
from app.comment_quality import deduplicate_public_issues, prepare_public_issues
from app.context_guard import build_context_lock
from app.supervisory_accuracy_guard import apply_accuracy_gate, paragraph_id
from app.supervisory_review_algorithm import SECTION_REVIEW_COMMAND
from app.ucc_section_contract import (
    SECTION_STATUS_INADEQUATE,
    SECTION_STATUS_MISSING,
    build_section_coverage_ledger,
    missing_section_labels_in_output,
    section_contract_key,
    ucc_section_contract_issues,
)


def row(n, text, *, chapter=1, heading=None, is_heading=False, path=None):
    return {
        "paragraph": n,
        "text": text,
        "heading": heading,
        "chapter_number": chapter,
        "is_heading": is_heading,
        "document_role": "current",
        "section_path": list(path or ([heading] if heading else [])),
    }


def chapter_one_with_general_objective_only():
    return [
        row(1, "CHAPTER ONE", heading="CHAPTER ONE", is_heading=True, path=["CHAPTER ONE"]),
        row(2, "Introduction", heading="Introduction", is_heading=True, path=["CHAPTER ONE", "Introduction"]),
        row(3, "This chapter introduces a study of internal controls and fraud prevention among rural banks in Ghana.", heading="Introduction", path=["CHAPTER ONE", "Introduction"]),
        row(4, "Background to the Study", heading="Background to the Study", is_heading=True, path=["CHAPTER ONE", "Background to the Study"]),
        row(5, "Internal controls are relevant to fraud prevention in Ghanaian rural banks. However, evidence on Assinman Rural Bank remains limited. " * 5, heading="Background to the Study", path=["CHAPTER ONE", "Background to the Study"]),
        row(6, "Statement of the Problem", heading="Statement of the Problem", is_heading=True, path=["CHAPTER ONE", "Statement of the Problem"]),
        row(7, "A 2024 report documented recurring fraud losses in Ghanaian banks. Despite this evidence, it remains unclear whether internal controls reduce fraud at Assinman Rural Bank. " * 3, heading="Statement of the Problem", path=["CHAPTER ONE", "Statement of the Problem"]),
        row(8, "Research Objectives", heading="Research Objectives", is_heading=True, path=["CHAPTER ONE", "Research Objectives"]),
        row(9, "General Objective", heading="General Objective", is_heading=True, path=["CHAPTER ONE", "Research Objectives", "General Objective"]),
        row(10, "To examine the effect of internal controls on fraud prevention at Assinman Rural Bank.", heading="General Objective", path=["CHAPTER ONE", "Research Objectives", "General Objective"]),
        row(11, "Specific Objectives", heading="Specific Objectives", is_heading=True, path=["CHAPTER ONE", "Research Objectives", "Specific Objectives"]),
        row(12, "To assess the effect of segregation of duties on fraud prevention. To determine the influence of authorisation controls on fraud detection.", heading="Specific Objectives", path=["CHAPTER ONE", "Research Objectives", "Specific Objectives"]),
        row(13, "Research Questions", heading="Research Questions", is_heading=True, path=["CHAPTER ONE", "Research Questions"]),
        row(14, "What internal controls are used at Assinman Rural Bank?", heading="Research Questions", path=["CHAPTER ONE", "Research Questions"]),
        row(15, "Significance of the Study", heading="Significance of the Study", is_heading=True, path=["CHAPTER ONE", "Significance of the Study"]),
        row(16, "The study adds empirical evidence to the literature and may inform bank management and regulatory policy. " * 4, heading="Significance of the Study", path=["CHAPTER ONE", "Significance of the Study"]),
        row(17, "Scope of the Study", heading="Scope of the Study", is_heading=True, path=["CHAPTER ONE", "Scope of the Study"]),
        row(18, "The study focuses on internal controls and fraud prevention at Assinman Rural Bank.", heading="Scope of the Study", path=["CHAPTER ONE", "Scope of the Study"]),
        row(19, "Limitations of the Study", heading="Limitations of the Study", is_heading=True, path=["CHAPTER ONE", "Limitations of the Study"]),
        row(20, "Limited access to confidential fraud records may restrict the completeness of the evidence and therefore limits interpretation.", heading="Limitations of the Study", path=["CHAPTER ONE", "Limitations of the Study"]),
        row(21, "Organisation of the Study", heading="Organisation of the Study", is_heading=True, path=["CHAPTER ONE", "Organisation of the Study"]),
        row(22, "Chapter One introduces the study. Chapter Two reviews literature. Chapter Three explains methods. Chapter Four presents results. Chapter Five concludes.", heading="Organisation of the Study", path=["CHAPTER ONE", "Organisation of the Study"]),
    ]


def material_entries(rows, level="Research Masters (MPhil)", scope="Chapter One"):
    ledger = build_section_coverage_ledger(rows, academic_level=level, depth="standard", submission_scope=scope)
    return {(entry["chapter_number"], entry["label"]): entry for entry in ledger["entries"]}


def test_general_objective_does_not_satisfy_purpose_at_any_level():
    rows = chapter_one_with_general_objective_only()
    for level in ("Bachelors", "Non-Research Masters", "Research Masters (MPhil)", "PhD"):
        entries = material_entries(rows, level)
        assert entries[(1, "Purpose of the Study")]["status"] == SECTION_STATUS_MISSING


def test_parent_research_objectives_aggregate_general_and_specific_children():
    entries = material_entries(chapter_one_with_general_objective_only())
    assert entries[(1, "Research Objectives")]["status"] not in {SECTION_STATUS_MISSING, SECTION_STATUS_INADEQUATE}
    assert len(entries[(1, "Research Objectives")]["paragraph_ids"]) >= 4


def test_inferential_objectives_trigger_hypotheses_at_all_levels():
    rows = chapter_one_with_general_objective_only()
    for level in ("Bachelors", "Non-Research Masters", "Research Masters (MPhil)", "Professional Doctorate", "PhD"):
        entries = material_entries(rows, level)
        assert entries[(1, "Research Hypotheses")]["status"] == SECTION_STATUS_MISSING


def test_brief_scope_is_equivalent_heading_but_inadequate_at_all_levels():
    rows = chapter_one_with_general_objective_only()
    for level in ("Bachelors", "Non-Research Masters", "Research Masters (MPhil)", "PhD"):
        entry = material_entries(rows, level)[(1, "Delimitations of the Study")]
        assert entry["matched_heading"] == "Scope of the Study"
        assert entry["status"] == SECTION_STATUS_INADEQUATE


def test_missing_definition_survives_validity_accuracy_and_public_quality_gates():
    rows = chapter_one_with_general_objective_only()
    issue = next(
        item for item in ucc_section_contract_issues(rows, academic_level="Research Masters (MPhil)", depth="standard", max_issues=500)
        if item.get("section_contract_label") == "Definition of Terms"
    )
    paragraph_index = {paragraph_id(item): item for item in rows if paragraph_id(item)}
    valid = _valid_issue(issue, paragraph_index, build_context_lock(rows))
    assert valid is not None
    guarded, _ = apply_accuracy_gate([valid], paragraph_index, rows)
    assert len(guarded) == 1
    public, _ = prepare_public_issues(guarded)
    assert len(public) == 1
    assert public[0]["section_contract_label"] == "Definition of Terms"
    assert "Definition of Terms is missing" in public[0]["issue_title"]


def test_same_missing_label_in_two_chapters_is_not_merged_or_treated_as_covered():
    rows = [
        row(1, "CHAPTER TWO", chapter=2, heading="CHAPTER TWO", is_heading=True, path=["CHAPTER TWO"]),
        row(2, "Introduction", chapter=2, heading="Introduction", is_heading=True, path=["CHAPTER TWO", "Introduction"]),
        row(3, "This chapter reviews relevant theory and evidence.", chapter=2, heading="Introduction", path=["CHAPTER TWO", "Introduction"]),
        row(4, "Theoretical Review", chapter=2, heading="Theoretical Review", is_heading=True, path=["CHAPTER TWO", "Theoretical Review"]),
        row(5, "Social Cognitive Theory explains the study variables and expected relationships. " * 10, chapter=2, heading="Theoretical Review", path=["CHAPTER TWO", "Theoretical Review"]),
        row(6, "Conceptual Review", chapter=2, heading="Conceptual Review", is_heading=True, path=["CHAPTER TWO", "Conceptual Review"]),
        row(7, "Internal control is defined as a system of policies and procedures. Fraud prevention refers to measures used to reduce fraud risk. " * 8, chapter=2, heading="Conceptual Review", path=["CHAPTER TWO", "Conceptual Review"]),
        row(8, "Empirical Review", chapter=2, heading="Empirical Review", is_heading=True, path=["CHAPTER TWO", "Empirical Review"]),
        row(9, "Studies in 2020, 2021 and 2022 reported different findings. However, the designs and samples differed, whereas the Ghanaian evidence remains limited. " * 8, chapter=2, heading="Empirical Review", path=["CHAPTER TWO", "Empirical Review"]),
        row(10, "Literature Gap", chapter=2, heading="Literature Gap", is_heading=True, path=["CHAPTER TWO", "Literature Gap"]),
        row(11, "The gap is that few studies have examined this relationship in Ghanaian rural banks.", chapter=2, heading="Literature Gap", path=["CHAPTER TWO", "Literature Gap"]),
        row(12, "Conceptual Framework", chapter=2, heading="Conceptual Framework", is_heading=True, path=["CHAPTER TWO", "Conceptual Framework"]),
        row(13, "The framework predicts that internal controls reduce fraud and that governance moderates the relationship. " * 5, chapter=2, heading="Conceptual Framework", path=["CHAPTER TWO", "Conceptual Framework"]),
        row(14, "CHAPTER THREE", chapter=3, heading="CHAPTER THREE", is_heading=True, path=["CHAPTER THREE"]),
        row(15, "Introduction", chapter=3, heading="Introduction", is_heading=True, path=["CHAPTER THREE", "Introduction"]),
        row(16, "This chapter explains the research methods and analysis.", chapter=3, heading="Introduction", path=["CHAPTER THREE", "Introduction"]),
    ]
    issues = ucc_section_contract_issues(rows, academic_level="MPhil", depth="standard", max_issues=500, submission_scope="Combined Chapters 2-3")
    summaries = [item for item in issues if item.get("section_contract_label") == "Chapter Summary"]
    assert {item.get("chapter_number") for item in summaries} == {2, 3}
    deduped = deduplicate_public_issues(summaries)
    assert len(deduped) == 2
    uncovered = missing_section_labels_in_output(rows, [summaries[0]], academic_level="MPhil", depth="standard", submission_scope="Combined Chapters 2-3")
    assert section_contract_key(summaries[1]["chapter_number"], "Chapter Summary") in uncovered


def test_full_submission_checks_front_and_back_matter_but_chapter_only_does_not():
    chapter_rows = chapter_one_with_general_objective_only()
    partial = build_section_coverage_ledger(chapter_rows, academic_level="MPhil", submission_scope="Chapter One")
    assert not any(entry.get("document_level") for entry in partial["entries"])

    full_rows = list(chapter_rows)
    n = 30
    for chapter in (2, 3, 4):
        full_rows.extend([
            row(n, f"CHAPTER {chapter}", chapter=chapter, heading=f"CHAPTER {chapter}", is_heading=True, path=[f"CHAPTER {chapter}"]),
            row(n + 1, "Introduction", chapter=chapter, heading="Introduction", is_heading=True, path=[f"CHAPTER {chapter}", "Introduction"]),
            row(n + 2, "This chapter presents the required content for the study.", chapter=chapter, heading="Introduction", path=[f"CHAPTER {chapter}", "Introduction"]),
        ])
        n += 3
    ledger = build_section_coverage_ledger(full_rows, academic_level="MPhil", submission_scope="full thesis")
    document_entries = [entry for entry in ledger["entries"] if entry.get("document_level")]
    labels = {entry["label"] for entry in document_entries}
    assert {"Title Page", "Declaration", "Abstract", "Table of Contents", "References"}.issubset(labels)
    assert all(entry["status"] == SECTION_STATUS_MISSING for entry in document_entries if entry["label"] in {"Title Page", "Declaration", "Abstract", "Table of Contents", "References"})


def test_prompts_preserve_chapter_specific_synthesis_and_all_level_structure_rules():
    assert "focused and selective" in COMMON_CONTEXT_RULES
    assert "deep critical synthesis" in COMMON_CONTEXT_RULES
    assert "Purpose of the Study as distinct from General Objective" in COMMON_CONTEXT_RULES
    assert "Bachelor’s, Non-Research Master’s, MPhil" in COMMON_CONTEXT_RULES
    assert "aggregate parent sections" in SECTION_REVIEW_COMMAND


def test_contract_comments_avoid_mechanical_level_and_upload_language():
    issues = ucc_section_contract_issues(chapter_one_with_general_objective_only(), academic_level="MPhil", depth="standard", max_issues=500)
    text = " ".join(
        str(issue.get(key, ""))
        for issue in issues
        for key in ("issue_title", "assessment", "required_action", "illustrative_guidance")
    ).lower()
    assert "at mphil level" not in text
    assert "at phd level" not in text
    assert "uploaded document" not in text
    assert "uploaded text" not in text
    assert "traceability of research methods" not in text
