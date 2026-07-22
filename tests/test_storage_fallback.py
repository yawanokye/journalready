from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


def test_storage_falls_back_when_configured_path_is_unwritable(tmp_path, monkeypatch):
    monkeypatch.setenv("REVIEW_STORAGE_DIR", "/proc/projectready-supervisor/reviews")
    fallback = tmp_path / "reviews"
    monkeypatch.setenv("REVIEW_STORAGE_FALLBACK_DIR", str(fallback))

    sys.modules.pop("app.storage", None)
    storage = importlib.import_module("app.storage")

    selected = storage.ensure_storage()
    assert selected == fallback
    assert selected.exists()

    storage.save_review_json("review-1", {"ok": True})
    assert storage.load_review_json("review-1") == {"ok": True}
