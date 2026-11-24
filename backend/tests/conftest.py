import os
from pathlib import Path

import pytest


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    from app.storage import projects

    store = projects.ProjectStore(tmp_path / "data")
    monkeypatch.setattr(projects, "store", store)
    return store

