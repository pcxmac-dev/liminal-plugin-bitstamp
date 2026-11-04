"""Fakes and guards copied from liminal's tests/conftest.py: tests never read the user's real keys
or limits, and never send a request (a FakeSession answers)."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def no_saved_keys(monkeypatch):
    """Tests never read the user's saved keys (their user environment variables)."""
    from liminal_libs import config

    monkeypatch.setattr(config, "saved_user_keys", lambda: {})


@pytest.fixture(autouse=True)
def no_found_limits(monkeypatch):
    """Nor the limits kept from the user's last capability scans (in their database)."""
    from liminal_libs.sources import registry

    monkeypatch.setattr(registry, "found_limits", lambda name, settings: [])


class FakeResponse:
    def __init__(self, status: int = 200, body=None, headers: dict | None = None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.text = str(body)

    def json(self):
        return self._body


class FakeSession:
    """Returns queued responses and records every request."""

    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict | None, dict]] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        return self.responses.pop(0)
