from pathlib import Path

from app.ai_config import HybridAIConfig
from app.academic_ai_engine import _chapter_review_packets


def _section(key: str, chapter: int | None, chars: int = 1000, **extra):
    row = {
        "section_key": key,
        "heading": key,
        "chapter_number": chapter,
        "section_path": [f"Chapter {chapter}", key] if chapter else [key],
        "paragraphs": [{"text": "x" * chars}],
    }
    row.update(extra)
    return row


def test_chapter_packets_do_not_mix_chapters():
    packets = _chapter_review_packets(
        [
            _section("s1", 1),
            _section("s2", 1),
            _section("s3", 2),
            _section("s4", 2),
        ],
        120000,
    )
    assert [[item["section_key"] for item in packet] for packet in packets] == [
        ["s1", "s2"],
        ["s3", "s4"],
    ]


def test_long_chapter_splits_only_at_section_boundaries():
    packets = _chapter_review_packets(
        [_section("s1", 1, 8000), _section("s2", 1, 8000)],
        10000,
    )
    assert len(packets) == 2
    assert packets[0][0]["section_key"] == "s1"
    assert packets[1][0]["section_key"] == "s2"


def test_synthetic_audits_remain_separate():
    packets = _chapter_review_packets(
        [
            _section("s1", 1),
            _section("audit", None, alignment_audit=True),
            _section("s2", 2),
        ],
        120000,
    )
    assert len(packets) == 3
    assert packets[1][0]["section_key"] == "audit"


def test_fast_chapter_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    for name in (
        "AI_CHAPTER_REVIEW_CONCURRENCY",
        "AI_CHAPTER_PACKET_MAX_CHARS",
        "AI_CHAPTER_RECOVERY_CONCURRENCY",
        "AI_CHAPTER_RECOVERY_MAX_OUTPUT_TOKENS",
        "AI_VERIFICATION_BATCH_SIZE",
    ):
        monkeypatch.delenv(name, raising=False)
    config = HybridAIConfig.from_env()
    assert config.chapter_review_concurrency == 2
    assert config.chapter_packet_max_chars == 60000
    assert config.chapter_recovery_concurrency == 2
    assert config.chapter_recovery_max_output_tokens == 7000
    assert config.verification_batch_size == 12


def test_old_three_stage_section_recovery_removed():
    source = Path("app/academic_ai_engine.py").read_text(encoding="utf-8")
    assert "academic-review-v2.5.0-isolated-generic-natural-evidence-ledger" in source
    assert "chapter_packet_coverage_recovery" in source
    assert "single_chapter_packet_retry" in source
    assert "academic-focused-section-recovery-v1.9.2" not in source
