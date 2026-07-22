from __future__ import annotations

from app.coverage_review import build_coverage_ledger, build_coverage_units, coverage_packets
from app.ai_prompts import ACADEMIC_REVIEW_SYSTEM_PROMPT, LIGHT_REVIEW_SYSTEM_PROMPT


def _paragraph(number: int, text: str, *, chapter: int = 1, heading: str = "Background", kind: str = "paragraph", table_index=None):
    return {
        "paragraph": number,
        "text": text,
        "chapter_number": chapter,
        "heading": heading,
        "section_path": [heading],
        "is_heading": False,
        "document_role": "current",
        "source_kind": kind,
        "table_index": table_index,
        "table_row": number if table_index is not None else None,
        "table_number": "4" if table_index is not None else "",
        "table_title": "Regression Results" if table_index is not None else "",
    }


def test_every_substantive_paragraph_is_targeted_once():
    rows = [_paragraph(i, f"Paragraph {i} has substantive academic content.") for i in range(1, 18)]
    units = build_coverage_units(rows, prose_paragraphs_per_unit=5, context_paragraphs=1)
    targets = [pid for unit in units for pid in unit["target_paragraph_ids"]]
    assert targets == [f"P{i}" for i in range(1, 18)]
    assert len(targets) == len(set(targets))
    assert all(unit["coverage_unit"] for unit in units)


def test_table_rows_are_separate_high_risk_coverage_units():
    rows = [_paragraph(1, "Narrative paragraph.")]
    rows.extend(_paragraph(i, f"Table row {i}: B=.2 SE=.1", chapter=4, heading="Results", kind="table_row", table_index=1) for i in range(2, 15))
    units = build_coverage_units(rows, prose_paragraphs_per_unit=5, table_rows_per_unit=5)
    table_units = [unit for unit in units if unit["coverage_unit_kind"] == "table"]
    assert len(table_units) == 3
    assert all("Table 4" in unit["heading"] for unit in table_units)
    packets = coverage_packets(units, max_units_per_request=4, high_risk_units_per_request=1)
    assert all(len(packet) == 1 for packet in packets if any(unit["coverage_unit_kind"] == "table" for unit in packet))


def test_coverage_ledger_requires_all_targets_and_has_no_comment_quota():
    rows = [_paragraph(i, f"Paragraph {i}.") for i in range(1, 6)]
    units = build_coverage_units(rows, prose_paragraphs_per_unit=3)
    for idx, unit in enumerate(units, start=1):
        unit["section_key"] = f"S{idx:03d}P01"
    reviews = [
        {
            "section_key": unit["section_key"],
            "assessed_paragraph_ids": list(unit["target_paragraph_ids"]),
            "issues": [] if idx == 0 else [{"finding_id": "F1"}],
            "strengths": [],
        }
        for idx, unit in enumerate(units)
    ]
    ledger = build_coverage_ledger(units, reviews)
    assert ledger["complete"] is True
    assert ledger["target_coverage_percent"] == 100.0
    assert ledger["target_count"] == 5
    assert sum(entry["issue_count"] for entry in ledger["entries"]) == 1


def test_prompts_remove_predetermined_comment_limits():
    combined = (ACADEMIC_REVIEW_SYSTEM_PROMPT + LIGHT_REVIEW_SYSTEM_PROMPT).lower()
    assert "no predetermined minimum or maximum number of comments" in combined
    assert "normally report no more than three" not in combined
    assert "assessed_paragraph_ids" in combined
