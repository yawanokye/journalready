from app.statistical_review import audit_table_level_accuracy, build_statistical_review
from app.student_friendly_review import make_issue_student_friendly
from app.ucc_section_contract import ucc_section_contract_issues


def p(n, text, heading=None, chapter=1, is_heading=False):
    return {
        "paragraph": n,
        "text": text,
        "heading": heading,
        "chapter_number": chapter,
        "is_heading": is_heading,
        "document_role": "current",
        "source_kind": "paragraph",
    }


def trow(n, text, table_index, table_number, title, row_no, heading="Results"):
    return {
        "paragraph": n,
        "text": text,
        "heading": heading,
        "chapter_number": 4,
        "is_heading": False,
        "document_role": "current",
        "source_kind": "table_row",
        "table_index": table_index,
        "table_number": str(table_number),
        "table_title": title,
        "table_row": row_no,
    }


def test_missing_section_language_is_direct_and_student_friendly():
    rows = [
        p(1, "CHAPTER ONE", "CHAPTER ONE", 1, True),
        p(2, "Introduction", "Introduction", 1, True),
        p(3, "This study examines perceived value and academic engagement.", "Introduction"),
        p(4, "Background to the Study", "Background to the Study", 1, True),
        p(5, "Perceived value may shape academic engagement.", "Background to the Study"),
        p(6, "Statement of the Problem", "Statement of the Problem", 1, True),
        p(7, "The problem remains insufficiently understood.", "Statement of the Problem"),
        p(8, "Purpose of the Study", "Purpose of the Study", 1, True),
        p(9, "The study examines perceived value and academic engagement.", "Purpose of the Study"),
        p(10, "Research Objectives", "Research Objectives", 1, True),
        p(11, "To examine perceived value and academic engagement.", "Research Objectives"),
        p(12, "Research Questions", "Research Questions", 1, True),
        p(13, "What is the relationship between perceived value and academic engagement?", "Research Questions"),
        p(14, "Significance of the Study", "Significance of the Study", 1, True),
        p(15, "The study will inform teaching practice.", "Significance of the Study"),
        p(16, "Scope of the Study", "Scope of the Study", 1, True),
        p(17, "The study covers selected schools.", "Scope of the Study"),
        p(18, "Organisation of the Study", "Organisation of the Study", 1, True),
        p(19, "Chapter Two reviews literature.", "Organisation of the Study"),
    ]
    issues = ucc_section_contract_issues(rows, academic_level="MPhil", depth="standard")
    issue = next(item for item in issues if item.get("missing_section_label") == "Definition of Terms")
    public = make_issue_student_friendly(issue, "MPhil")
    joined = " ".join(str(public.get(k, "")) for k in ("issue_title", "assessment", "required_action", "illustrative_guidance"))
    assert public["issue_title"] == "Definition of Terms is missing from Chapter One"
    assert "UCC thesis guidelines" in public["assessment"]
    assert "uploaded" not in joined.lower()
    assert "automated review" not in joined.lower()
    assert "perceived value" in public["illustrative_guidance"].lower()


def test_definition_of_key_concepts_is_accepted_as_definition_of_terms():
    rows = [
        p(1, "CHAPTER ONE", "CHAPTER ONE", 1, True),
        p(2, "Background to the Study", "Background to the Study", 1, True),
        p(3, "Background content " * 20, "Background to the Study"),
        p(4, "Statement of the Problem", "Statement of the Problem", 1, True),
        p(5, "Problem content " * 20, "Statement of the Problem"),
        p(6, "Purpose of the Study", "Purpose of the Study", 1, True),
        p(7, "The purpose is stated clearly " * 10, "Purpose of the Study"),
        p(8, "Research Objectives", "Research Objectives", 1, True),
        p(9, "The objectives are stated clearly " * 10, "Research Objectives"),
        p(10, "Research Questions", "Research Questions", 1, True),
        p(11, "The questions are stated clearly " * 10, "Research Questions"),
        p(12, "Significance of the Study", "Significance of the Study", 1, True),
        p(13, "The significance is stated clearly " * 10, "Significance of the Study"),
        p(14, "Limitations of the Study", "Limitations of the Study", 1, True),
        p(15, "The limitations are stated clearly " * 10, "Limitations of the Study"),
        p(16, "Scope of the Study", "Scope of the Study", 1, True),
        p(17, "The scope is stated clearly " * 10, "Scope of the Study"),
        p(18, "Definition of Key Concepts", "Definition of Key Concepts", 1, True),
        p(19, "Perceived value and academic engagement are defined here " * 10, "Definition of Key Concepts"),
        p(20, "Organisation of the Study", "Organisation of the Study", 1, True),
        p(21, "The chapters are described here " * 10, "Organisation of the Study"),
    ]
    issues = ucc_section_contract_issues(rows, academic_level="MPhil", depth="standard")
    assert not any(item.get("missing_section_label") == "Definition of Terms" for item in issues)


