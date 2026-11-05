"""OpenAI planning tests use mocked HTTP only; no live credentials/network."""
import copy
import json

import pandas as pd
import pytest
import requests

from app.services import openai_planner as planner


@pytest.fixture
def sources():
    return {'sales.xlsx': pd.DataFrame({'Department': ['SECRET_ROW_VALUE'], 'Revenue': [987654321]})}


@pytest.fixture
def plan():
    return {'status': 'ready', 'source': 'sales.xlsx', 'config': {
        'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': ['Department'],
        'metrics': [{'column': 'Revenue', 'operation': 'sum', 'alias': 'Total'}],
        'date_group': None, 'top_n': None}, 'explanation': ['Sum revenue by department'],
        'questions': [], 'unsupported': []}


def mock_response(monkeypatch, plan, refusal=None):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {'choices': [{'finish_reason': 'stop', 'message': {
                'content': json.dumps(plan), 'refusal': refusal}}]}
    calls = []
    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-private-key')
    monkeypatch.setattr(planner.requests, 'post', post)
    return calls


def test_valid_paraphrase_and_payload_privacy(monkeypatch, sources, plan):
    calls = mock_response(monkeypatch, plan)
    result = planner.plan_with_openai('Please break down our takings by Department', sources)
    assert result['status'] == 'ready'
    assert 'date_group' not in result['config']
    args, kwargs = calls[0]
    assert args == ('https://api.openai.com/v1/chat/completions',)
    assert kwargs['timeout'] == 45
    payload = kwargs['json']
    assert payload['response_format']['json_schema']['strict'] is True
    assert payload['model'] == 'gpt-4.1-mini'
    encoded = json.dumps(payload)
    assert 'SECRET_ROW_VALUE' not in encoded
    assert '987654321' not in encoded
    assert 'fake-private-key' not in encoded
    assert 'row_count' in encoded


@pytest.mark.parametrize('mutation', ['column', 'operation', 'unknown', 'missing', 'status', 'source'])
def test_invalid_plan_rejected(monkeypatch, sources, plan, mutation):
    if mutation == 'column':
        plan['config']['metrics'][0]['column'] = 'Invented'
    elif mutation == 'operation':
        plan['config']['metrics'][0]['operation'] = 'eval'
    elif mutation == 'unknown':
        plan['config']['execute'] = 'code'
    elif mutation == 'missing':
        del plan['source']
    elif mutation == 'status':
        del plan['status']
    else:
        plan['source'] = 'absent.xlsx'
    mock_response(monkeypatch, plan)
    with pytest.raises(ValueError, match='OPENAI_'):
        planner.plan_with_openai('Revenue by Department', sources)


def test_missing_key_no_http(monkeypatch, sources):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(planner.requests, 'post', lambda *a, **k: pytest.fail('HTTP called'))
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        planner.plan_with_openai('Revenue', sources)


def test_api_error_sanitized(monkeypatch, sources):
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-private-key')
    def fail(*args, **kwargs):
        raise requests.HTTPError('fake-private-key provider-secret-payload')
    monkeypatch.setattr(planner.requests, 'post', fail)
    with pytest.raises(ValueError) as error:
        planner.plan_with_openai('Revenue', sources)
    assert 'fake-private-key' not in str(error.value)
    assert 'provider-secret-payload' not in str(error.value)


def test_refusal_rejected(monkeypatch, sources, plan):
    mock_response(monkeypatch, plan, refusal='Cannot comply')
    with pytest.raises(ValueError, match='OPENAI_'):
        planner.plan_with_openai('Revenue', sources)


def test_nonready_is_not_executable(monkeypatch, sources, plan):
    plan['status'] = 'clarify'
    plan['questions'] = ['Which year?']
    mock_response(monkeypatch, plan)
    result = planner.plan_with_openai('Revenue this year', sources)
    assert result['source'] is None
    assert result['config'] is None


def test_equivalent_sources_require_clarification(monkeypatch, sources, plan):
    sources['copy.xlsx'] = sources['sales.xlsx'].copy()
    mock_response(monkeypatch, plan)
    result = planner.plan_with_openai('Revenue by Department', sources)
    assert result['status'] == 'clarify'
    assert result['source'] is result['config'] is None


def test_explicit_source_cannot_be_overridden(monkeypatch, sources, plan):
    sources['copy.xlsx'] = sources['sales.xlsx'].copy()
    mock_response(monkeypatch, plan)
    with pytest.raises(ValueError):
        planner.plan_with_openai('Revenue from copy.xlsx', sources)


def test_policy_is_metadata_and_resolves_department(monkeypatch, sources, plan):
    sources['copy.xlsx'] = sources['sales.xlsx'].copy()
    plan['config']['filters'] = [{'column': 'Department', 'operator': 'eq', 'type': 'text', 'value': 'IT'}]
    calls = mock_response(monkeypatch, plan)
    policy = {'version': 1, 'department_sources': {'IT': 'sales.xlsx'}}
    result = planner.plan_with_openai('Revenue of IT by Department', sources, policy)
    assert result['status'] == 'ready'
    assert json.loads(calls[0][1]['json']['messages'][1]['content'])['source_policy'] == policy


def test_bounded_request_no_http(monkeypatch, sources):
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
    monkeypatch.setattr(planner.requests, 'post', lambda *a, **k: pytest.fail('HTTP called'))
    with pytest.raises(ValueError):
        planner.plan_with_openai('x' * 8001, sources)


def test_unsupported_clears_source_config(monkeypatch, sources, plan):
    plan['status'] = 'unsupported'
    plan['unsupported'] = ['Forecasts are unsupported']
    mock_response(monkeypatch, plan)
    result = planner.plan_with_openai('Forecast Revenue', sources)
    assert result['source'] is result['config'] is None


