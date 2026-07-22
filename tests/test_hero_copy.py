from pathlib import Path


def test_current_hero_copy_is_present():
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    assert "<h1>Hello!</h1>" in html
    assert '<span class="v-prof-name">V-Prof {{ user.full_name }}</span>' in html
    assert "your Co-Academic Supervision and Assessment Assistant." in html
    assert "Meet your academic advisor for your research work" not in html
    assert "Professor provides structured, context-aware thesis review" not in html
