"""Migration never mutates originals or overwrites authoritative remote files."""
from pathlib import Path
from unittest.mock import Mock
import pytest
from scripts import migrate_supabase_storage as migration


def test_dry_run_has_no_network(tmp_path, monkeypatch):
    monkeypatch.setattr(migration, 'PROJECTS_DIR', tmp_path)
    folder = tmp_path/'demo_project'/'input'
    folder.mkdir(parents=True)
    source = folder/'sample.xlsx'
    source.write_bytes(b'original')
    monkeypatch.setattr(migration.shared_storage, 'is_enabled', Mock(side_effect=AssertionError('no network')))
    assert migration.migrate('demo_project') == 0
    assert source.read_bytes() == b'original'


def test_existing_different_remote_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(migration, 'PROJECTS_DIR', tmp_path)
    folder = tmp_path/'demo_project'/'input'
    folder.mkdir(parents=True)
    (folder/'sample.xlsx').write_bytes(b'original')
    monkeypatch.setattr(migration.shared_storage, 'is_enabled', lambda: True)
    monkeypatch.setattr(migration.file_manager, 'get_projects_root', lambda: tmp_path/'.shared-cache')
    monkeypatch.setattr(migration.shared_storage, 'list_objects', lambda _: ['sample.xlsx'])
    upload = Mock()
    monkeypatch.setattr(migration.shared_storage, 'upload_bytes', upload)
    monkeypatch.setattr(migration.shared_storage, 'read_bytes', lambda _: b'changed remote')
    assert migration.migrate('demo_project', apply=True) == 1
    upload.assert_not_called()
    assert (folder/'sample.xlsx').read_bytes() == b'original'


def test_new_upload_verified_and_backup_relocated(tmp_path, monkeypatch):
    monkeypatch.setattr(migration, 'PROJECTS_DIR', tmp_path)
    folder = tmp_path/'demo_project'/'input'
    folder.mkdir(parents=True)
    (folder/'sample.xlsx.backup-123').write_bytes(b'backup')
    monkeypatch.setattr(migration.shared_storage, 'is_enabled', lambda: True)
    monkeypatch.setattr(migration.file_manager, 'get_projects_root', lambda: tmp_path/'.shared-cache')
    monkeypatch.setattr(migration.shared_storage, 'list_objects', lambda _: [])
    upload = Mock()
    monkeypatch.setattr(migration.shared_storage, 'upload_bytes', upload)
    monkeypatch.setattr(migration.shared_storage, 'read_bytes', lambda _: b'backup')
    assert migration.migrate('demo_project', apply=True) == 0
    path, raw = upload.call_args.args
    assert path.parent.name == 'backups' and raw == b'backup'
    assert upload.call_args.kwargs == {'overwrite': False}


@pytest.mark.parametrize('project', ['..', '../other', 'x/y', 'x\\y'])
def test_invalid_project_rejected(project):
    with pytest.raises(ValueError):
        migration.inventory(project)


def test_cloud_forwards_only_documented_storage_names():
    import ast
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root/'streamlit_app.py').read_text(encoding='utf-8-sig'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == 'name' and isinstance(node.iter, ast.Tuple):
            names.update(item.value for item in node.iter.elts if isinstance(item, ast.Constant))
    assert {'FILE_STORAGE_BACKEND', 'SUPABASE_URL', 'SUPABASE_SECRET_KEY', 'SUPABASE_SERVICE_ROLE_KEY', 'SUPABASE_STORAGE_BUCKET'} <= names
