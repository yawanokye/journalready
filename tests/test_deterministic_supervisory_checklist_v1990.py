from app.deterministic_supervisory_checklist import deterministic_supervisory_checklist_issues


def para(n, text, *, section, chapter=1, heading=False):
    return {
        "text": text,
        "paragraph": n,
        "page": 1,
        "chapter_number": chapter,
        "is_heading": heading,
        "heading": section,
        "section_path": [section],
        "document_role": "current",
    }


def test_chapter_one_checklist_adds_structural_mphil_findings():
    paragraphs = [
        para(1, "University of Cape Coast", section="Title Page", chapter=None, heading=True),
        para(2, "CHAPTER ONE", section="Chapter One", chapter=1, heading=True),
        para(3, "Background to the Study", section="Background to the Study", chapter=1, heading=True),
        para(4, "The study revolve around climate change and pollution. Several studies are mentioned.", section="Background to the Study", chapter=1),
        para(5, "Statement of the Problem", section="Statement of the Problem", chapter=1, heading=True),
        para(6, "Manufacturing firms affect the environment. Hence, this project aims to investigate related issues.", section="Statement of the Problem", chapter=1),
        para(7, "Purpose of the study", section="Purpose of the study", chapter=1, heading=True),
        para(8, "The purpose of this study is to examine green procurement and environmental sustainability.", section="Purpose of the study", chapter=1),
        para(9, "Research Objectives", section="Research Objectives", chapter=1, heading=True),
        para(10, "To examine green procurement practices. To assess awareness. To examine operational performance.", section="Research Objectives", chapter=1),
        para(11, "Delimitation of the Study", section="Delimitation of the Study", chapter=1, heading=True),
        para(12, "The study covers data collected between [insert start month/year] and [insert end month/year].", section="Delimitation of the Study", chapter=1),
    ]

    issues = deterministic_supervisory_checklist_issues(
        paragraphs,
        academic_level="Research Masters/MPhil",
        research_approach="quantitative",
        max_issues=20,
    )

    assert issues
    titles = "\n".join(issue["issue_title"] for issue in issues)
    assert "central research problem" in titles.lower() or "problem" in titles.lower()
    assert any(issue.get("category") == "objectives_questions_hypotheses" for issue in issues)
    assert all("University of Cape Coast" not in issue.get("problematic_quote", "") for issue in issues)
    assert all(issue.get("evidence_paragraph_ids") for issue in issues)


def test_checklist_respects_uploaded_chapter_scope():
    paragraphs = [
        para(1, "CHAPTER ONE", section="Chapter One", chapter=1, heading=True),
        para(2, "Background to the Study", section="Background to the Study", chapter=1, heading=True),
        para(3, "The background gives a global context only.", section="Background to the Study", chapter=1),
    ]
    issues = deterministic_supervisory_checklist_issues(
        paragraphs,
        academic_level="Research Masters/MPhil",
        research_approach="quantitative",
        max_issues=50,
    )
    codes = {issue.get("checklist_code") for issue in issues}
    assert not any(str(code).startswith("C") for code in codes)
    assert not any(str(code).startswith("D") for code in codes)
    assert not any(str(code).startswith("E") for code in codes)
    assert not any(str(code).startswith("F") for code in codes)
