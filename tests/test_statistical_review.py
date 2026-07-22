from app.statistical_review import audit_statistical_consistency, build_statistical_review


def row(text, paragraph=1, chapter=4, heading="4.2 Results"):
    return {
        "text": text,
        "paragraph": paragraph,
        "page": 10,
        "chapter_number": chapter,
        "heading": heading,
        "section_number": "4.2",
        "source_kind": "paragraph",
    }


def test_invalid_and_contradictory_statistics_are_flagged():
    rows = [
        row("The model reported R-squared = 1.24.", 1),
        row("The effect was significant, p = 0.71.", 2),
        row("The coefficient = -0.42 showed a positive relationship.", 3),
        row("The response rate was 121%.", 4),
        row("The 95% CI was (0.80, 0.20).", 5),
    ]
    kinds = {warning["kind"] for warning in audit_statistical_consistency(rows)}
    assert "invalid_r_squared" in kinds
    assert "p_value_interpretation_mismatch" in kinds
    assert "coefficient_sign_interpretation_mismatch" in kinds
    assert "invalid_percentage" in kinds
    assert "reversed_confidence_interval" in kinds


def test_diagnostic_inventory_detects_model_checks():
    review = build_statistical_review(
        [row("Multicollinearity was assessed using VIF and heteroscedasticity was tested using the Breusch-Pagan test.")],
        chapter_numbers=[4],
    )
    assert review["diagnostic_inventory"]["any_diagnostics_present"] is True
