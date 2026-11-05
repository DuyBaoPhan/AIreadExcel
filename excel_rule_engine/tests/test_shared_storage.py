"""Offline contract tests for private Supabase storage and cache safety."""
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from app.services.sources import file_manager, shared_storage as storage
from app.services.sources.source_uploads import save_source


@pytest.fixture
def remote(monkeypatch, tmp_path):
    monkeypatch.setenv('FILE_STORAGE_BACKEND', 'supabase')
    monkeypatch.setenv('SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_SECRET_KEY', 'sb_secret_test-not-a-real-secret')
    monkeypatch.setenv('SUPABASE_STORAGE_BUCKET', 'private-files')
    monkeypatch.setattr(file_manager, '_PROJECTS_ROOT', tmp_path)
    folder = tmp_path / '.shared-cache' / 'demo' / 'input'
    folder.mkdir(parents=True)
    return folder


def response(body=None, content=b'', status=200):
    return Mock(status_code=status, content=content, json=Mock(return_value=body))


def test_local_default_no_network(monkeypatch, tmp_path):
    monkeypatch.delenv('FILE_STORAGE_BACKEND', raising=False)
    request = Mock(side_effect=AssertionError('network forbidden'))
    monkeypatch.setattr(storage.requests, 'request', request)
    storage.sync_folder(tmp_path)
    storage.upload_file(tmp_path / 'absent.csv')
    assert not storage.is_enabled()
    request.assert_not_called()


def test_no_fallback_invalid_config(monkeypatch):
    monkeypatch.setenv('FILE_STORAGE_BACKEND', 'supabase')
    monkeypatch.delenv('SUPABASE_URL', raising=False)
    with pytest.raises(storage.StorageError):
        storage.is_enabled()


def test_upload_key_private_auth_and_timeout(remote, monkeypatch):
    request = Mock(return_value=response())
    monkeypatch.setattr(storage.requests, 'request', request)
    path = remote / 'source.csv'
    storage.upload_bytes(path, b'a\n1\n')
    args, kwargs = request.call_args
    assert args[:2] == ('POST', 'https://example.supabase.co/storage/v1/object/private-files/projects/demo/input/source.csv')
    assert 'Authorization' not in kwargs['headers']
    assert kwargs['headers']['x-upsert'] == 'false'
    assert kwargs['timeout'] == (10, 60)
    assert kwargs['allow_redirects'] is False


def test_legacy_auth(remote, monkeypatch):
    monkeypatch.setenv('SUPABASE_SECRET_KEY', '')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'legacy-test')
    request = Mock(return_value=response())
    monkeypatch.setattr(storage.requests, 'request', request)
    storage.upload_bytes(remote / 'a.csv', b'x')
    assert request.call_args.kwargs['headers']['Authorization'] == 'Bearer legacy-test'


def test_authoritative_sync_removes_only_supported(remote, monkeypatch):
    (remote / 'stale.csv').write_bytes(b'stale')
    (remote / 'notes.txt').write_bytes(b'keep')
    request = Mock(side_effect=[response([{'id': 'id1', 'name': 'new.csv'}]), response(content=b'new')])
    monkeypatch.setattr(storage.requests, 'request', request)
    storage.sync_folder(remote)
    assert (remote / 'new.csv').read_bytes() == b'new'
    assert not (remote / 'stale.csv').exists()
    assert (remote / 'notes.txt').exists()


def test_failed_sync_never_returns_stale_or_changes_cache(remote, monkeypatch):
    (remote / 'old.csv').write_bytes(b'old')
    request = Mock(side_effect=[response([{'id': 'id', 'name': 'new.csv'}]), requests.ConnectionError('SECRET URL TOKEN')])
    monkeypatch.setattr(storage.requests, 'request', request)
    with pytest.raises(storage.StorageError) as error:
        file_manager.get_input_dir('demo')
    assert 'SECRET' not in str(error.value)
    assert (remote / 'old.csv').read_bytes() == b'old'
    assert not (remote / 'new.csv').exists()
    assert not list(remote.glob('.storage-*'))


def test_pagination(remote, monkeypatch):
    first = [{'id': str(i), 'name': f'{i}.csv'} for i in range(100)]
    request = Mock(side_effect=[response(first), response([{'id': 'last', 'name': 'last.csv'}])])
    monkeypatch.setattr(storage.requests, 'request', request)
    assert len(storage.list_objects(remote)) == 101
    assert request.call_args.kwargs['json']['offset'] == 100


@pytest.mark.parametrize('name', ['../outside.csv', 'x/y.csv', 'C:bad.csv', '.', '..'])
def test_remote_names_reject_traversal(remote, monkeypatch, name):
    monkeypatch.setattr(storage.requests, 'request', Mock(return_value=response([{'id': 'id', 'name': name}])))
    with pytest.raises(storage.StorageError):
        storage.sync_folder(remote)


def test_path_mapping_and_traversal(remote):
    assert storage.object_key(remote.parent / 'backups' / 'safe.xlsx') == 'projects/demo/backups/safe.xlsx'
    with pytest.raises(storage.StorageError):
        storage.object_key(remote.parent.parent.parent / 'escape.csv')
    with pytest.raises(ValueError):
        file_manager.get_project_dir('../demo-other')


def test_duplicate(remote, monkeypatch):
    monkeypatch.setattr(storage.requests, 'request', Mock(return_value=response(status=409)))
    with pytest.raises(FileExistsError):
        storage.upload_bytes(remote / 'x.csv', b'x')


def test_upload_failure_leaves_no_local_file(remote, monkeypatch):
    request = Mock(side_effect=[response([]), response(status=503)])
    monkeypatch.setattr(storage.requests, 'request', request)
    with pytest.raises(storage.StorageError):
        save_source(remote, 'new.csv', b'a\n1\n')
    assert list(remote.iterdir()) == []


def test_rpc_strict_boolean(remote, monkeypatch):
    request = Mock(return_value=response(True))
    monkeypatch.setattr(storage.requests, 'request', request)
    assert storage.rpc('acquire_source_update_lock', {'p_object_key': 'x'}) is True
    assert '/rest/v1/rpc/acquire_source_update_lock' in request.call_args.args[1]
    request.return_value = response('true')
    with pytest.raises(storage.StorageError):
        storage.rpc('acquire_source_update_lock', {})


def test_original_local_files_never_pruned(remote, monkeypatch):
    original = file_manager.get_local_projects_root() / 'demo' / 'input'
    original.mkdir(parents=True)
    (original / 'precious.csv').write_bytes(b'original')
    monkeypatch.setattr(storage.requests, 'request', Mock(return_value=response([])))
    storage.sync_folder(remote)
    assert (original / 'precious.csv').read_bytes() == b'original'


def test_output_sync_preserves_unpublished_files(remote, monkeypatch):
    folder = remote.parent / 'output'
    folder.mkdir()
    (folder / 'unpublished.xlsx').write_bytes(b'report')
    monkeypatch.setattr(storage.requests, 'request', Mock(return_value=response([])))
    storage.sync_folder(folder)
    assert (folder / 'unpublished.xlsx').read_bytes() == b'report'
