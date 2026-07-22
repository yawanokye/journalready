from pathlib import Path


def test_vprof_name_is_wrapped_for_blue_colour():
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    assert "<h1>Hello!</h1>" in html
    assert '<span class="v-prof-name">V-Prof {{ user.full_name }}</span>' in html
    assert "your Co-Academic Supervision and Assessment Assistant." in html


def test_only_vprof_name_uses_hero_blue():
    css = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert ".hero h1{color:var(--ink)}" in css
    assert ".v-prof-name{" in css
    assert "color:var(--hero-heading);" in css
