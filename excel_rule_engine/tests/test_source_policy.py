"""Configured authority must resolve source choice without weakening parsing."""
import json
from pathlib import Path

import pandas as pd
import pytest
from app.services import conversation_reporting as service


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / 'demo'
    source = root / 'input'
    source.mkdir(parents=True)
    output = root / 'output'
    output.mkdir()
    pd.DataFrame({'employee_id': ['I1', 'I2'], 'name': ['An', 'Binh'],
                  'department': ['IT', 'IT'], 'salary': [20_000_000, 30_000_000]}).to_csv(source / 'special.csv', index=False)
    pd.DataFrame({'employee_id': ['E1', 'E2'], 'name': ['An', 'Chi'],
                  'department': ['IT', 'HR'], 'salary': [99_000_000, 10_000_000]}).to_csv(source / 'general.csv', index=False)
    policy = root / 'source_policy.json'
    policy.write_text(json.dumps({'version': 1, 'department_sources': {'IT': 'special.csv'}}), encoding='utf-8')
    monkeypatch.setattr(service, 'safe_output_path', lambda project, name: output / name)
    return source, output, policy


def test_department_runs_immediately_and_keeps_evidence(project):
    source, output, _ = project
    response = service.automatic_request(source, 'demo', 'Liet ke nhan vien phong ban IT')
    assert response['status'] == 'ready', response
    result = response['result']
    assert result['source_file'] == 'special.csv'
    assert [r['name'] for r in result['detail_preview']] == ['An', 'Binh']
    assert result['total_rows'] == 2
    assert 'cau hinh' in result['selection_reason']
    assert len(list(output.iterdir())) == 1


def test_ranking_uses_configured_department_not_other_salary(project):
    source, _, _ = project
    response = service.automatic_request(source, 'demo', 'nhan vien phong ban IT luong cao nhat')
    assert response['status'] == 'ready', response
    assert response['result']['summary'][0]['name'] == 'Binh'


def test_explicit_choice_overrides_policy(project):
    source, _, _ = project
    result = service.automatic_request(source, 'demo', 'liet ke nhan vien phong ban IT', 'general.csv')['result']
    assert result['source_file'] == 'general.csv'
    assert result['total_rows'] == 1


@pytest.mark.parametrize('text', ['nhan vien luong cao nhat',
                                  'liet ke nhan vien phong ban IT sau thue'])
def test_policy_never_discards_unknown_or_missing_scope(project, text):
    source, output, _ = project
    response = service.automatic_request(source, 'demo', text)
    assert response['status'] == 'requires_input'
    assert not list(output.iterdir())


def test_missing_config_preserves_safe_ambiguity(project):
    source, output, policy = project
    policy.unlink()
    assert service.automatic_request(source, 'demo', 'liet ke nhan vien phong ban IT')['status'] == 'requires_input'
    assert not list(output.iterdir())


def test_stale_config_does_not_fall_back(project):
    source, output, policy = project
    policy.write_text('{"version":1,"department_sources":{"IT":"gone.csv"}}', encoding='utf-8')
    assert service.automatic_request(source, 'demo', 'liet ke nhan vien phong ban IT')['status'] == 'requires_input'
    assert not list(output.iterdir())


@pytest.mark.parametrize('contents', ['{', '{"version":2}', '{"version":1,"department_sources":{"IT":"../other.csv"}}'])
def test_invalid_policy_never_executes(project, contents):
    source, output, policy = project
    policy.write_text(contents, encoding='utf-8')
    with pytest.raises(ValueError):
        service.automatic_request(source, 'demo', 'liet ke nhan vien phong ban IT')
    assert not list(output.iterdir())


def test_demo_exact_screenshot_chooses_it():
    source = Path(__file__).resolve().parents[1] / 'projects/demo_project/input'
    plan = service.preview_request(source, 'Li\u1ec7t k\u00ea nh\u00e2n vi\u00ean ph\u00f2ng ban IT')
    assert plan['status'] == 'ready', plan
    assert plan['source'] == 'Employees_IT.xlsx'
    assert plan['source_policy']['department'] == 'IT'
