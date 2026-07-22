from app.thorough_review import thorough_review_deterministic_issues


def row(text, paragraph, chapter, heading):
    return {
        "text": text,
        "paragraph": paragraph,
        "page": paragraph,
        "chapter_number": chapter,
        "heading": heading,
        "section_number": f"{chapter}.{paragraph}",
        "source_kind": "paragraph",
        "document_role": "current",
    }


def test_generic_sem_audit_does_not_assume_example_constructs():
    rows = [
        row("CHAPTER THREE METHODOLOGY. The study used PLS-SEM to test customer satisfaction, service quality and loyalty.", 1, 3, "Data Analysis"),
        row("CHAPTER FOUR RESULTS. The structural model results are presented.", 2, 4, "Results"),
    ]
    issues = thorough_review_deterministic_issues(rows, academic_level="PhD", research_approach="quantitative")
    text = "\n".join(str(item) for item in issues).lower()
    assert "sem" in text or "pls-sem" in text
    assert "classroom incivility" not in text
    assert "academic entitlement" not in text
    assert "perceived academic support" not in text


def test_generic_qualitative_audit_triggers_trustworthiness_not_statistics():
    rows = [
        row("CHAPTER THREE METHODOLOGY. The study used qualitative interviews with participants.", 1, 3, "Data Analysis"),
        row("CHAPTER FOUR RESULTS. The results are presented narratively.", 2, 4, "Results"),
    ]
    issues = thorough_review_deterministic_issues(rows, academic_level="MPhil", research_approach="qualitative")
    text = "\n".join(str(item) for item in issues).lower()
    assert "trustworthiness" in text or "coding" in text
    assert "r²" not in text
    assert "process model" not in text
