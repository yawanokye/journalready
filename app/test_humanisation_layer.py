from app.article_service import _apply_strong_article_humanisation


def _sample_article() -> str:
    return """# Introduction

This study shows that the policy has an important role in institutional performance, but the current evidence remains fragmented across sectors and periods, while the available estimates also depend on model specification and the quality of the underlying administrative records. This study shows that the interpretation should remain cautious because the design is observational and the reported relationship may reflect omitted institutional differences. This study shows that additional robustness checks would strengthen the claim. Several additional observations are included here so the paragraph is long enough for the strong lexical and sentence-rhythm pass to operate without changing confirmed factual evidence.

| Variable | Value |
|---|---|
| beta | 0.42 |

The estimate was statistically significant (Adam, 2020), and the coefficient was 0.42. [confirm confidence interval]

$$
Yᵢ = β₀ + β₁Xᵢ + εᵢ
$$

## References

Adam, A. M. (2020). Sample size determination in survey research.
"""


def test_strong_humanisation_is_deterministic_and_changes_prose(monkeypatch):
    monkeypatch.setenv("ARTICLEREADY_STRONG_HUMANISATION", "1")
    monkeypatch.setenv("ARTICLEREADY_HUMANISATION_STRENGTH", "strong")
    source = _sample_article()
    first = _apply_strong_article_humanisation(source, seed_text="same-seed")
    second = _apply_strong_article_humanisation(source, seed_text="same-seed")
    assert first == second
    assert first != source


def test_strong_humanisation_protects_evidence_and_structure(monkeypatch):
    monkeypatch.setenv("ARTICLEREADY_STRONG_HUMANISATION", "1")
    output = _apply_strong_article_humanisation(_sample_article(), seed_text="protection")
    assert "| beta | 0.42 |" in output
    assert "(Adam, 2020)" in output
    assert "[confirm confidence interval]" in output
    assert "Yᵢ = β₀ + β₁Xᵢ + εᵢ" in output
    assert "Adam, A. M. (2020). Sample size determination in survey research." in output


def test_strong_humanisation_can_be_disabled(monkeypatch):
    monkeypatch.setenv("ARTICLEREADY_STRONG_HUMANISATION", "0")
    source = _sample_article()
    assert _apply_strong_article_humanisation(source, seed_text="disabled") == source
