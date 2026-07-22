from pathlib import Path


def test_reference_blue_is_reserved_for_vprof_name():
    css = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert "--hero-heading:#4557d5;" in css
    assert ".hero h1{color:var(--ink)}" in css
    assert ".v-prof-name{" in css
    assert "color:var(--hero-heading);" in css
