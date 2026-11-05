"""Historical legacy superlative regressions plus AI-only command integration."""
import asyncio
from unittest.mock import Mock, patch
import json

import pandas as pd
import pytest

from legacy_nlp.analytical_request import is_analytical_request
from legacy_nlp.report_planner import plan_report
from app.services.reports.report_engine import run_report

PRODUCT_REQUEST = 'sản phẩm nào có doanh thu nhỏ nhất'
EMPLOYEE_REQUEST = 'nhân viên nào có lương cao nhất'


def sales():
    return pd.DataFrame({'product': ['A', 'A', 'B', 'C', 'D'],
                         'revenue': [1, 99, 50, 40, 10]})


def employees():
    return pd.DataFrame({'employee_id': ['e1', 'e2', 'e3'],
                         'employee_name': ['An', 'An', 'Binh'], 'salary': [20, 30, 40]})


def test_exact_product_request_executes_grouped_sum():
    frame = sales()
    assert is_analytical_request(PRODUCT_REQUEST)
    plan = plan_report(PRODUCT_REQUEST, {'sales.xlsx': frame})
    assert plan['status'] == 'ready', plan
    assert plan['config']['top_n'] == {'column': 'RevenueSum', 'n': 1, 'ascending': True}
    result = run_report(frame, plan['config'])['summary']
    assert result['product'].tolist() == ['D']
    assert result['RevenueSum'].tolist() == [10]


@pytest.mark.parametrize('qualifier,ascending', [
    ('cao nhất', False), ('lớn nhất', False), ('highest', False), ('largest', False),
    ('nhỏ nhất', True), ('thấp nhất', True), ('lowest', True), ('smallest', True),
])
def test_top_three_aliases_execute(qualifier, ascending):
    frame = sales()
    plan = plan_report('top 3 sản phẩm có doanh thu ' + qualifier, {'sales': frame})
    assert plan['status'] == 'ready', plan
    summary = run_report(frame, plan['config'])['summary']
    assert summary['product'].tolist() == (['D', 'C', 'B'] if ascending else ['A', 'B', 'C'])


def test_exact_employee_request_preserves_distinct_identities():
    frame = employees()
    assert is_analytical_request(EMPLOYEE_REQUEST)
    plan = plan_report(EMPLOYEE_REQUEST, {'hr.xlsx': frame})
    assert plan['status'] == 'ready', plan
    assert plan['config']['group_by'] == ['employee_id', 'employee_name']
    result = run_report(frame, plan['config'])['summary']
    assert result['employee_id'].tolist() == ['e3']
    assert result['SalarySum'].tolist() == [40]


def test_employee_sources_require_selection():
    frame = employees()
    plan = plan_report(EMPLOYEE_REQUEST, {'hr.xlsx': frame, 'payroll.xlsx': frame.copy()})
    assert plan['status'] == 'clarify'
    assert plan['config'] is None
    explicit = plan_report(EMPLOYEE_REQUEST + ' file hr.xlsx', {'hr.xlsx': frame, 'payroll.xlsx': frame.copy()})
    assert explicit['status'] == 'ready'
    assert explicit['source'] == 'hr.xlsx'


def test_duplicate_employee_names_without_id_require_clarification():
    plan = plan_report(EMPLOYEE_REQUEST, {'hr': employees().drop(columns='employee_id')})
    assert plan['status'] == 'clarify'
    assert plan['config'] is None


@pytest.mark.parametrize('suffix', ['cao nhất và nhỏ nhất', 'highest lowest'])
def test_contradictory_rankings_clarify(suffix):
    plan = plan_report('sản phẩm nào doanh thu ' + suffix, {'sales': sales()})
    assert plan['status'] == 'clarify'
    assert plan['config'] is None


def test_unknown_superlative_constraint_does_not_disappear():
    plan = plan_report(PRODUCT_REQUEST + ' sau thue', {'sales': sales()})
    assert plan['status'] == 'unsupported'
    assert plan['config'] is None


def test_exact_salary_question_routes_to_ai_chat_not_legacy_export(tmp_path, monkeypatch):
    from app.main import handle_command, CommandRequest
    from app.services.ai.openai_planner import PLAN_SCHEMA, _matches
    from app.services.ai.chat_agent import _SCHEMA
    inputs = tmp_path / 'input'
    inputs.mkdir()
    employees().to_excel(inputs / 'hr.xlsx', index=False)
    action = {'action': 'query', 'reply': 'Tinh luong cao nhat.', 'request': EMPLOYEE_REQUEST, 'update': None}
    plan = {'status': 'ready', 'source': 'hr.xlsx', 'config': {
        'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': ['employee_id', 'employee_name'],
        'metrics': [{'column': 'salary', 'operation': 'sum', 'alias': 'SalarySum'}],
        'date_group': None, 'top_n': {'column': 'SalarySum', 'n': 1, 'ascending': False, 'offset': 0, 'scope': 'summary'}},
        'explanation': [], 'questions': [], 'unsupported': []}
    assert _matches(action, _SCHEMA)
    assert _matches(plan, PLAN_SCHEMA)
    def response(payload):
        return Mock(json=lambda: {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(payload)}}]})
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-fixture-key')
    with patch('app.main.ensure_session'), patch('app.main.create_task', return_value=1), \
         patch('app.main.update_task_status'), patch('app.main.get_input_dir', return_value=inputs), \
         patch('app.services.reports.conversation_reporting.build_advanced_report_bytes') as export, \
         patch('requests.post', side_effect=[response(action), response(plan)]) as provider:
        result = asyncio.run(handle_command(CommandRequest(text=EMPLOYEE_REQUEST)))
    assert result.error is None
    assert result.parsed['intent'] == 'CHAT'
    assert result.result['action'] == 'query'
    assert result.result['result']['summary'] == [{'employee_id': 'e3', 'employee_name': 'Binh', 'SalarySum': 40}]
    assert result.result['result']['source_file'] == 'hr.xlsx'
    assert result.result['result']['output_path'] is None
    assert provider.call_count == 2
    export.assert_not_called()


def test_missing_display_name_does_not_hide_highest_salary():
    frame = employees()
    frame.loc[2, 'employee_name'] = None
    plan = plan_report(EMPLOYEE_REQUEST, {'hr': frame})
    assert plan['status'] == 'ready', plan
    assert run_report(frame, plan['config'])['summary']['employee_id'].tolist() == ['e3']


def test_one_id_with_conflicting_names_requires_clarification():
    frame = employees()
    frame.loc[2, 'employee_id'] = 'e1'
    plan = plan_report(EMPLOYEE_REQUEST, {'hr': frame})
    assert plan['status'] == 'clarify'
    assert plan['config'] is None
