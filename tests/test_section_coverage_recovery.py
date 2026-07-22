from pathlib import Path

from app.academic_ai_engine import _section_key


def test_section_keys_are_short_and_stable():
    section = {
        "heading": "INVESTIGATING HOW EFFECTIVE STAKEHOLDER ENGAGEMENT AFFECT PROJECTS OUTCOMES",
        "part": 1,
    }
    assert _section_key(section, 0) == "S001P01"
    assert "STAKEHOLDER" not in _section_key(section, 0)


def test_browser_stops_polling_on_terminal_failure():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "terminalError.terminal = true" in js
    assert "if (error && error.terminal)" in js
