from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import (
    authenticate,
    hash_secret,
    initialise_admin_from_environment,
)
from app.database import Base, User


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _admin(db, password: str = "OldPassword123!") -> User:
    row = User(
        username="admin",
        password_hash=hash_secret(password),
        role="admin",
        full_name="Administrator",
        is_active=True,
        must_change_password=False,
    )
    db.add(row)
    db.commit()
    return row


def test_existing_admin_is_not_silently_overwritten(monkeypatch):
    db = _session()
    _admin(db)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "NewPassword123!")
    monkeypatch.delenv("VPROF_RESET_ADMIN_PASSWORD_ON_STARTUP", raising=False)

    state = initialise_admin_from_environment(db)

    assert state["reset"] is False
    assert authenticate(db, "admin", "OldPassword123!", required_role="admin")
    assert authenticate(db, "admin", "NewPassword123!", required_role="admin") is None


def test_explicit_startup_flag_resets_existing_admin(monkeypatch):
    db = _session()
    _admin(db)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "NewPassword123!")
    monkeypatch.setenv("VPROF_RESET_ADMIN_PASSWORD_ON_STARTUP", "true")
    monkeypatch.setenv("VPROF_ADMIN_REQUIRE_PASSWORD_CHANGE_AFTER_RESET", "false")

    state = initialise_admin_from_environment(db)

    assert state["reset"] is True
    assert authenticate(db, "admin", "NewPassword123!", required_role="admin")
    assert authenticate(db, "admin", "OldPassword123!", required_role="admin") is None


def test_reset_can_sync_admin_username(monkeypatch):
    db = _session()
    _admin(db)
    monkeypatch.setenv("ADMIN_USERNAME", "system.admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "NewPassword123!")
    monkeypatch.setenv("VPROF_RESET_ADMIN_PASSWORD_ON_STARTUP", "true")

    state = initialise_admin_from_environment(db)

    assert state["username"] == "system.admin"
    assert authenticate(db, "system.admin", "NewPassword123!", required_role="admin")