@pytest.mark.parametrize('body', [{}, {'choices': []}, {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]},
                                  {'choices': [{'finish_reason': 'stop', 'message': {'content': 'not JSON'}}]}])
def test_malformed_response_rejected(monkeypatch, sources, body):
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return body
    monkeypatch.setattr(planner.requests, 'post', lambda *a, **k: Response())
    with pytest.raises(ValueError, match='OPENAI_'):
        planner.plan_with_openai('Revenue', sources)


def test_engine_config_validation_is_applied(monkeypatch, sources, plan):
    plan['config']['metrics'].append(copy.deepcopy(plan['config']['metrics'][0]))
    mock_response(monkeypatch, plan)
    with pytest.raises(ValueError, match='OPENAI_'):
        planner.plan_with_openai('Revenue', sources)


def test_date_group_column_reference_validation(monkeypatch, sources, plan):
    plan['config']['date_group'] = {'column': 'missing date', 'frequency': 'month', 'alias': 'Month'}
    mock_response(monkeypatch, plan)
    with pytest.raises(ValueError, match='OPENAI_'):
        planner.plan_with_openai('Revenue by month', sources)


def test_invalid_summary_ranking_alias(monkeypatch, sources, plan):
    plan['config']['top_n'] = {'column': 'Revenue', 'n': 5, 'ascending': False, 'offset': 0, 'scope': 'summary'}
    mock_response(monkeypatch, plan)
    with pytest.raises(ValueError, match='OPENAI_'):
        planner.plan_with_openai('Top 5 departments', sources)

@pytest.mark.parametrize('scope', ['summary', 'detail'])
def test_valid_ranking_scope_converted_to_engine_config(monkeypatch, sources, plan, scope):
    if scope == 'detail':
        plan['config']['metrics'] = []
        plan['config']['group_by'] = []
    plan['config']['top_n'] = {'column': 'Total' if scope == 'summary' else 'Revenue',
                              'n': 1, 'ascending': False, 'offset': 0, 'scope': scope}
    mock_response(monkeypatch, plan)
    result = planner.plan_with_openai('highest takings', sources)
    assert result['status'] == 'ready'
    assert 'scope' not in result['config']['top_n']
    from app.services.report_engine import run_report
    report = run_report(sources['sales.xlsx'], result['config'])
    assert len(report['summary'] if scope == 'summary' else report['data']) == 1

def test_ready_with_unresolved_condition_rejected(monkeypatch, sources, plan):
    plan['questions'] = ['Which year?']
    mock_response(monkeypatch, plan)
    with pytest.raises(ValueError):
        planner.plan_with_openai('Revenue in March', sources)


@pytest.mark.parametrize('status',[400,401,403,429,503])
def test_http_error_classified_without_payload(monkeypatch,sources,status):
    from unittest.mock import Mock
    monkeypatch.setenv('OPENAI_API_KEY','fake-private-key')
    response=Mock(status_code=status)
    def fail(*args,**kwargs):
        raise requests.HTTPError('secret provider payload',response=response)
    monkeypatch.setattr(planner.requests,'post',fail)
    with pytest.raises(ValueError) as exc:
        planner.plan_with_openai('doanh thu nam 2024',sources)
    assert f'OPENAI_HTTP_{status}' in str(exc.value)
    assert 'secret' not in str(exc.value) and 'fake-private-key' not in str(exc.value)


def test_timeout_has_distinct_code(monkeypatch,sources):
    monkeypatch.setenv('OPENAI_API_KEY','test')
    def fail(*args,**kwargs):raise requests.Timeout('private')
    monkeypatch.setattr(planner.requests,'post',fail)
    with pytest.raises(ValueError,match='OPENAI_TIMEOUT'):
        planner.plan_with_openai('report',sources)



def test_unique_translated_column_references_resolved(monkeypatch):
    sources={'sales.xlsx':pd.DataFrame({'month':['2024-10'],'revenue':[100]})}
    plan={'status':'ready','source':'sales.xlsx','config':{'version':1,
        'filters':[{'column':'thang','operator':'between','type':'date','value':['2024-01-01','2024-12-31']}],
        'filter_logic':'and','group_by':[], 'metrics':[{'column':'doanh thu','operation':'sum','alias':'Total'}],
        'date_group':None,'top_n':None},'explanation':[],'questions':[],'unsupported':[]}
    mock_response(monkeypatch,plan)
    result=planner.plan_with_openai('xuat bao cao doanh thu nam 2024',sources)
    assert result['config']['filters'][0]['column']=='month'
    assert result['config']['metrics'][0]['column']=='revenue'
    from app.services.report_engine import run_report
    assert run_report(sources['sales.xlsx'],result['config'])['summary']['Total'].tolist()==[100]


def test_invented_year_not_silently_mapped(monkeypatch,plan,sources):
    plan['config']['filters']=[{'column':'year','operator':'eq','type':'number','value':2024}]
    mock_response(monkeypatch,plan)
    with pytest.raises(ValueError,match='OPENAI_PLAN_COLUMNS'):
        planner.plan_with_openai('report 2024',sources)


def test_ambiguous_synonym_not_guessed(monkeypatch,plan,sources):
    sources['sales.xlsx']['sales']=[10]
    plan['config']['metrics'][0]['column']='doanh thu'
    mock_response(monkeypatch,plan)
    with pytest.raises(ValueError,match='OPENAI_PLAN_COLUMNS'):
        planner.plan_with_openai('report',sources)
