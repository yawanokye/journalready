from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app import main as main_module


def test_stalled_record_uses_stage_activity(monkeypatch):
    old = datetime.now(timezone.utc) - timedelta(seconds=main_module.STAGE_STALE_AFTER_SECONDS + 5)
    record = SimpleNamespace(status="processing", current_stage="external-evidence-x", started_at=old, created_at=old)
    monkeypatch.setattr(main_module, "_stage_last_activity", lambda db, row: old)
    assert main_module._is_stalled_record(object(), record) is True


def test_portal_exposes_stalled_recovery_action():
    html = (main_module.BASE_DIR + "/templates/portal.html")
    text = open(html, encoding="utf-8").read()
    assert "recover-stalled" in text
    assert "Recover stalled stage" in text


def test_external_stage_timeout_is_configurable(monkeypatch):
    monkeypatch.setenv("AI_EXTERNAL_ASSESSMENT_STAGE_TIMEOUT_SECONDS", "900")
    from app.ai_config import HybridAIConfig
    config = HybridAIConfig.from_env()
    assert config.external_assessment_stage_timeout_seconds == 900
