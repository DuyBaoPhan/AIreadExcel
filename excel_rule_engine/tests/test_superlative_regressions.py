"""AI-only command integration for employee superlative requests."""
import asyncio
from unittest.mock import Mock, patch
import json

import pandas as pd


EMPLOYEE_REQUEST = 'nhân viên nào có lương cao nhất'


def employees():
    return pd.DataFrame({'employee_id': ['e1', 'e2', 'e3'],
                         'employee_name': ['An', 'An', 'Binh'], 'salary': [20, 30, 40]})


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