def test_stale_bank_example_is_replaced_for_social_studies_finding():
    issue = {
        "category": "objectives_questions_hypotheses",
        "section": "Research Objectives",
        "issue_title": "The objectives do not align with the purpose",
        "assessment": "The objectives use different constructs from the purpose.",
        "required_action": "Use the same constructs throughout the study.",
        "problematic_quote": "To examine students' perceived value of Social Studies and academic engagement.",
        "illustrative_guidance": "Link pressure, opportunity and rationalisation to fraud incidence and segregation of duties within the bank.",
    }
    public = make_issue_student_friendly(issue, "MPhil")
    example = public["illustrative_guidance"].lower()
    assert "fraud" not in example
    assert "bank" not in example
    assert "perceived value" in example


def test_table_audit_checks_descriptive_mean_regression_and_correlation_language():
    rows = [
        trow(1, "Item | Statement | M | SD", 1, 2, "Descriptive Statistics (N = 350)", 1),
        trow(2, "X1 | First item | 3.00 | .80", 1, 2, "Descriptive Statistics (N = 350)", 2),
        trow(3, "X2 | Second item | 3.20 | .90", 1, 2, "Descriptive Statistics (N = 350)", 3),
        trow(4, "X3 | Third item | 3.40 | .70", 1, 2, "Descriptive Statistics (N = 350)", 4),
        trow(5, "Overall Mean / SD | 3.60 | .80", 1, 2, "Descriptive Statistics (N = 350)", 5),
        trow(10, "Predictor Variables | Outcome Variables | r (Influence) | p | Decision", 2, 4, "Influence of X on Y (N = 350)", 1),
        trow(11, "X | Y | -.48 | < .001 | Significant Influence", 2, 4, "Influence of X on Y (N = 350)", 2),
        trow(20, "Predictor Variable | B | SE B | beta | t | p | R2 | F", 3, 6, "Regression Model (N = 350)", 1),
        trow(21, "Constant | 1.84 | .196 | - | 9.40 | < .001 | .40 | 77.98", 3, 6, "Regression Model (N = 350)", 2),
        trow(22, "Support | .512 | .058 | .63 | 8.83 | < .001 | - | -", 3, 6, "Regression Model (N = 350)", 3),
    ]
    kinds = {item["kind"] for item in audit_table_level_accuracy(rows)}
    assert "descriptive_overall_mean_mismatch" in kinds
    assert "correlation_interpreted_as_influence" in kinds
    assert "table_r2_f_n_mismatch" in kinds


def test_three_way_moderation_requires_all_lower_order_terms():
    title = "Moderating Effect of PAS on the Interaction Between CI and AEE in Predicting Engagement (N = 350)"
    rows = [
        trow(1, "Predictor Variables | B | SE B | beta | t | p | Decision", 5, 9, title, 1),
        trow(2, "CI | -.21 | .04 | -.23 | -5.49 | < .001 | Significant", 5, 9, title, 2),
        trow(3, "AEE | -.20 | .04 | -.21 | -5.30 | < .001 | Significant", 5, 9, title, 3),
        trow(4, "PAS | .39 | .05 | .45 | 8.41 | < .001 | Significant", 5, 9, title, 4),
        trow(5, "CI × AEE | -.15 | .03 | -.19 | -4.58 | < .001 | Significant", 5, 9, title, 5),
        trow(6, "PAS × (CI + AEE interaction) | .17 | .04 | .22 | 4.97 | < .001 | Significant", 5, 9, title, 6),
    ]
    kinds = {item["kind"] for item in audit_table_level_accuracy(rows)}
    assert "three_way_moderation_hierarchy_incomplete" in kinds


def test_build_statistical_review_does_not_use_generic_uploaded_language():
    rows = [
        trow(1, "Predictor Variables | Outcome Variables | r (Influence) | p | Decision", 2, 4, "Influence of X on Y (N = 100)", 1),
        trow(2, "X | Y | -.48 | < .001 | Significant Influence", 2, 4, "Influence of X on Y (N = 100)", 2),
    ]
    review = build_statistical_review(rows, chapter_numbers=[4])
    assert review["warning_count"] >= 1
    assert all("uploaded" not in item["message"].lower() for item in review["consistency_warnings"])
