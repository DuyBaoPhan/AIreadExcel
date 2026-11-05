"""Tests run offline, independent of a developer's private .env credentials."""
import os
import pytest

# Set before application imports load dotenv during test collection.
os.environ['REPORT_PLANNER'] = 'openai'
os.environ['FILE_STORAGE_BACKEND'] = 'local'


@pytest.fixture(autouse=True)
def offline_test_settings(monkeypatch):
    monkeypatch.setenv('REPORT_PLANNER', 'openai')
    monkeypatch.setenv('FILE_STORAGE_BACKEND', 'local')
    for name in ('SUPABASE_URL', 'SUPABASE_SECRET_KEY', 'SUPABASE_SERVICE_ROLE_KEY', 'SUPABASE_STORAGE_BUCKET'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    def no_network(*args, **kwargs):
        raise AssertionError('Live HTTP is disabled in tests; mock the provider explicitly.')
    monkeypatch.setattr('requests.sessions.Session.request', no_network)
