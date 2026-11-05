"""Offline regressions for durable reports and cross-instance downloads."""
import asyncio
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
from openpyxl import Workbook
from app.services.reports import report_storage, conversation_reporting
from app.services.sources import shared_storage


def test_workbook_shared_insert_and_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    upload = Mock(side_effect=shared_storage.StorageError('Storage unavailable'))
    monkeypatch.setattr(shared_storage, 'upload_file', upload)
    target = tmp_path / 'report.xlsx'
    with pytest.raises(ValueError, match='unavailable'):
        report_storage.save_workbook(Workbook(), target)
    assert target.read_bytes().startswith(b'PK')
    upload.assert_called_once_with(target, overwrite=False)
    with pytest.raises(FileExistsError):
        report_storage.save_workbook(Workbook(), target)
    assert upload.call_count == 1


def test_local_workbook_preserves_existing_behavior(tmp_path, monkeypatch):
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: False)
    upload = Mock()
    monkeypatch.setattr(shared_storage, 'upload_file', upload)
    target = tmp_path / 'report.xlsx'
    target.write_bytes(b'old')
    report_storage.save_workbook(Workbook(), target)
    assert target.read_bytes().startswith(b'PK')
    assert report_storage.persist_wizard_report(b'PK', 'Wizard.xlsx') == 'Wizard.xlsx'
    upload.assert_not_called()


def test_conversation_remote_collision_retries_before_success(tmp_path, monkeypatch):
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    upload = Mock(side_effect=[FileExistsError('Duplicate'), None])
    monkeypatch.setattr(shared_storage, 'upload_file', upload)
    monkeypatch.setattr(conversation_reporting, 'safe_output_path', lambda project, name: tmp_path / name)
    frame = pd.DataFrame({'amount': [10, 20]})
    plan = {'source': 'a.csv', 'config': {'version': 1}, 'warnings': [],
            'available_sources': ['a.csv'], 'fingerprint': 'snapshot'}
    result = conversation_reporting._render_report(plan, {'a.csv': frame}, 'demo', None)
    assert upload.call_count == 2
    assert Path(result['output_path']) == upload.call_args.args[0]
    assert len(list(tmp_path.glob('*.xlsx'))) == 2


def test_wizard_uploads_before_offering_filename(tmp_path, monkeypatch):
    from app.services.sources import file_manager
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    monkeypatch.setattr(file_manager, 'safe_output_path', lambda project, name: tmp_path / name)
    upload = Mock()
    monkeypatch.setattr(shared_storage, 'upload_file', upload)
    name = report_storage.persist_wizard_report(b'workbook', 'Wizard.xlsx', 'demo')
    assert (tmp_path / name).read_bytes() == b'workbook'
    upload.assert_called_once_with(tmp_path / name, overwrite=False)


def test_download_materializes_missing_cache_and_fails_closed(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, 'get_output_dir', lambda project: tmp_path)
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    def materialize(path):
        path.write_bytes(b'remote workbook')
    download = Mock(side_effect=materialize)
    monkeypatch.setattr(shared_storage, 'download_file', download)
    response = asyncio.run(main.download_file('demo', 'report.xlsx'))
    assert Path(response.path).read_bytes() == b'remote workbook'
    download.side_effect = shared_storage.StorageError('Storage unavailable')
    with pytest.raises(main.HTTPException) as error:
        asyncio.run(main.download_file('demo', 'report.xlsx'))
    assert error.value.status_code == 503
    download.side_effect = FileNotFoundError()
    with pytest.raises(main.HTTPException) as error:
        asyncio.run(main.download_file('demo', 'report.xlsx'))
    assert error.value.status_code == 404


def test_output_listing_syncs_before_listing(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, 'get_output_dir', lambda project: tmp_path)
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    (tmp_path / 'unpublished.xlsx').write_bytes(b'failed upload')
    monkeypatch.setattr(shared_storage, 'list_objects', lambda folder: ['remote.xlsx'])
    sync = Mock(side_effect=lambda folder: (folder / 'remote.xlsx').write_bytes(b'data'))
    monkeypatch.setattr(shared_storage, 'sync_folder', sync)
    result = asyncio.run(main.get_files('demo', 'output'))
    assert [item['name'] for item in result['files']] == ['remote.xlsx']
    sync.assert_called_once_with(tmp_path)


