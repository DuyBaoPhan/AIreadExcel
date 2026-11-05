"""Configured authority must resolve source choice without weakening parsing."""
import json
from pathlib import Path

import pandas as pd
import pytest
from app.services.reports import conversation_reporting as service
from .test_openai_planner import mock_response


def detail_plan(source="special.csv", *, ranking=False):
    """Finite provider fixture; real backend validates source policy and executes rows."""
    return {"status": "ready", "source": source, "config": {
        "version": 1, "filters": [{"column": "department", "operator": "eq",
                                  "type": "text", "value": "IT"}],
        "filter_logic": "and", "group_by": [], "metrics": [], "date_group": None,
        "top_n": {"column": "salary", "n": 1, "ascending": False, "offset": 0,
                  "scope": "detail"} if ranking else None},
        "explanation": [], "questions": [], "unsupported": []}


@pytest.fixture(autouse=True)
def ai_mode(monkeypatch):
    monkeypatch.setenv("REPORT_PLANNER", "openai")


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


def test_department_runs_immediately_and_keeps_evidence(project, monkeypatch):
    calls = mock_response(monkeypatch, detail_plan())
    source, output, _ = project
    response = service.automatic_request(source, 'demo', 'Liet ke nhan vien phong ban IT')
    assert response['status'] == 'ready', response
    result = response['result']
    assert result['source_file'] == 'special.csv'
    assert [r['name'] for r in result['detail_preview']] == ['An', 'Binh']
    assert result['total_rows'] == 2
    assert result['planner'] == 'openai'
    assert result['evidence']['config']['filters'][0]['value'] == 'IT'
    metadata = json.loads(calls[0][1]['json']['messages'][1]['content'])
    assert metadata['source_policy']['department_sources'] == {'IT': 'special.csv'}
    assert len(list(output.iterdir())) == 1


def test_ranking_uses_configured_department_not_other_salary(project, monkeypatch):
    mock_response(monkeypatch, detail_plan(ranking=True))
    source, _, _ = project
    response = service.automatic_request(source, 'demo', 'nhan vien phong ban IT luong cao nhat')
    assert response['status'] == 'ready', response
    assert response['result']['detail_preview'][0]['name'] == 'Binh'


def test_explicit_choice_overrides_policy(project, monkeypatch):
    mock_response(monkeypatch, detail_plan("general.csv"))
    source, _, _ = project
    result = service.automatic_request(source, 'demo', 'liet ke nhan vien phong ban IT', 'general.csv')['result']
    assert result['source_file'] == 'general.csv'
    assert result['total_rows'] == 1


@pytest.mark.parametrize('text', ['nhan vien luong cao nhat',
                                  'liet ke nhan vien phong ban IT sau thue'])
def test_policy_never_discards_unknown_or_missing_scope(project, text, monkeypatch):
    plan = detail_plan()
    if text == "nhan vien luong cao nhat":
        plan["config"]["filters"] = []
    else:
        plan.update(status="unsupported", source=None, config=None,
                    unsupported=["Chua ho tro tinh luong sau thue."])
    mock_response(monkeypatch, plan)
    source, output, _ = project
    response = service.automatic_request(source, 'demo', text)
    assert response['status'] == 'requires_input'
    assert not list(output.iterdir())


def test_missing_config_preserves_safe_ambiguity(project, monkeypatch):
    mock_response(monkeypatch, detail_plan())
    source, output, policy = project
    policy.unlink()
    assert service.automatic_request(source, 'demo', 'liet ke nhan vien phong ban IT')['status'] == 'requires_input'
    assert not list(output.iterdir())


def test_stale_config_does_not_fall_back(project, monkeypatch):
    calls = mock_response(monkeypatch, detail_plan())
    source, output, policy = project
    policy.write_text('{"version":1,"department_sources":{"IT":"gone.csv"}}', encoding='utf-8')
    with pytest.raises(ValueError, match='Invalid source policy'):
        service.automatic_request(source, 'demo', 'liet ke nhan vien phong ban IT')
    assert not calls
    assert not list(output.iterdir())


@pytest.mark.parametrize('contents', ['{', '{"version":2}', '{"version":1,"department_sources":{"IT":"../other.csv"}}'])
def test_invalid_policy_never_executes(project, contents, monkeypatch):
    calls = mock_response(monkeypatch, detail_plan())
    source, output, policy = project
    policy.write_text(contents, encoding='utf-8')
    with pytest.raises(ValueError):
        service.automatic_request(source, 'demo', 'liet ke nhan vien phong ban IT')
    assert not calls
    assert not list(output.iterdir())


def test_demo_exact_screenshot_chooses_it(monkeypatch):
    calls = mock_response(monkeypatch, detail_plan("Employees_IT.xlsx"))
    source = Path(__file__).resolve().parents[1] / 'projects/demo_project/input'
    plan = service.preview_request(source, 'Li\u1ec7t k\u00ea nh\u00e2n vi\u00ean ph\u00f2ng ban IT')
    assert plan['status'] == 'ready', plan
    assert plan['source'] == 'Employees_IT.xlsx'
    metadata = json.loads(calls[0][1]['json']['messages'][1]['content'])
    assert metadata['source_policy']['department_sources']['IT'] == 'Employees_IT.xlsx'
    assert plan['config']['filters'][0]['value'] == 'IT'
