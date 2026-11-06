"""API tests must never start a worker against business data or paid providers."""

import pytest

from app.conf.config import settings


@pytest.fixture(autouse=True)
def disable_automatic_worker(monkeypatch):
    monkeypatch.setattr(settings, "TASK_WORKER_ENABLED", False)