def test_wizard_never_returns_filename_after_upload_failure(tmp_path, monkeypatch):
    from app.services.sources import file_manager
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    monkeypatch.setattr(file_manager, 'safe_output_path', lambda project, name: tmp_path / name)
    monkeypatch.setattr(shared_storage, 'upload_file', Mock(side_effect=shared_storage.StorageError('Storage unavailable')))
    with pytest.raises(shared_storage.StorageError):
        report_storage.persist_wizard_report(b'workbook', 'Wizard.xlsx', 'demo')
    assert len(list(tmp_path.glob('*.xlsx'))) == 1


@pytest.mark.parametrize('comparison', [False, True])
def test_legacy_excel_writers_upload_completed_workbooks(tmp_path, monkeypatch, comparison):
    from app.services.excel.excel_writer import write_excel, write_comparison_excel
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    upload = Mock()
    monkeypatch.setattr(shared_storage, 'upload_file', upload)
    target = tmp_path / 'legacy.xlsx'
    frame = pd.DataFrame({'amount': [10]})
    if comparison:
        write_comparison_excel(frame, frame, frame, target)
    else:
        write_excel(frame, target)
    assert target.read_bytes().startswith(b'PK')
    upload.assert_called_once_with(target, overwrite=False)


def test_shared_report_snapshot_ignores_stale_cache(tmp_path, monkeypatch):
    (tmp_path / 'fresh.csv').write_bytes(b'amount\n1\n')
    (tmp_path / 'local_only.csv').write_bytes(b'amount\n999\n')
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    monkeypatch.setattr(shared_storage, 'list_objects', lambda folder: ['fresh.csv'])
    remote = Mock(return_value=b'amount\n42\n')
    monkeypatch.setattr(shared_storage, 'read_bytes', remote)
    frames, snapshots, names, warnings = conversation_reporting._load_sources(tmp_path, None)
    assert names == ['fresh.csv']
    assert frames['fresh.csv']['amount'].tolist() == [42]
    assert snapshots['fresh.csv'] == b'amount\n42\n'
    assert not warnings
    remote.assert_called_once_with(tmp_path / 'fresh.csv')
    remote.return_value = b'amount\n43\n'
    assert conversation_reporting._load_sources(tmp_path, None)[1]['fresh.csv'] != snapshots['fresh.csv']


def test_shared_report_snapshot_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    monkeypatch.setattr(shared_storage, 'list_objects', lambda folder: ['fresh.csv'])
    monkeypatch.setattr(shared_storage, 'read_bytes', lambda path: b'amount\n42\n')
    monkeypatch.setattr(conversation_reporting, 'MAX_SOURCE_BYTES', 5)
    with pytest.raises(ValueError, match='40 MB'):
        conversation_reporting._load_sources(tmp_path, None)


def test_shared_rag_snapshot_ignores_stale_cache(tmp_path, monkeypatch):
    from app.services.ai import rag_index
    (tmp_path / 'fresh.csv').write_bytes(b'amount\n1\n')
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    monkeypatch.setattr(shared_storage, 'list_objects', lambda folder: ['fresh.csv'])
    remote = Mock(return_value=b'amount\n42\n')
    monkeypatch.setattr(shared_storage, 'read_bytes', remote)
    _, first, contents = rag_index._snapshot(tmp_path, None)
    assert contents == [('fresh.csv', b'amount\n42\n')]
    remote.return_value = b'amount\n43\n'
    assert rag_index._snapshot(tmp_path, None)[1] != first
    monkeypatch.setattr(rag_index, 'MAX_TOTAL_BYTES', 5)
    with pytest.raises(rag_index.RetrievalError, match='40 MB'):
        rag_index._snapshot(tmp_path, None)


def test_shared_report_storage_errors_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(shared_storage, 'is_enabled', lambda: True)
    monkeypatch.setattr(shared_storage, 'list_objects', lambda folder: ['fresh.csv'])
    remote = Mock(side_effect=shared_storage.StorageError('unavailable'))
    monkeypatch.setattr(shared_storage, 'read_bytes', remote)
    with pytest.raises(shared_storage.StorageError):
        conversation_reporting._load_sources(tmp_path, None)
    remote.side_effect = FileNotFoundError()
    with pytest.raises(ValueError, match='thay doi'):
        conversation_reporting._load_sources(tmp_path, None)
