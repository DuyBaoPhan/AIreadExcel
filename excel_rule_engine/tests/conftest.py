"""Tests run offline, independent of a developer's private .env credentials."""
import os
import pytest

# Set before application imports load dotenv during test collection.
os.environ['REPORT_PLANNER'] = 'openai'


@pytest.fixture(autouse=True)
def offline_test_settings(monkeypatch):
    monkeypatch.setenv('REPORT_PLANNER', 'openai')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    def no_network(*args, **kwargs):
        raise AssertionError('Live HTTP is disabled in tests; mock the provider explicitly.')
    monkeypatch.setattr('requests.sessions.Session.request', no_network)
