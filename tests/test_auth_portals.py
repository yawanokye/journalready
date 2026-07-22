from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_supervisor_auth.db")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "AdminPass123!")
os.environ.setdefault("REVIEW_STORAGE_DIR", "./test_review_storage")

from fastapi.testclient import TestClient
from app.main import app


def csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def test_admin_creates_lecturer_and_lecturer_logs_in() -> None:
    with TestClient(app) as client:
        page = client.get("/admin/login")
        response = client.post(
            "/admin/login",
            data={"username": "admin", "password": "AdminPass123!", "csrf_token": csrf(page.text)},
            follow_redirects=False,
        )
        assert response.status_code == 303

        page = client.get("/account/password")
        client.post(
            "/account/password",
            data={
                "current_password": "AdminPass123!",
                "new_password": "NewAdmin123!",
                "confirm_password": "NewAdmin123!",
                "csrf_token": csrf(page.text),
            },
        )

        page = client.get("/admin")
        client.post(
            "/admin/lecturers",
            data={
                "full_name": "Test Lecturer",
                "username": "test.lecturer",
                "department": "Graduate School",
                "email": "",
                "phone": "",
                "csrf_token": csrf(page.text),
            },
            follow_redirects=False,
        )
        page = client.get("/admin")
        password = re.search(r'<span>Temporary password</span><strong>([^<]+)</strong>', page.text).group(1)
        assert "test.lecturer" in page.text

        client.post("/logout", data={"csrf_token": csrf(page.text)})
        page = client.get("/login")
        response = client.post(
            "/login",
            data={"username": "test.lecturer", "password": password, "csrf_token": csrf(page.text)},
            follow_redirects=False,
        )
        assert response.headers["location"] == "/account/password"
