from pathlib import Path

def test_login_template_contains_role_tabs():
    html = Path("app/templates/login.html").read_text(encoding="utf-8")
    assert 'href="/login"' in html
    assert 'href="/admin/login"' in html
    assert "Supervisor" in html
    assert "Admin" in html
    assert "access-role-tabs" in html

def test_access_styles_are_present():
    css = Path("app/static/styles.css").read_text(encoding="utf-8")
    assert ".access-header" in css
    assert ".access-role-tab.active" in css
    assert ".access-login-card" in css
