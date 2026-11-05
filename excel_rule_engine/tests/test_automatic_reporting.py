"""Single-snapshot automatic reporting, evidence and HTTP contract regressions."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.reports import conversation_reporting as service
from app.main import app, automatic_conversation_report, ReportPlanRequest


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    source = tmp_path / 'input'
    output = tmp_path / 'output'
    source.mkdir()
    output.mkdir()
    (source / 'sales.csv').write_text('san pham,doanh thu\nA,10\nB,20\n', encoding='utf-8')
    monkeypatch.setattr(service, 'safe_output_path', lambda project, name: output / name)
    return source, output


def test_real_request_reports_without_preview_or_confirm(workspace):
    source, output = workspace
    original = (source / 'sales.csv').read_bytes()
    with patch.object(service, '_load_sources', wraps=service._load_sources) as load, \
         patch.object(service, 'execute_request', side_effect=AssertionError('no confirm pass')):
        response = service.automatic_request(source, 'demo', 'doanh thu theo san pham')
    assert response['status'] == 'ready'
    result = response['result']
    assert result['total_rows'] == 2
    assert result['files_included'] == 1
    assert result['evidence']['matched_rows'] == 2
    assert result['source_selection']['selected_source'] == 'sales.csv'
    assert result['source_selection']['mode'] == 'automatic'
    assert len(list(output.iterdir())) == 1
    assert (source / 'sales.csv').read_bytes() == original
    load.assert_called_once()
    book = pd.ExcelFile(result['output_path'])
    assert book.sheet_names


@pytest.mark.parametrize('text', ['doanh thu theo san pham', 'lam phep thuat voi du lieu'])
def test_ambiguous_and_unsupported_never_fall_back(workspace, text):
    source, output = workspace
    (source / 'other.csv').write_bytes((source / 'sales.csv').read_bytes())
    response = service.automatic_request(source, 'demo', text)
    assert response['status'] == 'requires_input'
    assert response['report_plan']['status'] != 'ready'
    assert 'result' not in response
    assert not list(output.iterdir())


def test_explicit_selection_and_unique_output(workspace):
    source, output = workspace
    (source / 'other.csv').write_text('san pham,doanh thu\nZ,999\n', encoding='utf-8')
    paths = []
    for _ in range(2):
        result = service.automatic_request(source, 'demo', 'doanh thu theo san pham', 'sales.csv')['result']
        assert result['source_selection']['mode'] == 'explicit'
        assert sum(row['RevenueSum'] for row in result['summary']) == 30
        paths.append(result['output_path'])
    assert len(set(paths)) == 2
    assert len(list(output.iterdir())) == 2
    for name in ('../sales.csv', 'missing.csv', 'SALES.csv'):
        with pytest.raises(ValueError):
            service.automatic_request(source, 'demo', 'doanh thu', name)


def test_changed_file_after_plan_uses_original_snapshot(workspace):
    source, output = workspace
    real_planner = service.plan_report
    def change_after_plan(text, frames):
        result = real_planner(text, frames)
        (source / 'sales.csv').write_text('san pham,doanh thu\nZ,999\n', encoding='utf-8')
        return result
    with patch.object(service, 'plan_report', side_effect=change_after_plan) as planner:
        result = service.automatic_request(source, 'demo', 'doanh thu theo san pham')['result']
    assert sum(row['RevenueSum'] for row in result['summary']) == 30
    planner.assert_called_once()


def test_wrong_planner_source_cannot_override_exact_selection(workspace):
    source, output = workspace
    plan = {'status': 'ready', 'source': 'other.csv', 'config': {'version': 1}}
    with patch.object(service, 'plan_report', return_value=plan), pytest.raises(ValueError):
        service.automatic_request(source, 'demo', 'doanh thu', 'sales.csv')
    assert not list(output.iterdir())


@pytest.mark.parametrize('contents', ['san pham,doanh thu\n', 'san pham,doanh thu\nA,\nB,\n'])
def test_absent_evidence_never_exports(workspace, contents):
    source, output = workspace
    (source / 'sales.csv').write_text(contents, encoding='utf-8')
    try:
        response = service.automatic_request(source, 'demo', 'doanh thu theo san pham')
    except ValueError:
        pass
    else:
        assert response['status'] == 'requires_input'
    assert not list(output.iterdir())


def test_malformed_config_is_clean_error(workspace):
    source, output = workspace
    plan = {'status': 'ready', 'source': 'sales.csv', 'config': {'version': 1, 'metrics': [{'operation': 'sum'}]}}
    with patch.object(service, 'plan_report', return_value=plan), pytest.raises(ValueError):
        service.automatic_request(source, 'demo', 'doanh thu')
    assert not list(output.iterdir())


def test_auto_route_contract_and_no_generic_fallback(workspace):
    source, output = workspace
    assert '/api/report/auto' in {route.path for route in app.routes}
    with patch('app.main.get_input_dir', return_value=source), \
         patch('app.main.run_export_report', side_effect=AssertionError('generic fallback')):
        response = asyncio.run(automatic_conversation_report(ReportPlanRequest(text='doanh thu theo san pham')))
    assert response['status'] == 'ready'
    with patch('app.services.reports.conversation_reporting.automatic_request', side_effect=ValueError('bad data')):
        with pytest.raises(HTTPException) as error:
            asyncio.run(automatic_conversation_report(ReportPlanRequest(text='bad')))
    assert error.value.status_code == 400
